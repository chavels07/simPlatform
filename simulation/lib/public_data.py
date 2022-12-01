# -*- coding: utf-8 -*-
# @Time        : 2022/11/20 20:01
# @File        : public_data.py
# @Description : 存放不仅用于仿真内部，也可用在其他环节所需的数据结构

import re
from datetime import datetime, timedelta
from typing import Tuple, List, TypeVar, Callable, Any, Optional

from simulation.lib.common import alltypeassert
from simulation.lib.public_conn_data import PubMsgLabel


"""标准数据结构中默认的常量"""
REGION = 1


"""任务类型"""
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

    def __cmp__(self, task):
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
        time_diff = (real_time - cls._real_time_year_begin())
        moy = time_diff.days * 24 * 60 + time_diff.seconds // 60
        return moy

    @classmethod
    def _real_time_year_begin(cls) -> datetime:
        """获得所在年份的第一天，动态添加属性到类避免datetime的重复实例化"""
        attr_name = 'real_time_year_begin'
        cls.running_check()
        res = getattr(cls, attr_name, None)
        if res is None:
            this_year = datetime(cls.start_real_datetime.year, 1, 1)
            setattr(cls, attr_name, this_year)
            cls._dynamic_attributes.append(attr_name)
            res = this_year
        return res


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
def create_SafetyMessage(ptcId: int,
                         moy: int,
                         secMark: int,
                         lat: int,
                         lon: int,
                         x: int,
                         y: int,
                         lane_ref_id: int,
                         speed: int,
                         direction: int,
                         width: int,
                         length: int,
                         classification: str,
                         edge_id: str,
                         lane_id: str,
                         obuId: List[int] = None
                         ):

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
            'lat': int(lat * 10000000),
            'lon': int(lon * 10000000)
        },
        'referPos':{
            'positionX': int(x),
            'positionY': int(y)
        },
        'nodeId':{
            'region': 1,
            'id': 0
        },
        'laneId': lane_ref_id,
        'accuracy':{
            'pos': 'a2m'
        },
        'transmission': 'unavailable',
        'speed': int(speed / 0.02),
        'heading': direction,
        'motionCfd':{
            'speedCfd': 'prec1ms',
            'headingCfd': 'prec0_01deg'
        },
        'size':{
            'width': int(width * 100),
            'length': int(length * 100)
        },
        'vehicleClass':{
            'classification': classification
        },
        'section_ext_id': edge_id,
        'lane_ext_id': lane_id
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
