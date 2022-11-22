# -*- coding: utf-8 -*-
# @Time        : 2022/11/17 18:01
# @File        : sim_data.py
# @Description : 存放仿真运行环节需要记录的数据

from collections import namedtuple
from dataclasses import dataclass
from abc import abstractmethod
from typing import Tuple, Dict, Callable, Any, Optional, TypeVar, NewType

import sumolib
import traci

from simulation.lib.common import logger
from simulation.lib.public_data import signalized_intersection_name_str
from simulation.information.traffic import Flow
from simulation.application.signal_control import SignalController
from simulation.connection.mqtt import PubMsgLabel

# IntersectionId = NewType('IntersectionId', str)

# TODO: 可以对Task进行任意修改，现版本随便写写的


class BaseTask:
    """
    仿真中需要执行的任务
    """
    def __init__(self, exec_func: Callable, args: tuple = (), kwargs: dict = None, exec_time: Optional[float] = None):
        """

        Args:
            exec_func: 执行的函数
            exec_time: 达到此时间才在仿真中执行函数，None表示立即执行
            args: position 参数
            kwargs: keyword 参数
        """
        self.exec_func = exec_func
        self.args = args
        self.kwargs = kwargs if kwargs is not None else {}
        self.exec_time = exec_time

    def execute(self):
        return self.exec_func(*self.args, **self.kwargs)


class ImplementTask(BaseTask):
    """在仿真中进行控制命令的任务"""
    def execute(self) -> Tuple[bool, Any]:
        """

        Returns: 函数提取后的结果

        """
        success, res = super().execute()
        return success, res


class InfoTask(BaseTask):
    """在仿真中获取信息的任务"""
    def __init__(self, exec_func: Callable, args=(), kwargs=None, exec_time=None, target_topic: str = None):
        super().__init__(exec_func, args=args, kwargs=kwargs, exec_time= exec_time)
        self.target_topic = target_topic  # 如果需要发送信息，确定发送的topic

    def execute(self) -> Tuple[bool, Optional[PubMsgLabel]]:
        """

        Returns: 函数提取后的结果

        """
        success, res = super().execute()
        return success, res


class EvalTask(BaseTask):
    pass


@dataclass
class TransitionIntersection:
    intersection_id: str
    current_phase_index: int


class NaiveSimInfoStorage:
    """针对单点交叉口的运行数据存储"""
    def __init__(self, net):
        self.flow_status = Flow()  # 流量信息存储
        self.signal_controllers = self._initialize_sc(net)  # 信号转换计划

    @staticmethod
    def _initialize_sc(net: sumolib.net.Net):
        SignalController.load_net(net)  # 初始化signal controller的地图信息
        nodes = net.getNodes()
        scs = {}
        for node in nodes:
            node_type = node.getType()
            if node_type != 'traffic_light':
                continue

            tl_node_id = node.getID()
            sc = SignalController(tl_node_id)
            scs[tl_node_id] = sc
        return scs

    def create_signal_update_task(self, signal_scheme: dict) -> Optional[ImplementTask]:
        node = signal_scheme.get('node_id')
        if node is None:
            return None
        node_id = node.get('id')
        if node_id is None:
            return None

        node_name = signalized_intersection_name_str(node_id)
        sc = self.signal_controllers.get(node_name)
        if sc is None:
            logger.info(f'cannot find intersection {node_name} in the network for signal scheme data')
            return None

        updated_logic = sc.create_control_task(signal_scheme)
        if updated_logic is None:
            return None
        exec_time = sc.get_next_cycle_start()
        return ImplementTask(traci.trafficlight.setProgramLogic, args=(sc.tls_id, updated_logic), exec_time=exec_time)

    def reset(self):
        """清空当前保存的运行数据"""
        self.flow_status.clear()


class ArterialSimInfoStorage(NaiveSimInfoStorage):
    """新增干线的运行数据存储"""
    def __init__(self, net):
        super().__init__(net)
        self.transition_status: Dict[str, TransitionIntersection] = {}

    def reset(self):
        """清空当前保存的运行数据"""
        super().reset()
        self.transition_status.clear()

