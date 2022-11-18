# -*- coding: utf-8 -*-
# @Time        : 2022/11/17 18:01
# @File        : sim_data.py
# @Description : 存放仿真运行环节需要记录的数据

from collections import namedtuple
from dataclasses import dataclass
from abc import abstractmethod

from typing import Tuple, Dict, Callable, Any, Optional, TypeVar, NewType

from simulation.information.traffic import Flow
from simulation.connection.mqtt import PubMsgLabel

_MsgProperty = namedtuple('MsgProperty', ['topic_name', 'fb_code'])
MSG_TYPE = {
    # 订阅
    'SignalScheme': _MsgProperty('MECUpload/1/SignalScheme', 0x24),
    'SpeedGuide': _MsgProperty('MECUpload/1/SpeedGuide', 0x34),

    # 自定义数据结构，通过json直接传递，None表示无需转换fb
    'Start': _MsgProperty('MECUpload/1/Start', None),  # 仿真开始
    'TransitionSS': _MsgProperty('MECUpload/1/TransitionSignalScheme', None),  # 过渡周期信控方案
    'SERequirement': _MsgProperty('MECUpload/1/SignalExecutionRequirement', None)  # 请求发送当前执行的信控方案

    # 发布

}

# IntersectionId = NewType('IntersectionId', str)

# TODO: 可以对Task进行任意修改，现版本随便写写的


class BaseTask:
    """
    仿真中需要执行的任务
    """
    def __init__(self, exec_func: Callable, time_effect=None, args=(), kwargs=None):
        self.exec_func = exec_func
        self.args = args
        self.kwargs = kwargs
        self.time_effect = time_effect

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
    def __init__(self, exec_func: Callable, time_effect=None, args=(), kwargs=None, target_topic: str = None):
        super().__init__(exec_func, time_effect, args, kwargs)
        self.target_topic = target_topic  # 如果需要发送信息，确定发送的topic

    def execute(self) -> Tuple[bool, Optional[PubMsgLabel]]:
        """

        Returns: 函数提取后的结果

        """
        success, res = super().execute()
        return success, res


@dataclass
class TransitionIntersection:
    intersection_id: str
    current_phase_index: int


class NaiveSimInfoStorage:
    """针对单点交叉口的运行数据存储"""
    def __init__(self):
        self.flow_status = Flow()  # 流量信息存储
        self.signal_update_plan = ...  # 信号转换计划


class ArterialSimInfoStorage(NaiveSimInfoStorage):
    """新增干线工嗯呢该的运行数据存储"""
    def __init__(self):
        super().__init__()
        self.transition_status: Dict[str, TransitionIntersection] = {}

