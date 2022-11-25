# -*- coding: utf-8 -*-
# @Time        : 2022/11/20 20:01
# @File        : public_data.py
# @Description : 存放不仅用于仿真内部，也可用在其他环节所需的数据结构

import re
from enum import Enum, auto
from datetime import datetime
from typing import List, TypeVar

from simulation.lib.common import alltypeassert


class MsgType(Enum):
    pass


class OrderMsg(MsgType):
    # 控制命令
    Start = auto()


class DataMsg(MsgType):
    # 标准数据结构
    SignalScheme = auto()
    SpeedGuide = auto()
    SafetyMessage = auto()


class SpecialDataMsg(MsgType):
    # 仿真专用数据结构
    TransitionSS = auto()
    SERequirement = auto()


DetailMsgType = TypeVar('DetailMsgType', bound=MsgType)  # MsgType的所有子类，用于类型注解

"""标准数据结构中默认的常量"""
REGION = 1


"""标准数据格式构造"""
@alltypeassert
def create_NodeReferenceID(node_id: int,
                           region: int = REGION) -> dict:
    _NodeReferenceID = {
        'region': region,
        'id': node_id
    }
    return _NodeReferenceID


@alltypeassert
def create_Phasic(phase_id: int,
                  order: int,
                  scat_no: str,
                  movements: List[str],
                  green: int,
                  yellow: int,
                  all_red: int,
                  min_green: int,
                  max_green: int) -> dict:
    _Phasic = {
        'id': phase_id,
        'order': order,
        'scat_no': scat_no,
        'movements': movements,
        'green': green,
        'yellow': yellow,
        'allred': all_red,
        'min_green': min_green,
        'max_green': max_green
    }
    return _Phasic


@alltypeassert
def create_SignalScheme(scheme_id: int,
                        node_id: dict,
                        time_span: dict,
                        cycle: int,
                        control_mode: int,
                        min_cycle: int,
                        max_cycle: int,
                        base_signal_scheme_id: int,
                        offset: int,
                        phases: List[dict]) -> dict:
    _SignalScheme = {
        'scheme_id': scheme_id,
        'node_id': node_id,
        'time_span': time_span,
        'cycle': cycle,
        'control_mode': control_mode,
        'min_cycle': min_cycle,
        'max_cycle': max_cycle,
        'base_signal_scheme_id': base_signal_scheme_id,
        'offset': offset,
        'phases': phases
    }
    return _SignalScheme

# create_Phasic(1, 1, '', (), 1, 1, 1, 1, 1)


def create_DateTimeFilter(last_hour: int = 1) -> dict:
    """

    Args:
        last_hour: 持续时间

    Returns:

    """
    now = datetime.now()
    month, day = now.strftime('%b').upper(), now.day
    weekday = now.strftime('%a').upper()
    if weekday == 'THU':
        weekday = 'THUR'  # 修正Thursday
    from_time = {'hh': now.hour, 'mm': now.minute, 'ss': now.second}
    if now.hour < 24 - last_hour:
        to_time = {'hh': now.hour + last_hour, 'mm': now.minute, 'ss': now.second}  # 默认执行一个小时
    else:
        to_time = {'hh': 23, 'mm': 59, 'ss': 59}  # 最后一个小时，信控方案的执行结束时间为当天最后一秒
    _DateTimeFilter = {
        'month_filter': [month],
        'day_filter': [day],
        'weekday_filter': [weekday],
        'from_time_point': from_time,
        'to_time_point': to_time
    }
    return _DateTimeFilter


def create_SafetyMessage(ptcType: int,
                         ptcId: int,
                         moy: int,
                         secMark: int):

    _SafetyMessage = {
        'ptcType': ptcType,
        'ptcId': ptcId,
        'source': 1,
        'device': [1],

    }
    return _SafetyMessage


"""常用方法"""
point_numeric_pat = re.compile(r'point(\d+)')
minus_numeric_pat = re.compile(r'-(\d+)')


def signalized_intersection_name_decimal(ints: str) -> int:
    """
    从交叉口名称字符串提取数字部分
    Args:
        ints: 交叉口名称

    Returns: 交叉口编号

    """
    if ints.startswith('point'):
        ints_num = point_numeric_pat.match(ints).group(1)
    elif ints.startswith('-'):
        ints_num = minus_numeric_pat.match(ints).group(1)
    else:
        raise ValueError(f'unexpected intersection name: {ints}')
    return int(ints_num)


def signalized_intersection_name_str(ints: int) -> str:
    """
     从交叉口的数字标号寻找对应的名称字符串
    Args:
        ints: 交叉口编号

    Returns: 交叉口名称

    """
    pass
