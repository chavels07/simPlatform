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


class EvalTask(BaseTask):
    pass


@dataclass
class TransitionIntersection:
    intersection_id: str
    current_phase_index: int


class NaiveSimInfoStorage:
    """针对单点交叉口的运行数据存储"""
    def __init__(self):
        self.flow_status = Flow()  # 流量信息存储
        self.signal_update_plan = ...  # 信号转换计划

    def reset(self):
        """清空当前保存的运行数据"""
        self.flow_status.clear()


class ArterialSimInfoStorage(NaiveSimInfoStorage):
    """新增干线的运行数据存储"""
    def __init__(self):
        super().__init__()
        self.transition_status: Dict[str, TransitionIntersection] = {}

    def reset(self):
        """清空当前保存的运行数据"""
        super().reset()
        self.transition_status.clear()

