# -*- coding: utf-8 -*-
# @Time        : 2022/11/17 17:29
# @File        : control.py
# @Description : 对SUMO运行对象单次控制

from collections import namedtuple
from enum import Enum
from itertools import islice
from typing import Tuple, List, Dict

import sumolib
import traci

from simulation.lib.common import logger
from simulation.lib.public_data import (create_Phasic, create_SignalScheme, create_NodeReferenceID,
                                        create_DateTimeFilter,
                                        signalized_intersection_name_decimal)


class TLStatus(Enum):
    RED = 'r'
    YELLOW = 'y'
    YELLOW = 'Y'
    GREEN = 'g'
    GREEN = 'G'

    def lower_name(self):
        return self.name.lower()


class Turn(Enum):
    STRAIGHT = 's'
    LEFT = 'l'
    RIGHT = 'r'
    TURN = 't'
    PARTIALLY_LEFT = 'L'
    PARTIALLY_RIGHT = 'R'


class EasyPhaseTiming:
    def __init__(self, green: int = None, yellow: int = None, allred: int = None):
        self.green = green
        self.yellow = yellow
        self.allred = allred

    @classmethod
    def arbitrary_init(cls, interval: int, status: TLStatus) -> 'EasyPhaseTiming':
        """
        允许从任意一个灯态开始对信号配时进行初始化
        Args:
            interval: 持续时间
            status: 灯色

        Returns: PhaseTiming实例

        """
        return cls(**{status.lower_name(): interval})

    def green_yellow_completed(self) -> bool:
        """绿灯和黄灯是否被赋值"""
        return self.green is not None and self.yellow is not None

    def integrate_instance(self, other: 'EasyPhaseTiming') -> bool:
        """
        从另一个timing实例合成填补当前的实例
        Args:
            other: cls instance

        Returns: 合成是否成功，另一个实例也缺少该数据时失败

        """
        if self.green is None:
            if other.green is None:
                return False
            self.green = other.green
        elif self.yellow is None:
            if other.yellow is None:
                return False
            self.yellow = other.yellow

        if self.allred is None and other.allred is not None:
            self.allred = other.allred

        return True

    def all_red_complete(self) -> 'EasyPhaseTiming':
        if self.allred is None:
            self.allred = 0
        return self

    @property
    def time_sum(self):
        return self.green + self.allred + self.yellow


def get_tl_status(state: str) -> TLStatus:
    """从sumo中的str类型信号状态转成枚举类型"""
    if state == 'r' or state == 'R':
        return TLStatus.RED
    elif state == 'y' or state == 'Y':
        return TLStatus.YELLOW
    elif state == 'g' or state == 'G':
        return TLStatus.GREEN
    else:
        return TLStatus.UNKNOWN


def get_movement_from_state(state: str) -> List[int]:
    pass


def get_phase_status(state: str) -> TLStatus:
    """根据sumo中相位的信号状态判断相位对应的放行(灯色)类型"""
    if 'g' in state or 'G' in state:
        return TLStatus.GREEN
    elif 'y' in state or 'Y' in state:
        return TLStatus.YELLOW
    else:
        return TLStatus.RED


def phase_gather(phases: List[traci.trafficlight.Phase]) -> List[EasyPhaseTiming]:
    """根据sumo中相位信息转换成按控制车流的相位划分形式"""
    gather_res = []
    green_flag = False
    index_ptr = None
    for phase in phases:
        status = get_phase_status(phase.state)  # 表示各junctionlink的信号放行状态
        if index_ptr is None:
            gather_res.append(EasyPhaseTiming.arbitrary_init(phase.duration, status))
            index_ptr = 0
            continue
        if status is TLStatus.GREEN:
            gather_res.append(EasyPhaseTiming(green=phase.duration))
            index_ptr += 1  # 出现绿灯时新增一个相位，指针后移一位
        elif status is TLStatus.YELLOW:
            gather_res[index_ptr].yellow = phase.duration
        elif status is TLStatus.RED:
            gather_res[index_ptr].allred = phase.duration

    # 对于绿灯不是作为phases list首位的情况进行合并处理
    if not gather_res[0].green_yellow_completed():
        first_item = gather_res.pop(0)
        last_item = gather_res[-1]
        success_flag = last_item.integrate_instance(first_item)
        if not success_flag:
            raise ValueError(
                f'not complete signal timing, cannot integrate together, this: {last_item}, other: {first_item}')

    # 没有all red的情况进行填充
    return [item.all_red_complete() for item in gather_res]


ConnInfo = namedtuple('ConnInfo', ['turn', 'from_edge'])


class SignalController:
    _net = None

    def __init__(self, ints_id: str, sim_instance: ...):
        self.ints_id = ints_id
        self.tls_id, self.conn_info = self.__ints_tl_mapping_from_connection()  # traffic light id, 交叉口内部连接转向，进口道信息
        # self.tls_controller: sumolib.net.TLS = self._net.getTLS(self.tls_id)

    @classmethod
    def load_net(cls, net: sumolib.net.Net):
        """加载SignalController的路网"""
        cls._net = net

    def __ints_tl_mapping_from_connection(self) -> Tuple[str, Dict[int, ConnInfo]]:
        """从connection建立交叉口id和信号灯id的映射，能应对id不直接相当的情况"""
        node: sumolib.net.node.Node = self._net.getNode(self.ints_id)
        connections: List[sumolib.net.Connection] = node.getConnections()
        assert len(connections)
        any_connection = connections[0]
        tls_id = any_connection.getTLSID()

        conn_info = {}
        for conn in connections:
            link_index = conn.getTLLinkIndex()
            from_edge = conn.getFrom()
            turn = Turn(conn.getDirection())
            conn_info[link_index] = ConnInfo(turn=turn, from_edge=from_edge)
        return tls_id, conn_info

    def get_current_signal_program(self) -> dict:
        """获取当前交叉口的信号控制方案"""
        current_program_id = traci.trafficlight.getProgram(self.tls_id)
        curr_logic = self.get_current_logic()
        local_phases: List[traci.trafficlight.Phase] = curr_logic.getPhases()
        gather_phases = phase_gather(local_phases)  # 按照相位传统定义(车流控制)从SUMO中的相位中进行集合转换处理
        phases = []
        cycle_length = 0
        for index, timing in enumerate(gather_phases, start=1):
            phasic_res = create_Phasic(phase_id=index,
                                       order=index,
                                       scat_no='',
                                       movements=...,
                                       green=timing.green,
                                       yellow=timing.yellow,
                                       all_red=timing.allred,
                                       min_green=timing.green,
                                       max_green=timing.green)
            phases.append(phasic_res)
            cycle_length += timing.time_sum

        node_id = create_NodeReferenceID(signalized_intersection_name_decimal(self.ints_id))
        time_span = create_DateTimeFilter()
        signal_scheme = create_SignalScheme(scheme_id=current_program_id,
                                            node_id=node_id,
                                            time_span=time_span,
                                            cycle=cycle_length,
                                            control_mode=0,
                                            min_cycle=cycle_length,
                                            max_cycle=cycle_length,
                                            base_signal_scheme_id=current_program_id,
                                            offset=0,
                                            phases=phases)  # TODO: offset
        return signal_scheme

    def get_current_logic(self) -> traci.trafficlight.Logic:
        all_programs: List[traci.trafficlight.Logic] = traci.trafficlight.getAllProgramLogics(self.tls_id)
        current_program_id = traci.trafficlight.getProgram(self.tls_id)
        if len(all_programs) == 1:
            curr_logic = all_programs[0]
        elif len(all_programs) == 0:
            raise RuntimeError(f'no traffic light program for intersection {self.ints_id}')
        else:
            for _program in all_programs:
                if _program.getSubID() == current_program_id:
                    curr_logic = _program
                    break
            else:
                raise RuntimeError(f'no traffic light program for intersection {self.ints_id} '
                                   f'matching program id {current_program_id}')
        return curr_logic

    def get_next_cycle_start(self) -> float:
        """获取交叉口信号进入下一个周期的时间点"""
        curr_time = traci.simulation.getTime()
        curr_phase = traci.trafficlight.getPhase(self.tls_id)
        phases: List[traci.trafficlight.Phase] = self.get_current_logic().getPhases()
        next_start_time = curr_time + traci.trafficlight.getNextSwitch(self.tls_id)
        # 处于最后一个相位，直接返回
        if curr_phase == len(phases) - 1:
            return next_start_time

        # 加上剩余的相位持续时间
        for phase in islice(phases, curr_phase + 1, None):
            next_start_time += phase.duration

        return next_start_time

    def create_control_task(self, signal_scheme: dict):
        phases: List[dict] = signal_scheme.get('phases')
        if phases is None or not len(phases):
            logger.info('invalid signal scheme without phases argument, cannot create control')
            return None

        updated_phases_list = []
        phases.sort(key=lambda x: x['order'] if 'order' in x else 0)  # 按order排序，若无order则不变排序
        for phase in phases:
            movements = phase.get('movements')
            green = phase.get('green')
            yellow = phase.get('yellow')
            if green is None or yellow is None:
                logger.info('green or yellow argument missed, cannot create control')
                return None
            # movements字段为空时，直接使用当前connection控制组合
            if movements is None:
                pass
            else:
                movement_indexes = []
                for movement in movements:
                    if not movement.isnumeric() or int(movement) not in self.conn_info:
                        logger.info(f'movement {movement} is not defined in intersection {self.ints_id}')

                    movement_indexes.append(int(movement))
                # TODO: 检查link index 开始命名编号
                green_state = ''.join(
                    TLStatus.GREEN.name if index in movement_indexes else TLStatus.RED.name for index in
                    range(len(self.conn_info)))
                yellow_state = ''.join(
                    TLStatus.YELLOW.name if index in movement_indexes else TLStatus.RED.name for index in
                    range(len(self.conn_info)))


            updated_phases_list.append(traci.trafficlight.Phase(green, green_state))
            updated_phases_list.append(traci.trafficlight.Phase(yellow, yellow_state))
            all_red = phase.get('allred')
            if all_red:
                all_red_state = 'r' * len(self.conn_info)
                updated_phases_list.append(traci.trafficlight.Phase(all_red, all_red_state))

        new_program_id = traci.trafficlight.getProgram(self.tls_id) + 1
        updated_logic = traci.trafficlight.Logic(new_program_id, 1, 0, phases=updated_phases_list)



