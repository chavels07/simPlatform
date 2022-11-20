# -*- coding: utf-8 -*-
# @Time        : 2022/11/20 20:01
# @File        : public_data.py
# @Description : 存放不仅用于仿真内部，也可用在其他环节所需的数据结构

from enum import Enum, auto
from typing import TypeVar


class MsgType(Enum):
    pass


class OrderMsg(MsgType):
    # 控制命令
    Start = auto()


class DataMsg(MsgType):
    # 标准数据结构
    SignalScheme = auto()
    SpeedGuide = auto()


class SpecialDataMsg(MsgType):
    # 仿真专用数据结构
    TransitionSS = auto()
    SERequirement = auto()


# MsgType的所有子类，用于类型注解
DetailMsgType = TypeVar('DetailMsgType', bound=MsgType)