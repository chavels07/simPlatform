# -*- coding: utf-8 -*-
# @Time        : 2022/11/30 21:33
# @File        : public_conn_data.py
# @Description : 通信相关的公共数据

from enum import Enum, auto
from typing import TypeVar, Any


class MsgType(Enum):
    pass


class OrderMsg(MsgType):
    # 控制命令
    Start = auto()
    TFStart = auto()
    ScoreReport = auto()


class DataMsg(MsgType):
    # 标准数据结构
    SignalScheme = auto()
    SignalExecution = auto()
    SpeedGuide = auto()
    SafetyMessage = auto()
    RoadsideSafetyMessage = auto()
    SignalPhaseAndTiming = auto()
    TrafficFlow = auto()


class SpecialDataMsg(MsgType):
    # 仿真专用数据结构
    TransitionSS = auto()
    SERequirement = auto()


DetailMsgType = TypeVar('DetailMsgType', bound=MsgType)  # MsgType的所有子类，用于类型注解

CONVERT_METHOD = ['json', 'flatbuffers', 'raw']


class PubMsgLabel:
    """任意通过MQTT传输的消息均要通过转换成该类"""

    def __init__(self, raw_msg: Any, msg_type: DetailMsgType, convert_method: str, multiple: bool = False):
        """

        Args:
            raw_msg: 消息内容, most likely type: dict
            msg_type: 消息的类型
            convert_method: 发送前需要转换成的数据
            multiple: 消息是否为可迭代的多条消息，当有多条消息需要发送时raw_msg为list需要设为true

        """
        self.raw_msg = raw_msg
        self.msg_type = msg_type
        self.convert_method = convert_method
        self.multiple = multiple

    @property
    def convert_method(self):
        return self._convert_method

    @convert_method.setter
    def convert_method(self, value):
        if not isinstance(value, str) or value not in CONVERT_METHOD:
            raise ValueError(f'given convert method is not defined, allowed value: {",".join(CONVERT_METHOD)}')
        self._convert_method = value
