# -*- coding: utf-8 -*-
# @Time        : 2022/11/19 13:09
# @File        : core.py
# @Description :

import os
import sys
import time
import json
import subprocess
import heapq

from collections import OrderedDict, defaultdict, abc
from datetime import datetime
from enum import Enum, auto
from functools import partial
from typing import List, Dict, Optional, Callable, Union, Iterable

import simulation.lib.config as config
from simulation.lib.common import logger, singleton, timer
from simulation.lib.public_conn_data import DataMsg, OrderMsg, SpecialDataMsg, DetailMsgType, PubMsgLabel
from simulation.lib.public_data import ImplementTask, InfoTask, BaseTask, SimStatus
from simulation.lib.sim_data import NaiveSimInfoStorage, ArterialSimInfoStorage
from simulation.connection.mqtt import MQTTConnection

# 校验环境变量中是否存在SUMO_HOME
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

import sumolib
import traci


@singleton
class SimCore:
    """仿真主体"""

    def __init__(self, sumo_cfg_fp: str, network_fp: str = None, arterial_storage: bool = False):
        """

        Args:
            sumo_cfg_fp: sumo cfg文件路径
            network_fp: 路网文件路径
            arterial_storage:
        """
        self._cfg_fp = sumo_cfg_fp
        self._net_fp = network_fp
        self.net = sumolib.net.readNet(network_fp, withLatestPrograms=True)  # 路网对象化数据
        self.connection = MQTTConnection()  # 通信接口实现数据外部交互
        self.step_limit = None  # 默认限制仿真运行时间, None为无限制
        self.storage = ArterialSimInfoStorage() if arterial_storage else NaiveSimInfoStorage()  # 仿真部分数据存储
        # 允许创建任务的函数返回一系列任务或单个任务，目的是为了保证不同类型的task creator函数只有单个
        # self.internal_task_creator: List[Callable[[], Union[Sequence[BaseTask], BaseTask]]] = []
        self.task_create_func: Dict[DetailMsgType,
                                    Callable[[Union[dict, str]], Optional[Union[BaseTask, Iterable[BaseTask]]]]] = {}
        self.cycle_task_queue: List[BaseTask] = []
        self.single_task_queue: List[BaseTask] = []

    def initialize(self, route_fp: str = None, detector_fp: Optional[str] = None, step_limit: int = None,
                   step_len: float = None):
        """
        初始化SUMO路网
        Args:
            route_fp: 车辆路径文件路径
            detector_fp: 检测器文件路径
            step_limit: 限制仿真运行时间(s), None为无限制
            step_len: 仿真单步时长

        Returns:

        """
        sumoBinary = sumolib.checkBinary('sumo-gui')
        sumoCmd = [sumoBinary, '-c', self._cfg_fp]
        if self._net_fp is not None:
            sumoCmd.extend(['-n', self._net_fp])
        if route_fp is not None:
            sumoCmd.extend(['-r', route_fp])
        if detector_fp is not None:
            sumoCmd.extend(['-a', detector_fp])
        if step_len is not None:
            sumoCmd.extend(['--step-length', str(step_len)])
        traci.start(sumoCmd)
        self.step_limit = step_limit
        self.storage.quick_init_update_execute(self.net, set(config.SimulationConfig.junction_region))

        # 运行仿真后添加订阅消息
        self.storage.initialize_sub_after_start()

    def initialize_internal_storage(self, *, junction_list=None):
        """仿真内部各功能模块初始化"""
        self.storage.initialize_sc(self.net, junction_list=junction_list)
        self.storage.initialize_participant(self.net, junction_list=junction_list)

    def connect(self, broker: str, port: int, topics=None):
        """通过MQTT通信完成与服务器的连接"""
        self.connection.connect(broker, port, topics)

    def is_connected(self):
        """通信是否处于连接状态"""
        return self.connection.state

    def add_new_task(self, new_task: BaseTask):
        if new_task.cycle_time is None:
            heapq.heappush(self.single_task_queue, new_task)
        else:
            heapq.heappush(self.cycle_task_queue, new_task)

    def run(self):
        logger.info('仿真开始')
        while traci.simulation.getMinExpectedNumber() >= 0:
            traci.simulationStep(0)
            # time.sleep(0.1)  # 临时加入

            current_timestamp = traci.simulation.getTime()
            SimStatus.time_rolling(current_timestamp)
            self.storage.update_storage()  # 执行storage更新任务
            self.handle_current_msg()  # 处理接收到的数据类消息，转化成控制任务

            # 周期执行任务
            if len(self.cycle_task_queue):
                top_task = self.cycle_task_queue[0]
                while top_task.exec_time < SimStatus.sim_time_stamp:
                    top_task.exec_time += top_task.cycle_time
                    if top_task.exec_time > SimStatus.sim_time_stamp:
                        heapq.heappop(self.cycle_task_queue)
                        heapq.heappush(self.cycle_task_queue, top_task)
                        top_task = self.cycle_task_queue[0]
                while top_task.exec_time == SimStatus.sim_time_stamp:
                    success, msg_label = top_task.execute()
                    if msg_label is not None and success:
                        self.connection.publish(msg_label)
                    top_task.exec_time = round(top_task.cycle_time + top_task.exec_time, 3)  # 防止浮点数运算时精度损失

                    heapq.heappop(self.cycle_task_queue)
                    heapq.heappush(self.cycle_task_queue, top_task)
                    top_task = self.cycle_task_queue[0]

            start = time.time()
            # 单次执行任务
            while len(self.single_task_queue):
                top_task = self.single_task_queue[0]
                if top_task.exec_time is None or top_task.exec_time == SimStatus.sim_time_stamp:
                    if isinstance(top_task, ImplementTask):
                        success, res = top_task.execute()  # TODO: 如果控制函数执行后需要在main中修改状态，需要通过返回值传递
                    elif isinstance(top_task, InfoTask):
                        start1 = time.time()
                        success, msg_label = top_task.execute()  # 返回结果: 执行是否成功, 需要发送的消息Optional[PubMsgLabel]
                        start2 = time.time()
                        if msg_label is not None and success:
                            self.connection.publish(msg_label)
                        end1 = time.time()
                        print(end1 - start2, start2 - start1)
                elif top_task.exec_time > SimStatus.sim_time_stamp:
                    break
                heapq.heappop(self.single_task_queue)

            end = time.time()
            # print(f'execute task consume time {end - start}')

            if self.step_limit is not None and current_timestamp > self.step_limit:
                break  # 完成仿真任务提前终止仿真程序

        logger.info('仿真结束')
        self._reset()
        SimStatus.reset()  # 仿真状态信息重置

    def _reset(self):
        """运行仿真结束后重置仿真状态"""
        self.step_limit = None
        self.storage.reset()

    def register_task_creator(self, msg_type: DetailMsgType,
                              handler_func: Callable[[Union[dict, str]], Optional[BaseTask]]):
        """注册从接收的数据转换成任务的处理方法"""
        self.task_create_func[msg_type] = handler_func

    def quick_register_task_creator_all(self):
        self.task_create_func[DataMsg.SignalScheme] = self.storage.create_signal_update_task
        self.task_create_func[DataMsg.SpeedGuide] = self.storage.create_speed_guide_task
        self.task_create_func[SpecialDataMsg.TransitionSS] = ...  # TODO: 过渡方案，要求获取signal_scheme的task
        self.task_create_func[SpecialDataMsg.SERequirement] = ...

    def handle_current_msg(self):
        """处理通过通信获得的消息，并转换成Tasks"""
        # 处理标准消息
        for msg_type, msg_info in self.connection.loading_msg(DataMsg):
            handler_func = self.task_create_func.get(msg_type)
            if handler_func is None:
                pass  # TODO: 不处理

            new_task = handler_func(msg_info)
            if new_task is not None:
                if isinstance(new_task, abc.Iterable):
                    for single_task in new_task:
                        self.add_new_task(single_task)
                else:
                    self.add_new_task(new_task)

    def auto_activate(self):
        """自动读取Config激活需要发送的消息类型"""
        msg_mapping = {
            'basic_safety_message': self.activate_bsm_publish,
            'roadside_safety_message': self.activate_rsm_publish,
            'signal_phase_and_timing': self.activate_spat_publish,
            'traffic_flow': self.activate_traffic_flow_publish,
            'signal_execution': self.activate_signal_execution_publish
        }

        for msg_type, pub_cycle in config.SimulationConfig.pub_msgs:
            activate_func = msg_mapping.get(msg_type)
            if activate_func is None:
                raise KeyError(f'message: {msg_type} is not supported')
            activate_func(config.SimulationConfig.junction_region, pub_cycle)

    def activate_spat_publish(self, intersections: List[str] = None, pub_cycle: float = 0.1):
        """
        激活仿真SPAT发送功能
        Args:
            intersections: 选定需要发送SPAT的交叉口, 若未提供参数则选中路网所有信控交叉口
            pub_cycle: 推送周期

        Returns:

        """

        if intersections is None:
            for ints_id, sc in self.storage.signal_controllers.items():
                self.add_new_task(
                    InfoTask(exec_func=sc.create_spat_pub_msg, cycle_time=pub_cycle, task_name=f'SPAT-{ints_id}'))
        else:
            for ints_id in intersections:
                sc = self.storage.signal_controllers.get(ints_id)
                if sc is None:
                    raise KeyError(f'intersection {ints_id} is not in current map')
                self.add_new_task(
                    InfoTask(exec_func=sc.create_spat_pub_msg, cycle_time=pub_cycle, task_name=f'SPAT-{ints_id}'))

    def activate_signal_execution_publish(self, intersections: List[str] = None, pub_cycle: float = 0.1):
        """
        激活仿真SignalExecution发送功能
        Args:
            intersections: 选定需要发送SE的交叉口, 若未提供参数则选中路网所有信控交叉口
            pub_cycle: 推送周期

        Returns:

        """
        if intersections is None:
            for ints_id, sc in self.storage.signal_controllers.items():
                self.add_new_task(
                    InfoTask(exec_func=sc.create_signal_execution_pub_msg, cycle_time=pub_cycle,
                             task_name=f'SignalExe-{ints_id}'))
        else:
            for ints_id in intersections:
                sc = self.storage.signal_controllers.get(ints_id)
                if sc is None:
                    raise KeyError(f'intersection {ints_id} is not in current map')
                self.add_new_task(
                    InfoTask(exec_func=sc.create_signal_execution_pub_msg, cycle_time=pub_cycle,
                             task_name=f'SignalExe-{ints_id}'))

    def activate_bsm_publish(self, intersections: List[str] = None, pub_cycle: float = 0.1):
        """
        激活仿真BSM发送功能
        Args:
            intersections: 选定需要发送BSM的交叉口范围区域, 若未提供参数则选中路网所有信控交叉口
            pub_cycle: 推送周期

        Returns:

        """
        if intersections is None:
            for ints_id, veh_container in self.storage.junction_veh_cons.items():
                self.add_new_task(InfoTask(exec_func=veh_container.create_bsm_pub_msg, cycle_time=pub_cycle,
                                           task_name=f'BSM-{ints_id}'))
        else:
            for ints_id in intersections:
                veh_container = self.storage.junction_veh_cons.get(ints_id)
                if veh_container is None:
                    raise KeyError(f'intersection {ints_id} is not current map')
                self.add_new_task(InfoTask(exec_func=veh_container.create_bsm_pub_msg, cycle_time=pub_cycle,
                                           task_name=f'BSM-{ints_id}'))

    def activate_rsm_publish(self, intersections: List[str] = None, pub_cycle: float = 0.1):
        """
        激活仿真RSM发送功能
        Args:
            intersections: 选定需要发送RSM的交叉口范围区域, 若未提供参数则选中路网所有信控交叉口
            pub_cycle: 推送周期

        Returns:

        """
        if intersections is None:
            for ints_id, veh_container in self.storage.junction_veh_cons.items():
                self.add_new_task(InfoTask(exec_func=veh_container.create_rsm_pub_msg, cycle_time=pub_cycle,
                                           task_name=f'RSM-{ints_id}'))
        else:
            for ints_id in intersections:
                veh_container = self.storage.junction_veh_cons.get(ints_id)
                if veh_container is None:
                    raise KeyError(f'intersection {ints_id} is not current map')
                self.add_new_task(InfoTask(exec_func=veh_container.create_rsm_pub_msg, cycle_time=pub_cycle,
                                           task_name=f'RSM-{ints_id}'))

    def activate_traffic_flow_publish(self, intersections: List[str] = None, pub_cycle: float = 60):
        """
        激活仿真TrafficFlow发送功能
        Args:
            intersections: 选定需要发送TF的交叉口, 若未提供参数则选中路网所有信控交叉口
            pub_cycle: 推送周期

        Returns:

        """
        self.add_new_task(
            InfoTask(self.storage.flow_status.create_traffic_flow_pub_msg, args=(intersections,), cycle_time=pub_cycle,
                     task_name=f'TrafficFlow'))


"""测评系统与仿真无关的内容均以事件形式定义(如生成json轨迹文件，发送评分等)，处理事件的函数的入参以关键词参数形式传入，返回值固定为None"""


class EvalEventType(Enum):
    START_EVAL = auto()
    ERROR = auto()
    FINISH_TASK = auto()
    FINISH_EVAL = auto()


class EventArgumentError(AttributeError):
    """事件参数未找到错误"""
    pass


eval_event_subscribers = defaultdict(list)  # 事件订阅


def subscribe_eval_event(event: EvalEventType, function: Callable) -> None:
    """
    注册将要处理的事件
    Args:
        event: 函数需要被执行时对应的事件类型
        function: 被执行的函数

    Returns:

    """
    eval_event_subscribers[event].append(function)


def emit_eval_event(event: EvalEventType, *args, **kwargs):
    """触发某类事件发生时对应的后续所有操作"""
    for func in eval_event_subscribers[event]:
        func(*args, **kwargs)


def handle_trajectory_record_event(*args, **kwargs) -> None:
    """
    以json文件形式保存轨迹

    Args:
        *args:
        **kwargs: 1) docker_name: str docker名 2) sub_name: str 子任务的文件名
                  3) traj_record_dir: str 轨迹数据存储路径 4) veh_info: dict 字典

    """

    traj_record_dir = kwargs.get('traj_record_dir', '../data/trajectory')  # 目录赞写死
    docker_name = kwargs.get('docker_name', 'test')
    docker_record_dir = os.path.join(traj_record_dir, docker_name)
    if not os.path.exists(docker_record_dir):
        os.mkdir(docker_record_dir)
    veh_info = kwargs.get('veh_info')
    sub_name = kwargs.get('sub_name', docker_name)
    path = os.path.join(traj_record_dir, docker_name, sub_name) + '.json'
    with open(path, 'w+') as f:
        json.dump(veh_info, f, indent=2)


def handle_multiple_trajectory_record_event(*args, **kwargs) -> None:
    trajectories = kwargs.get('trajectories')
    save_dir = '../data/trajectory'

    for junction_id, veh_info in trajectories.items():
        # handle_trajectory_record_event(traj_record_dir=save_dir, veh_info=veh_info)
        handle_trajectory_record_event(traj_record_dir=save_dir, docker_name="test",
                                       sub_name='_'.join(('test', junction_id)), veh_info=veh_info)

    logger.info(f'轨迹记录已保存在{save_dir}')


def handle_eval_apply_event(*args, **kwargs) -> None:
    """
    执行测评系统获取评分
    Args:
        *args:
        **kwargs: required argument: 
        1) eval_exe_path: str 评测exe路径
        2) docker_name: str docker名 
        3) traj_record_dir: str 轨迹数据存储路径
        4) eval_record_dir: str 评测结果存储路径 结果存储于eval_record_dir/docker_name/sub_name.json
    Returns:

    """
    eval_exe_path = kwargs.get('eval_exe_path', '../bin/eval.exe')  # ../bin/eval.exe
    docker_name = kwargs.get('docker_name', 'test')
    traj_record_dir = kwargs.get('traj_record_dir', '../data/trajectory')  # ../data/trajectory/
    eval_record_dir = kwargs.get('eval_record_path', '../data/evaluation')  # ../data/evaluation/
    junction_info_dir = kwargs.get('junction_info_dir', '../data/junction')
    # if eval_record_dir is None:
    #     raise EventArgumentError('apply score event handling requires key-only argument "eval_record"')
    # if docker_name is None:
    #     raise EventArgumentError('apply score event handling requires key-only argument "eval_name"')

    # traj_file_path = ''
    # eval_file_path = ''
    # 运行测评程序得到eval res
    docker_eval_record_dir = os.path.join(eval_record_dir, docker_name)
    if not os.path.exists(docker_eval_record_dir):
        os.mkdir(docker_eval_record_dir)
    docker_traj_record_dir = os.path.join(traj_record_dir, docker_name)
    for file in os.listdir(docker_traj_record_dir):
        traj_file_path = os.path.join(docker_traj_record_dir, file)
        eval_file_path = os.path.join(docker_eval_record_dir, file)
        eval_cmd = [eval_exe_path, traj_file_path, junction_info_dir, eval_file_path]
        process = subprocess.Popen(eval_cmd)
        exit_code = process.wait()
        # 仅在评测异常时由主程序写入结果，否则由评测程序写入
        if exit_code != 0:
            eval_res = {'score': -1, 'detail': 'evaluation faliure'}
            with open(eval_file_path, 'w+') as f:
                json.dump(eval_res, f)


def handle_score_report_event(*args, **kwargs) -> None:
    """
    分数上报 多流量仿真评测时合并评测分数
    Args:
        *args:
        **kwargs:
        1) eval_record_dir: str 评测结果存储路径
        2) docker_name: str docker名 
        3) connection mqtt连接
    """
    eval_record_dir = kwargs.get('eval_record_dir', '../data/evaluation')
    docker_name = kwargs.get('docker_name', 'test')

    # eval_record_dir = kwargs.get('eval_record_dir')
    # docker_name = kwargs.get('docker_name')
    all_result = {'score': 0, 'name': docker_name, 'abnormal': 0}
    detail = {'errorTimes': 0, 'detailInfo': []}
    eval_count = 0
    for file in os.listdir(os.path.join(eval_record_dir, docker_name)):
        eval_count += 1
        with open(os.path.join(eval_record_dir, docker_name, file), 'r') as f:
            single_result: dict = json.load(f)
            if single_result['score'] == -1:  # evaluation error
                all_result['abnormal'] = 1
                detail['errorTimes'] = detail['errorTimes'] + 1
                detail['detailInfo'].append(single_result['detail'])
            else:
                all_result['score'] = all_result['score'] + single_result['score']
                detail['detailInfo'].append(single_result)
    all_result['score'] = float(all_result['score']) / float(eval_count)
    all_result['detail'] = detail
    connection = kwargs.get('connection')
    connection.publish(PubMsgLabel(all_result, OrderMsg.ScoreReport, 'json'))


def initialize_score_prepare():
    """注册评分相关的事件"""
    # subscribe_eval_event(EvalEventType.FINISH_TASK, handle_trajectory_record_event)
    subscribe_eval_event(EvalEventType.FINISH_TASK, handle_multiple_trajectory_record_event)
    subscribe_eval_event(EvalEventType.START_EVAL, handle_eval_apply_event)
    subscribe_eval_event(EvalEventType.FINISH_EVAL, handle_score_report_event)


@singleton
class AlgorithmEval:
    def __init__(self):
        self.sim = SimCore(config.SetupConfig.config_file_path,
                           config.SetupConfig.network_file_path,
                           config.SetupConfig.arterial_mode)
        self.testing_name: str = config.SetupConfig.test_name
        self.eval_record: Dict[str, dict] = {}
        self.__eval_start_func: Optional[Callable[[], None]] = None

        # 通信
        self.sim.connect(config.ConnectionConfig.broker, config.ConnectionConfig.port)

        # 注册任务生成函数
        self.sim.quick_register_task_creator_all()

        # 初始化内部仿真内部功能模块
        self.sim.initialize_internal_storage(junction_list=config.SimulationConfig.junction_region)

        # 仿真运行开始方式
        self.mode_setting(config.SetupConfig.is_route_directory(),
                          config.SetupConfig.route_file_path,
                          detector_fp=config.SetupConfig.detector_file_path)

        # 注册仿真各环节触发的事件
        self.auto_initialize_event()

    def sim_task_start(self, route_fp: str, detector_fp: Optional[str] = None, step_limit: int = None, step_len: float = None):
        self.sim.initialize(route_fp, detector_fp, step_limit, step_len)
        self.sim.run()
        emit_eval_event(EvalEventType.FINISH_TASK, sim_core=self.sim, eval_record=self.eval_record,
                        trajectories=self.sim.storage.trajectory_info)

        traci.close()

        # using for test
        self.eval_task_start(connection=self.sim.connection)

    def eval_task_start(*args, **kwargs):
        emit_eval_event(EvalEventType.START_EVAL, *args, **kwargs)
        emit_eval_event(EvalEventType.FINISH_EVAL, *args, **kwargs)

    @staticmethod
    def auto_initialize_event():
        initialize_score_prepare()

    def sim_task_from_directory(self, sce_dir_fp: str, detector_fp: Optional[str], *, f_name_startswith: str = None,
                                step_limit: int = None, step_len: float = None):
        """
        从文件夹中读取所有流量文件创建评测任务

        Args:
            sce_dir_fp: route文件所在文件夹
            detector_fp: 检测器文件
            f_name_startswith: 指定route文件命名开头
            step_limit: 仿真总时长
            step_len: 仿真步长

        Returns:

        """
        route_fps = []
        for file in os.listdir(sce_dir_fp):
            if f_name_startswith is None or file.startswith(f_name_startswith):
                route_fps.append('/'.join((sce_dir_fp, file)))
        for route_fp in route_fps:
            self.sim_task_start(route_fp, detector_fp, step_limit, step_len)

    def mode_setting(self, multiple_file: bool, route_fp: str, *, detector_fp: Optional[str] = None) -> None:
        """
        调用loop_start前，指定测评时流量文件读取模式
        Args:
            multiple_file: 是否为单个文件
            route_fp: route文件路径
            detector_fp: 检测器文件

        Returns:

        """
        if multiple_file:
            self.__eval_start_func = partial(self.sim_task_from_directory,
                                             sce_dir_fp=route_fp,
                                             detector_fp=detector_fp,
                                             step_limit=config.SimulationConfig.sim_time_limit,
                                             step_len=config.SimulationConfig.sim_time_step)
        else:
            self.__eval_start_func = partial(self.sim_task_start,
                                             route_fp=route_fp,
                                             detector_fp=detector_fp,
                                             step_limit=config.SimulationConfig.sim_time_limit,
                                             step_len=config.SimulationConfig.sim_time_step)

    def loop_start(self, test_name_split: str = ' '):
        """
        阻塞形式开始测评，接受start命令后开始运行
        Args:
            test_name_split: start指令中提取算法名称的分割字符，取最后一部分为测试的名称

        Returns:

        """
        sim = self.sim
        if not sim.is_connected():
            raise RuntimeError('与服务器处于未连接状态,请先创建连接')
        while True:
            recv_msgs = sim.connection.loading_msg(OrderMsg)

            # 有数据时会才会进入循环
            for msg_type, msg_ in recv_msgs:
                print(msg_)
                if msg_type is OrderMsg.Start:
                    self.testing_name = msg_['docker'].split(test_name_split)[-1]  # 获取分割后的最后一部分作为测试名称
                    self.__eval_start_func()

                    self.eval_task_start(connection=self.sim.connection)

    def start(self):
        """运行仿真测评"""
        if config.SetupConfig.await_start_cmd:
            self.loop_start()
        else:
            self.__eval_start_func()
