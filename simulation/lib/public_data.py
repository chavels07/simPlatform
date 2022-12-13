# -*- coding: utf-8 -*-
# @Time        : 2022/11/20 20:01
# @File        : public_data.py
# @Description : 存放不仅用于仿真内部，也可用在其他环节所需的数据结构

import re
import time
import weakref
from datetime import datetime, timedelta
from functools import wraps
from typing import Tuple, List, Dict, TypeVar, Callable, Any, Optional, Union

from simulation.lib.common import alltypeassert
from simulation.lib.public_conn_data import PubMsgLabel

"""标准数据结构中默认的常量"""
REGION = 1

"""任务类型"""


class BaseTask:
    """
    仿真中需要执行的任务
    """

    def __init__(self, exec_func: Callable, args: tuple = (), kwargs: dict = None, exec_time: Optional[float] = None, cycle_time: Optional[float] = None):
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
        self.exec_time = exec_time if cycle_time is None else 0
        self.cycle_time = cycle_time

    def execute(self):
        return self.exec_func(*self.args, **self.kwargs)

    def __lt__(self, task):
        if self.exec_time is None:
            return -1
        return self.exec_time - task.exec_time


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

    def execute(self) -> Tuple[bool, Optional[PubMsgLabel]]:
        """

        Returns: 函数提取后的结果

        """
        success, res = super().execute()
        return success, res


class EvalTask(BaseTask):
    pass


class SimStatus:
    """记录仿真部分状态值，避免重复调用接口或计算"""
    sim_time_stamp: Optional[float] = None  # 仿真运行的内部时间
    start_real_datetime: Optional[datetime] = None  # 仿真开始时运行对应真实世界的时间

    _dynamic_attributes = []  # 记录动态定义的内部使用状态属性(避免污染公共类属性而不去显式声明)

    @classmethod
    def reset(cls):
        """重置仿真的状态"""
        cls.sim_time_stamp = None
        cls.start_real_datetime = None

        # 清除动态添加的属性
        for d_attr in cls._dynamic_attributes:
            delattr(cls, d_attr)

        cls._dynamic_attributes.clear()

    @classmethod
    def time_rolling(cls, curr_timestamp: float):
        """
        更新仿真内部和真实时间
        Args:
            curr_timestamp: 仿真当前的时间

        Returns:

        """
        if cls.start_real_datetime is None:
            cls.start_real_datetime = datetime.now()

        cls.sim_time_stamp = curr_timestamp

    @classmethod
    def running_check(cls) -> None:
        """检查状态信息初始化"""
        if cls.sim_time_stamp is None:
            raise RuntimeError('仿真未初始化运行状态信息，无法提取相应信息')

    @classmethod
    def current_real_time(cls) -> datetime:
        """仿真当前对应的真实世界时间"""
        cls.running_check()
        return cls.start_real_datetime + timedelta(seconds=cls.sim_time_stamp)

    @classmethod
    def current_moy(cls) -> int:
        """获取当前moy"""
        real_time = cls.current_real_time()
        time_diff = (real_time - cls.real_time_year_begin())
        moy = time_diff.days * 24 * 60 + time_diff.seconds // 60
        return moy

    @classmethod
    def current_timestamp_in_minute(cls) -> float:
        """获取当前所在分钟里的秒数"""
        real_time = cls.current_real_time()
        return real_time.second + real_time.microsecond / 1000_000

    @classmethod
    def real_time_year_begin(cls) -> datetime:
        """获得所在年份的第一天，动态添加属性到类避免datetime的重复实例化"""
        attr_name = '_real_time_year_begin'
        cls.running_check()
        res = getattr(cls, attr_name, None)
        if res is None:
            this_year = datetime(cls.start_real_datetime.year, 1, 1)
            setattr(cls, attr_name, this_year)
            cls._dynamic_attributes.append(attr_name)
            res = this_year
        return res

    @classmethod
    def start_real_unix_timestamp(cls):
        cls.running_check()
        attr_name = '_start_real_unix_timestamp'
        res = getattr(cls, attr_name, None)
        if res is None:
            ts = time.mktime(cls.start_real_datetime.timetuple())
            setattr(cls, attr_name, ts)
            cls._dynamic_attributes.append(attr_name)
            res = ts
        return res

    @classmethod
    def current_real_timestamp(cls):
        """获取当前真实时间的时间戳"""
        cls.running_check()
        real_time = cls.current_real_time()
        return real_time.timestamp()

    @classmethod
    def cache_property(cls, func):
        """
        用于在一次仿真步中多次提取的订阅数据，但不想重复调用traci接口或作为类成员变量存储，
        可使用该装饰器装饰一个get subscribe方法，例子参考signal_control.py/SignalController Class/get_subscribe_info Method
        """
        class _Cache:
            def __init__(self, _func):
                self._func = _func
                self.cache_value = weakref.WeakKeyDictionary()

            def __get__(self, instance, owner):
                if instance is None:
                    return self
                if instance not in self.cache_value:
                    self.cache_value[instance] = self._func(instance), cls.sim_time_stamp
                elif cls.sim_time_stamp != self.cache_value[instance][1]:
                    self.cache_value[instance] = self._func(instance), cls.sim_time_stamp  # 适用于无参的function

                return self.cache_value[instance][0]

        return _Cache(func)


"""标准数据格式构造, 传入参数的数据取现实标准单位"""
Num = Union[int, float]


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


@alltypeassert
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


@alltypeassert
def create_TimeCountingDown(start_time: Num,
                            min_end_time: Num,
                            max_end_time: Num,
                            likely_end_time: Num,
                            time_confidence: Num,
                            next_start_time: Num,
                            next_duration: Num):
    """支持int和float输入并做类型检查"""
    start_time = int(start_time * 10)
    min_end_time = int(min_end_time * 10)
    max_end_time = int(max_end_time * 10)
    if min_end_time == 0:
        min_end_time = 1  # 避免为0时出现字段丢失
    if max_end_time == 0:
        max_end_time = 1

    likely_end_time = int(likely_end_time * 10)
    time_confidence = int(time_confidence * 10)
    next_start_time = int(next_start_time * 10)
    next_duration = int(next_duration * 10)

    _TimeCountingDown = {
        'startTime': start_time,
        'minEndTime': min_end_time,
        'maxEndTime': max_end_time,
        'likelyEndTime': likely_end_time,
        'timeConfidence': time_confidence,
        'nextStartTime': next_start_time,
        'nextDuration': next_duration
    }
    return _TimeCountingDown


@alltypeassert
def create_PhaseState(light: int,
                      timing: dict,
                      timing_type: str = 'DF_TimeCountingDown'):
    _PhaseState = {
        'light': light,
        'timing_type': timing_type,
        'timing': timing
    }
    return _PhaseState


@alltypeassert
def create_Phase(phase_id: int,
                 phase_states: List[dict]):
    _Phase = {
        'id': phase_id,
        'phaseStates': phase_states
    }
    return _Phase


@alltypeassert
def create_DF_IntersectionState(intersection_id: dict,
                                status: Dict[str, int],
                                moy: int,
                                timestamp: float,
                                time_confidence: int,
                                phases: List[dict]):
    timestamp = int(timestamp * 1000)
    if timestamp == 0:
        timestamp += 1  # 避免为0时出现字段丢失
    _IntersectionState = {
        'intersectionId': intersection_id,
        'status': status,
        'moy': moy,
        'timeStamp': timestamp,
        'timeConfidence': time_confidence,
        'phases': phases
    }
    return _IntersectionState


@alltypeassert
def create_SignalPhaseAndTiming(moy: int,
                                timestamp: float,
                                name: str,
                                intersections: List[dict]):
    timestamp = int(timestamp * 1000)
    if timestamp == 0:
        timestamp = 1  # 避免为0时出现字段丢失
    _SignalPhaseAndTiming = {
        'moy': moy,
        'timeStamp': timestamp,
        'name': name,
        'intersections': intersections
    }
    return _SignalPhaseAndTiming


@alltypeassert
def create_PhasicExec(phasic_id: int,
                      order: int,
                      movements: List[str],
                      green: Num,
                      yellow: Num,
                      allred: Num):
    _PhasicExec = {
        'phasic_id': phasic_id,
        'order': order,
        'movements': movements,
        'green': int(green),
        'yellow': int(yellow),
        'allred': int(allred)
    }
    return _PhasicExec


@alltypeassert
def create_SignalExecution(node_id: dict,
                           sequence: int,
                           control_mode: int,
                           cycle: Num,
                           base_signal_scheme_id: int,
                           start_time: float,
                           phases: List[dict]):
    _SignalExecution = {
        'node_id': node_id,
        'sequence': sequence,
        'control_mode': control_mode,
        'cycle': cycle,
        'base_signal_scheme_id': base_signal_scheme_id,
        'start_time': int(start_time),
        'phases': phases
    }


# @alltypeassert
# def create_SafetyMessage(ptcId: int,
#                          moy: int,
#                          secMark: float,
#                          lat: int,
#                          lon: int,
#                          x: int,
#                          y: int,
#                          lane_ref_id: int,
#                          speed: int,
#                          direction: int,
#                          width: int,
#                          length: int,
#                          classification: str,
#                          edge_id: str,
#                          lane_id: str,
#                          obuId: List[int] = None
#                          ):
#     secMark = int(secMark * 1000)
#     if secMark == 0:
#         secMark += 1  # 避免为0时字段丢失的问题
#     _SafetyMessage = {
#         'ptcType': 1,
#         'ptcId': ptcId,
#         'obuId': obuId,
#         'source': 1,
#         'device': [1],
#         'moy': moy,
#         'secMark': secMark,
#         'timeConfidence': 'time000002',
#         'pos': {
#             'lat': int(lat * 10000000),
#             'lon': int(lon * 10000000)
#         },
#         'referPos': {
#             'positionX': int(x),
#             'positionY': int(y)
#         },
#         'nodeId': {
#             'region': 1,
#             'id': 0
#         },
#         'laneId': lane_ref_id,
#         'accuracy': {
#             'pos': 'a2m'
#         },
#         'transmission': 'unavailable',
#         'speed': int(speed / 0.02),
#         'heading': direction,
#         'motionCfd': {
#             'speedCfd': 'prec1ms',
#             'headingCfd': 'prec0_01deg'
#         },
#         'size': {
#             'width': int(width * 100),
#             'length': int(length * 100)
#         },
#         'vehicleClass': {
#             'classification': classification
#         },
#         'section_ext_id': edge_id,
#         'lane_ext_id': lane_id
#     }
#     return _SafetyMessage

@alltypeassert
def create_SafetyMessage(ptcId: int,
                         moy: int,
                         secMark: float,
                         lat: float,
                         lon: float,
                         x: float,
                         y: float,
                         node: dict,
                         lane_ref_id: int,
                         speed: float,
                         direction: float,
                         acceleration: float,
                         width: float,
                         length: float,
                         classification: str,
                         edge_id: str,
                         lane_id: str,
                         obuId: List[int] = None):
    secMark = int(secMark * 1000)
    if secMark == 0:
        secMark += 1  # 避免为0时字段丢失的问题
    _SafetyMessage = {
        'ptcType': 1,
        'ptcId': ptcId,
        'obuId': obuId,
        'source': 1,
        'device': [1],
        'moy': moy,
        'secMark': secMark,
        'timeConfidence': 'time000002',
        'pos': {
            'lat': int(lat * 1e7),
            'lon': int(lon * 1e7)
        },
        'referPos': {
            'positionX': int(x),
            'positionY': int(y)
        },
        'nodeId': node,
        'laneId': lane_ref_id,
        'accuracy': {
            'pos': 'a2m'
        },
        'transmission': 'unavailable',
        'speed': int(speed / 0.02),
        'heading': int(direction / 0.0125),
        'motionCfd': {
            'speedCfd': 'prec1ms',
            'headingCfd': 'prec0_01deg'
        },
        'accelSet': {
            "long": int(acceleration / 0.01)
        },
        'size': {
            'width': int(width * 100),
            'length': int(length * 100)
        },
        'vehicleClass': {
            'classification': classification
        },
        'section_ext_id': edge_id,
        'lane_ext_id': lane_id
    }
    return _SafetyMessage


def create_trajectory(ptcId: int,
                      moy: int,
                      secMark: float,
                      lat: float,
                      lon: float,
                      node: str,
                      lane_ref_id: int,
                      speed: float,
                      direction: float,
                      acceleration: float,
                      classification: str,
                      edge_id: str,
                      auto_level: int = 1,
                      auto_status: int = 1):
    secMark = int(secMark * 1000)
    if secMark == 0:
        secMark += 1  # 避免为0时字段丢失的问题
    trajectory = {
        'ptcType': 1,
        'ptcId': ptcId,
        'source': 1,
        'device': [1],
        'moy': moy,
        'secMark': secMark,
        'timeConfidence': 'time000002',
        'pos': {
            'lat': int(lat * 1e7),
            'lon': int(lon * 1e7)
        },
        'laneId': lane_ref_id,
        'speed': int(speed / 0.02),
        'heading': int(direction / 0.0125),
        'accelSet': {
            "long": int(acceleration / 0.01)
        },
        'vehicleClass': {
            'classification': classification
        },
        'junction': node,
        'link': edge_id,
        'turning': 0,
        'autoLevel': auto_level,
        'autoStatus': auto_status
    }
    return trajectory


def create_TrafficFlowStat(map_element: str,
                           ptc_type: int,
                           veh_type: str,
                           volume: int,
                           speed_area: float):
    speed_area = int(speed_area * 100)
    _MapElement = {'ext_id': map_element}
    _TrafficFlowStat = {
        'map_element': _MapElement,
        'map_element_type': 'DE_LaneStatInfo',
        'ptc_type': ptc_type,
        'veh_type': veh_type,
        'volume': volume,
        'speed_area': speed_area
    }  # TrafficFlow暂时只提供流量和区域速度数据
    return _TrafficFlowStat


@alltypeassert
def create_TrafficFlow(node: dict,
                       gen_time: Num,
                       stat_type: dict,
                       stat_type_type: str,
                       stats: List[dict]):
    gen_time = int(gen_time)
    _TrafficFlow = {
        'node': node,
        'gen_time': gen_time,
        'stat_type': stat_type,
        'stat_type_type': stat_type_type,
        'stats': stats
    }
    return _TrafficFlow


"""常用方法"""
POINT_NUMERIC_PAT = re.compile(r'point(\d+)')
MINUS_NUMERIC_PAT = re.compile(r'-(\d+)')


def signalized_intersection_name_decimal(ints: str) -> int:
    """
    从交叉口名称字符串提取数字部分
    Args:
        ints: 交叉口名称

    Returns: 交叉口编号

    """
    if ints.startswith('point'):
        ints_num = POINT_NUMERIC_PAT.match(ints).group(1)
    elif ints.startswith('-'):
        ints_num = MINUS_NUMERIC_PAT.match(ints).group(1)
    else:
        raise ValueError(f'unexpected intersection name: {ints}')
    # return int(ints_num)
    return 10  # Temporary


def signalized_intersection_name_str(ints: int) -> str:
    """
     从交叉口的数字标号寻找对应的名称字符串
    Args:
        ints: 交叉口编号

    Returns: 交叉口名称

    """
    attach_char = '-' if ints // 1000 else 'point'  # 编号小于1000则是信控交叉口，使用point作为前缀
    return attach_char + str(ints)


FLOW_VEH_PAT = re.compile(r'flow(\d+).(\d+)')


def veh_name_from_flow_decimal(veh_id: str) -> int:
    """
    从以Flow作为输入的车辆名称字符串提取数字部分
    Args:
        veh_id: 从SUMO提取的车辆id字符串

    Returns: 车辆数字ID

    Raises: ValueError(数字过大，超过65535)

    Warnings: Flow的id不能超过65, 输入的车辆总数不宜超过1000(500对于Flow65)
    """
    match_res = FLOW_VEH_PAT.match(veh_id)
    flow_id = match_res.group(1)
    veh_in_flow_id = match_res.group(2)
    numeric_veh_id = int(flow_id) * 1000 + int(veh_in_flow_id)
    if numeric_veh_id > 65535:
        raise ValueError('vehicle id exceeds 65535, invalid number')
    return numeric_veh_id
