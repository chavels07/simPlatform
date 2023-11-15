# -*- coding: utf-8 -*-
# @Time        : 2022/11/19 13:09
# @File        : core.py
# @Description : 仿真平台及测评系统核心模块

import os
import sys
import re
import json
import subprocess
import time
import traceback
import heapq

from collections import defaultdict, abc
from enum import Enum, auto
from functools import partial
from itertools import chain
from typing import List, Dict, Optional, Callable, Union, Iterable

import simulation.lib.config as config
from simulation.lib.common import logger, singleton, ImplementCounter
from simulation.lib.public_conn_data import DataMsg, OrderMsg, SpecialDataMsg, DetailMsgType, PubMsgLabel
from simulation.lib.public_data import ImplementTask, InfoTask, BaseTask, SimStatus
from simulation.lib.sim_data import SimInfoStorage, ArterialSimInfoStorage
from simulation.connection.mqtt import MQTTConnection

# 校验环境变量中是否存在SUMO_HOME
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

import sumolib
import traci


SIM_FLAG_FINISH = 0  # 仿真正常
SIM_FLAG_ERROR = 1  # 仿真错误
SIM_FLAG_TERMINATE = 2  # 外部中断命令


@singleton
class Simulation:
    """仿真平台系统
    Notes:
        ----------使用说明----------
        初始化过程
        1) 调用initialize_storage方法  # 初始化交叉口、信号灯内部存储状态
        2) 调用initialize_sumo方法     # 根据配置信息启动SUMO应用程序

        仿真执行
        run

    """

    def __init__(self, arterial_storage: bool = config.SetupConfig.arterial_mode):
        """

        Args:
            arterial_storage:
        """
        self.sim_core = SimCoreSUMO()
        self.storage = ArterialSimInfoStorage() if arterial_storage else SimInfoStorage()  # 仿真部分数据存储
        # 允许创建任务的函数返回一系列任务或单个任务，目的是为了保证不同类型的task creator函数只有单个
        # self.internal_task_creator: List[Callable[[], Union[Sequence[BaseTask], BaseTask]]] = []
        self.task_queue = TaskQueue()
        self.terminate_func: Optional[Callable[[], bool]] = None

    def initialize_sumo(self,
                        sumo_cfg_fp: str,
                        network_fp: str,
                        route_fp: str,
                        detector_fp: str,
                        sim_time_len: float,
                        sim_time_limit: Optional[int] = None,
                        warm_up_time: int = 0):
        """
        初始化SUMO路网
        Args:
            sumo_cfg_fp: sumo cfg文件路径
            network_fp: 路网文件路径
            route_fp: 车辆路径文件路径
            detector_fp: 检测器文件路径
            sim_time_len: 仿真单步时长
            sim_time_limit: 仿真时长限制
            warm_up_time: 预热时间

        Returns:

        """
        # 初始化地图

        sumoBinary = sumolib.checkBinary('sumo-gui')
        sumoCmd = [sumoBinary, '-c', sumo_cfg_fp]
        if network_fp is not None:
            sumoCmd.extend(['-n', network_fp])
        if route_fp is not None:
            sumoCmd.extend(['-r', route_fp])
        if detector_fp is not None:
            sumoCmd.extend(['-a', detector_fp])
        if sim_time_len is not None:
            sumoCmd.extend(['--step-length', str(sim_time_len)])
        traci.start(sumoCmd)

        self.sim_core.sim_time_limit = sim_time_limit
        self.sim_core.warm_up_time = warm_up_time

        # 运行仿真后添加订阅消息
        self.storage.initialize_subscribe_after_start()

    def initialize_storage(self, network_fp, *, junction_list=None,
                           trajectory_feature: bool = True,
                           traffic_flow_feature: bool = False):
        """平台内部各功能模块仿真场景范围初始化"""

        self.sim_core.load_net(network_fp)
        self.storage.initialize_signal_controller(self.sim_core.net, junction_list=junction_list)
        self.storage.initialize_traffic_flow(self.sim_core.net, junction_list=junction_list)
        self.storage.initialize_participant(self.sim_core.net, junction_list=junction_list)

        self.storage.initialize_update_execute(trajectory_update=trajectory_feature,
                                               traffic_flow_update=traffic_flow_feature)

    def run(self, connection: MQTTConnection) -> int:
        """
        仿真运行

        Args:
            connection: 实现数据外部交互的MQTT通信接口

        Returns:
            返回状态: 0: 正常, 1: 异常, 2: 外部中断命令

        Notes:
            每一仿真步需要依次处理的事项
            1) 仿真程序单步运行
            2) 根据仿真程序的最新状态更新storage
            3) 处理通信接收到的控制命令，转化成控制任务
            4) 维护任务池执行当前步需完成的任务
        """
        self._reset()  # 预先清楚上一次仿真运行可能遗留的数据
        ret_val = SIM_FLAG_FINISH

        logger.info('仿真开始')
        try:
            while traci.simulation.getMinExpectedNumber() >= 0:

                self.sim_core.run_single_step()
                # time.sleep(0.03)

                if self.sim_core.waiting_warm_up():
                    continue

                self.storage.update_storage()  # 执行storage更新任务

                # 处理接收到的数据类消息，转化成控制任务
                for msg_type, msg_info in connection.loading_msg(DataMsg):
                    self.task_queue.handle_current_msg(msg_type, msg_info)

                # 推送各消息类任务产生消息
                for msg in chain(self.task_queue.cycle_task_execute(), self.task_queue.single_task_execute()):
                    connection.publish(msg)

                if self.sim_core.reach_limit():
                    break  # 完成仿真任务提前终止仿真程序

                # 提前终止仿真
                if self.terminate_func is not None and self.terminate_func():
                    ret_val = SIM_FLAG_TERMINATE
                    break
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logger.error(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
            ret_val = SIM_FLAG_ERROR

        logger.info('仿真结束')
        SimStatus.reset()  # 仿真状态信息重置
        return ret_val

    def _reset(self):
        """运行仿真结束后重置仿真状态"""
        self.storage.reset()
        self.task_queue.reset(single_only=True)

    def quick_register_task_creator_all(self):
        """快速注册从接收的数据转换成任务的处理方法"""
        self.task_queue.register_task_creator(
            DataMsg.SignalScheme,
            partial(self.storage.create_signal_scheme_update_task, callback=implement_counter.implement_reaction)
        )
        self.task_queue.register_task_creator(
            DataMsg.SignalRequest,
            partial(self.storage.create_signal_request_update_task, callback=implement_counter.implement_reaction)
        )

        self.task_queue.register_task_creator(
            DataMsg.SpeedGuide,
            partial(self.storage.create_speed_guide_task, callback=implement_counter.implement_reaction)
        )
        # self.task_create_func[DataMsg.SignalScheme] = self.storage.create_signal_scheme_update_task
        # self.task_create_func[DataMsg.SpeedGuide] = self.storage.create_speed_guide_task
        # self.task_create_func[SpecialDataMsg.TransitionSS] = ...  # TODO: 过渡方案，要求获取signal_scheme的task
        # self.task_create_func[SpecialDataMsg.SERequirement] = ...

    def auto_activate_publish(self):
        """自动读取Config激活需要发送的消息类型"""
        msg_mapping = {
            'basicSafetyMessage': self.task_queue.activate_bsm_publish,
            'roadsideSafetyMessage': self.task_queue.activate_rsm_publish,
            'signalPhaseAndTiming': self.task_queue.activate_spat_publish,
            'trafficFlow': self.task_queue.activate_traffic_flow_publish,
            'signalExecution': self.task_queue.activate_signal_execution_publish
        }

        for msg_type, pub_cycle in config.SimulationConfig.pub_msgs:
            activate_func = msg_mapping.get(msg_type)
            if activate_func is None:
                raise KeyError(f'message: {msg_type} is not supported')
            activate_func(self.storage, config.SimulationConfig.junction_region, pub_cycle)


class SimCoreSUMO:
    """SUMO仿真控制"""

    def __init__(self):
        self._net = None
        self._sim_time_limit = None
        self._warm_up_time = 0

    def load_net(self, network_fp: str):
        self._net = sumolib.net.readNet(network_fp, withLatestPrograms=True)  # 静态路网对象化数据

    @property
    def net(self):
        if self._net is None:
            raise RuntimeError('sumo core has not been initialize')
        return self._net

    @property
    def sim_time_limit(self):
        return self._sim_time_limit

    @sim_time_limit.setter
    def sim_time_limit(self, value: Optional[int]):
        if isinstance(value, int) and value < 0:
            raise ValueError('simulation time limit must be greater than 0')
        self._sim_time_limit = value

    @property
    def warm_up_time(self):
        return self._warm_up_time

    @warm_up_time.setter
    def warm_up_time(self, value: int):
        if isinstance(value, int) and (
                value < 0 or self._sim_time_limit is not None and self.warm_up_time > self.sim_time_limit):
            raise ValueError(f'invalid warm up time {value} s')
        self._warm_up_time = value

    def run_single_step(self):
        traci.simulationStep(0)
        SimStatus.time_rolling(traci.simulation.getTime())

    def reach_limit(self):
        if self.sim_time_limit is not None and SimStatus.sim_time_stamp > self.sim_time_limit:
            return True
        return False

    def waiting_warm_up(self):
        if SimStatus.sim_time_stamp < self.warm_up_time:
            return True
        return False


implement_counter = ImplementCounter()


class TaskQueue:
    """任务池"""

    def __init__(self):
        self.cycle_task_queue: List[BaseTask] = []
        self.single_task_queue: List[BaseTask] = []
        self._task_create_func: Dict[DetailMsgType,
        Callable[[Union[dict, str]], Optional[Union[BaseTask, Iterable[BaseTask]]]]] = {}

    def add_new_task(self, new_task: BaseTask):
        """添加新任务"""
        if new_task.cycle_time is None:
            heapq.heappush(self.single_task_queue, new_task)
        else:
            heapq.heappush(self.cycle_task_queue, new_task)

    def cycle_task_execute(self) -> List[PubMsgLabel]:
        """
        执行周期性任务，任务执行后将更新下次执行时间

        Returns: 需要推送的消息

        """
        publish_msgs = []

        if len(self.cycle_task_queue):
            top_task = self.cycle_task_queue[0]
            while top_task.exec_time < SimStatus.sim_time_stamp:
                top_task.exec_time = round(top_task.cycle_time + top_task.exec_time, 3)  # 防止浮点数运算时精度损失
                if top_task.exec_time > SimStatus.sim_time_stamp:
                    heapq.heappop(self.cycle_task_queue)
                    heapq.heappush(self.cycle_task_queue, top_task)
                    top_task = self.cycle_task_queue[0]
            while top_task.exec_time == SimStatus.sim_time_stamp:
                success, msg_label = top_task.execute()
                if msg_label is not None and success:
                    publish_msgs.append(msg_label)
                top_task.exec_time = round(top_task.cycle_time + top_task.exec_time, 3)

                heapq.heappop(self.cycle_task_queue)
                heapq.heappush(self.cycle_task_queue, top_task)
                top_task = self.cycle_task_queue[0]
        return publish_msgs

    def single_task_execute(self) -> List[PubMsgLabel]:
        """
        执行非周期性任务，任务执行后会被移除

        Returns: 需要推送的消息

        """
        publish_msgs = []
        while len(self.single_task_queue):
            top_task = self.single_task_queue[0]
            if top_task.exec_time is None or top_task.exec_time == SimStatus.sim_time_stamp:
                if isinstance(top_task, ImplementTask):
                    success, res = top_task.execute()
                elif isinstance(top_task, InfoTask):
                    success, msg_label = top_task.execute()  # 返回结果: 执行是否成功, 需要发送的消息Optional[PubMsgLabel]
                    if msg_label is not None and success:
                        publish_msgs.append(msg_label)
            elif top_task.exec_time > SimStatus.sim_time_stamp:
                break
            heapq.heappop(self.single_task_queue)
        return publish_msgs

    def handle_current_msg(self, msg_type: DetailMsgType, msg_info: dict, unbound_warning: bool = False):
        """
        处理通过通信获得的消息，并转换成Tasks
        Args:
            msg_type: 消息类型
            msg_info: 消息内容
            unbound_warning: 为绑定消息处理方法时是否提醒

        Returns:

        """
        # 处理标准消息
        handler_func = self._task_create_func.get(msg_type)
        if handler_func is None:
            if unbound_warning:
                logger.warn(f'{msg_type}类型消息的处理方法未绑定，无法创建更新任务')

        new_task = handler_func(msg_info)
        if new_task is not None:
            if isinstance(new_task, abc.Iterable):
                for single_task in new_task:
                    self.add_new_task(single_task)
            else:
                self.add_new_task(new_task)

    def register_task_creator(self, msg_type: DetailMsgType,
                              handler_func: Callable[[Union[dict, str]], Optional[BaseTask]]):
        """
        注册从接收的数据转换成任务的处理方法
        Args:
            msg_type: 消息类型
            handler_func: 消息处理转换成任务的方法

        Returns:

        """
        self._task_create_func[msg_type] = handler_func

    def reset(self, single_only: bool = False):
        """重置任务池"""
        if not single_only:
            self.cycle_task_queue.clear()
        self.single_task_queue.clear()

    def activate_spat_publish(self, storage: SimInfoStorage, intersections: List[str] = None, pub_cycle: float = 0.1):
        """
        激活仿真SPAT发送功能
        Args:
            storage: 仿真数据存储器
            intersections: 选定需要发送SPAT的交叉口, 若未提供参数则选中路网所有信控交叉口
            pub_cycle: 推送周期

        Returns:

        """

        if intersections is None:
            for ints_id, sc in storage.signal_controllers.items():
                self.add_new_task(
                    InfoTask(exec_func=sc.create_spat_pub_msg, cycle_time=pub_cycle, task_name=f'SPAT-{ints_id}'))
        else:
            for ints_id in intersections:
                sc = storage.signal_controllers.get(ints_id)
                if sc is None:
                    raise KeyError(f'cannot find intersection {ints_id} in storage')
                self.add_new_task(
                    InfoTask(exec_func=sc.create_spat_pub_msg, cycle_time=pub_cycle, task_name=f'SPAT-{ints_id}'))

    def activate_signal_execution_publish(self, storage: SimInfoStorage, intersections: List[str] = None,
                                          pub_cycle: float = 0.1):
        """
        激活仿真SignalExecution发送功能
        Args:
            storage: 仿真数据存储器
            intersections: 选定需要发送SE的交叉口, 若未提供参数则选中路网所有信控交叉口
            pub_cycle: 推送周期

        Returns:

        """
        if intersections is None:
            for ints_id, sc in storage.signal_controllers.items():
                self.add_new_task(
                    InfoTask(exec_func=sc.create_signal_execution_pub_msg, cycle_time=pub_cycle,
                             task_name=f'SignalExe-{ints_id}'))
        else:
            for ints_id in intersections:
                sc = storage.signal_controllers.get(ints_id)
                if sc is None:
                    raise KeyError(f'cannot find intersection {ints_id} in storage')
                self.add_new_task(
                    InfoTask(exec_func=sc.create_signal_execution_pub_msg, cycle_time=pub_cycle,
                             task_name=f'SignalExe-{ints_id}'))

    def activate_bsm_publish(self, storage: SimInfoStorage, intersections: List[str] = None, pub_cycle: float = 0.1):
        """
        激活仿真BSM发送功能
        Args:
            storage: 仿真数据存储器
            intersections: 选定需要发送BSM的交叉口范围区域, 若未提供参数则选中路网所有信控交叉口
            pub_cycle: 推送周期

        Returns:

        """
        if intersections is None:
            for ints_id, veh_container in storage.junction_veh_cons.items():
                self.add_new_task(InfoTask(exec_func=veh_container.create_bsm_pub_msg, cycle_time=pub_cycle,
                                           task_name=f'BSM-{ints_id}'))
        else:
            for ints_id in intersections:
                veh_container = storage.junction_veh_cons.get(ints_id)
                if veh_container is None:
                    raise KeyError(f'cannot find intersection {ints_id} in storage')
                self.add_new_task(InfoTask(exec_func=veh_container.create_bsm_pub_msg, cycle_time=pub_cycle,
                                           task_name=f'BSM-{ints_id}'))

    def activate_rsm_publish(self, storage: SimInfoStorage, intersections: List[str] = None, pub_cycle: float = 0.1):
        """
        激活仿真RSM发送功能
        Args:
            storage: 仿真数据存储器
            intersections: 选定需要发送RSM的交叉口范围区域, 若未提供参数则选中路网所有信控交叉口
            pub_cycle: 推送周期

        Returns:

        """
        if intersections is None:
            for ints_id, veh_container in storage.junction_veh_cons.items():
                self.add_new_task(InfoTask(exec_func=veh_container.create_rsm_pub_msg, cycle_time=pub_cycle,
                                           task_name=f'RSM-{ints_id}'))
        else:
            for ints_id in intersections:
                veh_container = storage.junction_veh_cons.get(ints_id)
                if veh_container is None:
                    raise KeyError(f'cannot find intersection {ints_id} in storage')
                self.add_new_task(InfoTask(exec_func=veh_container.create_rsm_pub_msg, cycle_time=pub_cycle,
                                           task_name=f'RSM-{ints_id}'))

    def activate_traffic_flow_publish(self, storage: SimInfoStorage, intersections: List[str] = None,
                                      pub_cycle: float = 60):
        """
        激活仿真TrafficFlow发送功能
        Args:
            storage: 仿真数据存储器
            intersections: 选定需要发送TF的交叉口, 若未提供参数则选中路网所有信控交叉口
            pub_cycle: 推送周期

        Returns:

        """
        if intersections is None:
            for ints_id, flow_container in storage.flow_cons.items():
                self.add_new_task(InfoTask(exec_func=flow_container.create_traffic_flow_pub_msg, cycle_time=pub_cycle,
                                           task_name=f'TF-{ints_id}'))
        else:
            for ints_id in intersections:
                flow_container = storage.flow_cons.get(ints_id)
                if flow_container is None:
                    raise KeyError(f'cannot find intersection {ints_id} in storage')
                self.add_new_task(InfoTask(exec_func=flow_container.create_traffic_flow_pub_msg, cycle_time=pub_cycle,
                                           task_name=f'TF-{ints_id}'))


@singleton
class AlgorithmEval:
    def __init__(self):
        self.sim = Simulation()
        self.testing_name: str = config.SetupConfig.test_name
        self.eval_record: Dict[str, dict] = {}
        self.__eval_start_func: Optional[Callable] = None

        # 仿真运行开始方式
        self.mode_setting(config.SetupConfig.route_file_path,
                          config.SetupConfig.is_route_directory())

        # 注册仿真各环节触发的事件
        self.auto_initialize_event()

    def initialize_storage(self):
        """初始化内部仿真内部功能模块，先于simulation初始化"""
        self.sim.initialize_storage(config.SetupConfig.network_file_path,
                                    junction_list=config.SimulationConfig.junction_region,
                                    traffic_flow_feature=any(
                                        msg.name == config.CONFIG_MSG_NAME['TF'] for msg in
                                        config.SimulationConfig.pub_msgs))

    def _initialize_simulation(self, route_fp: str):
        """初始化仿真内容"""
        self.sim.initialize_sumo(sumo_cfg_fp=config.SetupConfig.config_file_path,
                                 network_fp=config.SetupConfig.network_file_path,
                                 route_fp=route_fp,
                                 detector_fp=config.SetupConfig.detector_file_path,
                                 sim_time_len=config.SimulationConfig.sim_time_step,
                                 sim_time_limit=config.SimulationConfig.sim_time_limit,
                                 warm_up_time=config.SimulationConfig.warm_up_time)
        # 注册任务生成函数
        self.sim.quick_register_task_creator_all()

    def _detect_terminate_signal(self, connection: MQTTConnection):
        recv_msgs = connection.loading_msg(OrderMsg)

        for msg_type, msg_ in recv_msgs:
            if msg_type is OrderMsg.Terminate:
                if msg_['name'] == self.testing_name:
                    return True
        return False

    def sim_task_start(self, connection: MQTTConnection, sim_task_name: str = 'default') -> int:
        """开始运行仿真任务"""
        emit_eval_event(EvalEventType.BEFORE_TASK, connection=connection)

        # 注册退出函数
        if self.sim.terminate_func is None:
            self.sim.terminate_func = partial(self._detect_terminate_signal, connection=connection)

        sim_ret_val = self.sim.run(connection=connection)
        emit_eval_event(EvalEventType.FINISH_TASK, sim_core=self.sim, eval_record=self.eval_record,
                        trajectories=self.sim.storage.trajectory_info, docker_name=self.testing_name)

        traci.close()

        self.eval_task_start(connection=connection, docker_name=self.testing_name, task_name=sim_task_name,
                             eval_record=self.eval_record)
        return sim_ret_val

    def eval_task_start(*args, **kwargs):
        emit_eval_event(EvalEventType.START_EVAL, *args, **kwargs)
        emit_eval_event(EvalEventType.FINISH_EVAL, *args, **kwargs)

    @staticmethod
    def auto_initialize_event():
        initialize_score_prepare()

    def sim_task_single_scenario(self, connection: MQTTConnection, route_fp: str):
        """从单个流量文件创建测评任务"""
        self._initialize_simulation(route_fp)
        self.sim.auto_activate_publish()
        sim_ret_val = self.sim_task_start(connection)

        emit_eval_event(EvalEventType.FINISH_ALL_TEST_BATCH,
                        docker_name=self.testing_name,
                        connection=connection,
                        eval_record=self.eval_record)

    def sim_task_from_directory(self, connection: MQTTConnection, sce_dir_fp: str, *, f_name_startswith: str = None):
        """
        从文件夹中读取所有流量文件创建评测任务

        Args:
            connection: MQTT通信连接
            sce_dir_fp: route路径文件所在文件夹
            f_name_startswith: 指定route文件命名开头

        Returns:

        """
        route_fps = []
        for file in os.listdir(sce_dir_fp):
            if f_name_startswith is None or file.startswith(f_name_startswith):
                route_fps.append('/'.join((sce_dir_fp, file)))
        for index, route_fp in enumerate(route_fps, start=1):
            self._initialize_simulation(route_fp=route_fp)
            self.sim.auto_activate_publish()
            sim_ret_val = self.sim_task_start(connection, sim_task_name=str(index))

            # 提前终止仿真运行
            if sim_ret_val == SIM_FLAG_TERMINATE:
                break

        emit_eval_event(EvalEventType.FINISH_ALL_TEST_BATCH,
                        docker_name=self.testing_name,
                        connection=connection,
                        eval_record=self.eval_record)

    def mode_setting(self, route_fp: str, multiple_file: bool) -> None:
        """
        调用loop_start前，指定测评时流量文件读取模式

        Args:
            route_fp: 路径文件/目录地址
            multiple_file: 是否为单个文件

        Returns:

        """
        if multiple_file:
            self.__eval_start_func = partial(self.sim_task_from_directory, sce_dir_fp=route_fp)
        else:
            self.__eval_start_func = partial(self.sim_task_single_scenario, route_fp=route_fp)

    def loop_start(self, connection: MQTTConnection, *, test_name_split: str = ' '):
        """
        阻塞形式开始测评，接受start命令后开始运行

        Args:
            connection: MQTT通信连接
            test_name_split: start指令中提取算法名称的分割字符，取最后一部分为测试的名称

        Returns:

        """
        while True:
            recv_msgs = connection.loading_msg(OrderMsg)

            # 有数据时会才会进入循环
            for msg_type, msg_ in recv_msgs:
                if msg_type is OrderMsg.Start:
                    test_name = re.findall('algo/(\S+)\|', msg_['docker'])
                    if not test_name:
                        logger.warning(f'invalid test name {test_name}')
                        continue

                    self.testing_name = test_name[0]  # 获取分割后的最后一部分作为测试名称
                    self.__eval_start_func(connection)

    def start(self, connection: MQTTConnection):
        """运行仿真测评"""
        if config.SetupConfig.await_start_cmd:
            self.loop_start(connection)
        else:
            self.__eval_start_func(connection)


"""测评系统与仿真无关的内容均以事件形式定义(如生成json轨迹文件，发送评分等)，处理事件的函数的入参以关键词参数形式传入，返回值固定为None"""


class EvalEventType(Enum):
    START_EVAL = auto()
    ERROR = auto()
    BEFORE_TASK = auto()
    FINISH_TASK = auto()
    FINISH_EVAL = auto()
    FINISH_ALL_TEST_BATCH = auto()


class EventArgumentError(AttributeError):
    """事件参数未找到错误"""
    pass


eval_event_subscribers: Dict[EvalEventType, list] = defaultdict(list)  # 事件订阅


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


def handle_data_reload_event(*args, **kwargs) -> None:
    implement_counter.reset()  # 重置执行计数器计数
    logger.reset_user_info()

    connection: MQTTConnection = kwargs.get('connection')
    if connection is not None:
        connection.clear_residual_data()


def handle_trajectory_record_event(*args, **kwargs) -> None:
    """
    以json文件形式保存轨迹

    Args:
        *args:
        **kwargs: 1) docker_name: str docker名 2) sub_name: str 子任务的文件名
                  3) traj_record_dir: str 轨迹数据存储路径 4) veh_info: dict 字典

    """

    traj_record_dir = kwargs.get('traj_record_dir', '../data/trajectory')  # 目录暂写死
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
    docker_name = kwargs.get('docker_name', 'test')
    save_dir = '../data/trajectory'

    for junction_id, veh_info in trajectories.items():
        # handle_trajectory_record_event(traj_record_dir=save_dir, veh_info=veh_info)
        handle_trajectory_record_event(traj_record_dir=save_dir, sub_name='_'.join((docker_name, junction_id)),
                                       veh_info=veh_info, **kwargs)

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
        4) eval_record: list
    """
    eval_record_dir = kwargs.get('eval_record_dir', '../data/evaluation')
    docker_name = kwargs.get('docker_name', 'test')

    # eval_record_dir = kwargs.get('eval_record_dir')
    # docker_name = kwargs.get('docker_name')
    all_result = {'score': 0, 'name': docker_name, 'abnormal': 0}
    detail = {'errorTimes': 0, 'detailInfo': [], 'errorInfo': []}
    if implement_counter.valid_implement:
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
    else:
        detail['errorTimes'] = 1
        detail['errorInfo'].append('No valid execution received from Algorithm')

    # deliver user information for unsuccessful execution
    for user_info in logger.pop_user_info():
        detail['errorTimes'] += 1
        detail['errorInfo'].append(user_info)

    all_result['detail'] = detail

    eval_record = kwargs.get('eval_record')
    if eval_record is None:
        # 如果未给定记录集合, 直接通过发布评测结果
        connection = kwargs.get('connection')
        print(f'测试{config.SetupConfig.test_name!r}测评结果: {all_result}')
        connection.publish(PubMsgLabel(all_result, OrderMsg.ScoreReport, 'json'))

    task_name = kwargs.get('task_name', 'default')
    eval_record[task_name] = all_result


def handle_test_batch_complete(*args, **kwargs) -> None:
    docker_name = kwargs.get('docker_name', 'test')
    eval_record: Dict[str, dict] = kwargs.get('eval_record')
    eval_record_dir = kwargs.get('eval_output_path', '../data/output')

    docker_eval_record_dir = os.path.join(eval_record_dir, docker_name)
    if not os.path.exists(docker_eval_record_dir):
        os.mkdir(docker_eval_record_dir)

    if not eval_record:
        return None

    score_res = []
    abnormal_count = 0
    detail = []
    for task_name, single_eval_result in eval_record.items():
        if single_eval_result['score'] == 0:
            abnormal_count += 1
        score_res.append(single_eval_result['score'])
        detail.append(single_eval_result['detail'])
        score_record_name = os.path.join(docker_eval_record_dir, f'{docker_name}_{task_name}.json')
        with open(score_record_name, 'w') as f:
            json.dump(single_eval_result, f, indent=2)
    assemble_res = {
        'score': 0 if abnormal_count else sum(score_res) / len(score_res),
        'name': docker_name,
        'abnormal': abnormal_count,
        'detail': detail
    }

    # clear the dict without influencing the nested data required to report
    eval_record.clear()
    connection = kwargs.get('connection')
    print(f'测试综合测评结果: {assemble_res}')

    connection.publish(PubMsgLabel(assemble_res, OrderMsg.ScoreReport, 'json'))


def initialize_score_prepare():
    """注册评分相关的事件"""
    subscribe_eval_event(EvalEventType.BEFORE_TASK, handle_data_reload_event)
    # subscribe_eval_event(EvalEventType.FINISH_TASK, handle_trajectory_record_event)
    subscribe_eval_event(EvalEventType.FINISH_TASK, handle_multiple_trajectory_record_event)
    subscribe_eval_event(EvalEventType.START_EVAL, handle_eval_apply_event)
    subscribe_eval_event(EvalEventType.FINISH_EVAL, handle_score_report_event)
    subscribe_eval_event(EvalEventType.FINISH_ALL_TEST_BATCH, handle_test_batch_complete)
