# -*- coding: utf-8 -*-
# @Time        : 2022/11/19 13:09
# @File        : core.py
# @Description :

import os
import sys
import time

from collections import OrderedDict, defaultdict
from enum import Enum, auto
from functools import partial
from typing import List, Dict, Optional, Callable

from simulation.lib.common import logger, singleton
from simulation.lib.public_data import OrderMsg
from simulation.lib.sim_data import ImplementTask, InfoTask, EvalTask, NaiveSimInfoStorage, ArterialSimInfoStorage
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
        self.net = sumolib.net.readNet(network_fp, withLatestPrograms =True)  # 路网对象化数据
        self.connection = MQTTConnection()  # 通信接口实现数据外部交互
        self.step_limit = None  # 默认限制仿真运行时间, None为无限制
        self.storage = ArterialSimInfoStorage(self.net) if arterial_storage else NaiveSimInfoStorage(self.net)  # 仿真部分数据存储
        self.info_tasks: OrderedDict[int, InfoTask] = OrderedDict()  # TODO:后面还需要实现OD的继承数据结构来保证时间按序排列的
        self.implement_tasks: OrderedDict[int, ImplementTask] = OrderedDict()

    def initialize(self, route_fp: str = None, detector_fp: Optional[str] = None, step_limit: int = None):
        """
        初始化SUMO路网
        Args:
            route_fp: 车辆路径文件路径
            detector_fp: 检测器文件路径
            step_limit: 限制仿真运行时间(s), None为无限制

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
        traci.start(sumoCmd)
        self.step_limit = step_limit

    def connect(self, broker: str, port: int, topics=None):
        """通过MQTT通信完成与服务器的连接"""
        self.connection.connect(broker, port, topics)

    def is_connected(self):
        """通信是否处于连接状态"""
        return self.connection.status

    def run(self, step_len: float = 0):
        """

        Args:
            step_len: 每一步仿真的更新时间间距(s)

        Returns:

        """
        logger.info('仿真开始')
        while traci.simulation.getMinExpectedNumber() >= 0:
            traci.simulationStep(step=step_len)

            current_timestamp = traci.simulation.getTime()

            # 任务池处理
            # 控制下发
            for effect_time, implement_task in self.implement_tasks.items():
                if effect_time > current_timestamp:
                    break  # 如果任务需要执行的时间大于当前仿真时间，提前退出
                success, res = implement_task.execute()  # TODO: 如果控制函数执行后需要在main中修改状态，需要通过返回值传递

            # 读取数据
            for effect_time, info_task in self.info_tasks.items():
                if effect_time > current_timestamp:
                    break  # 如果任务需要执行的时间大于当前仿真时间，提前退出
                success, msg_label = info_task.execute()  # 返回结果: 执行是否成功, 需要发送的消息Optional[PubMsgLabel]
                if msg_label is not None and success:
                    self.connection.publish(msg_label)

            if self.step_limit is not None and current_timestamp > self.step_limit:
                break  # 完成仿真任务提前终止仿真程序

        logger.info('仿真结束')
        self._reset()

    def _reset(self):
        """运行仿真结束后重置仿真状态"""
        self.step_limit = None
        self.storage.reset()
        self.info_tasks.clear()
        self.implement_tasks.clear()


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
    """以json文件形式保存轨迹"""
    pass


def handle_eval_apply_event(*args, **kwargs) -> None:
    """
    执行测评系统获取评分
    Args:
        *args:
        **kwargs: required argument: 1) eval_record: Dict[str, dict], 2) eval_name: str

    Returns:

    """
    eval_record = getattr(kwargs, 'eval_record', None)
    eval_name = getattr(kwargs, 'eval_name', None)
    if eval_record is None:
        raise EventArgumentError('apply score event handling requires key-only argument "eval_record"')
    if eval_name is None:
        raise EventArgumentError('apply score event handling requires key-only argument "eval_name"')

    # 运行测评程序得到eval res
    eval_res = {'score': 100}
    eval_record[eval_name] = eval_res


def handle_score_report_event(*args, **kwargs) -> None:
    """分数上报"""
    pass


def initialize_score_prepare():
    """注册评分相关的事件"""
    subscribe_eval_event(EvalEventType.FINISH_TASK, handle_trajectory_record_event)
    subscribe_eval_event(EvalEventType.FINISH_TASK, handle_eval_apply_event)
    subscribe_eval_event(EvalEventType.FINISH_EVAL, handle_score_report_event)


@singleton
class AlgorithmEval:
    def __init__(self, cfg_fp: str = '../data/network/anting.sumocfg',
                 network_fp: str = '../data/network/anting.net.xml'):
        self.sim = SimCore(cfg_fp, network_fp, arterial_storage=True)
        self.testing_name: str = 'No test'
        self.eval_record: Dict[str, dict] = {}
        self.__eval_start_func: Optional[Callable[[], None]] = None

    def connect(self, broker: str, port: int, topics=None):
        self.sim.connect(broker, port, topics=topics)

    def eval_task_start(self, route_fp: str, detector_fp: Optional[str] = None, step_limit: int = None,
                        step_len: float = 0):
        self.sim.initialize(route_fp, detector_fp, step_limit)
        self.sim.run(step_len)
        emit_eval_event(EvalEventType.FINISH_TASK, sim_core=self.sim, eval_record=self.eval_record)

        traci.close()

    @staticmethod
    def auto_initialize_event():
        initialize_score_prepare()

    def eval_task_from_directory(self, sce_dir_fp: str, detector_fp: Optional[str], *, f_name_startswith: str = None,
                                 step_limit: int = None, step_len: float = 0):
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
            self.eval_task_start(route_fp, detector_fp, step_limit, step_len)

    def eval_mode_setting(self, single_file: bool, *, route_fp: str = None, sce_dir_fp: str = None,
                          detector_fp: Optional[str] = None, **kwargs) -> None:
        """
        调用loop_start前，指定测评时流量文件读取模式
        Args:
            single_file: 是否为单个文件
            route_fp: route文件
            sce_dir_fp: route文件所在文件夹
            detector_fp: 检测器文件
            **kwargs:

        Returns:

        """
        if single_file:
            if route_fp is None:
                raise ValueError('运行单个流量文件时route_fp参数需给定')
            self.__eval_start_func = partial(self.eval_task_start, route_fp=route_fp, detector_fp=detector_fp)
        else:
            if sce_dir_fp is None:
                raise ValueError('运行文件夹下所有流量文件时sce_dir_fp参数需给定')
            self.__eval_start_func = partial(self.eval_task_from_directory, sce_dir_fp=sce_dir_fp, detector_fp=detector_fp, **kwargs)

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
            if recv_msgs is None:
                continue

            for msg_type, msg_ in recv_msgs:
                if msg_type is OrderMsg.Start:
                    self.testing_name = msg_.split(test_name_split)[-1]  # 获取分割后的最后一部分作为测试名称
                    self.__eval_start_func()

