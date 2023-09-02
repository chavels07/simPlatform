# -*- coding: utf-8 -*-
# @Time        : 2022/11/17 17:29
# @File        : signal_control.py
# @Description : 对SUMO运行对象单次控制

from collections import namedtuple
from enum import Enum
from itertools import islice
from typing import Tuple, List, Dict, Optional, Any

import sumolib
import traci
import traci.constants as tc

from simulation.lib.common import logger
from simulation.lib.net_tool import JunctionConns, entry_movement_sorted
from simulation.lib.public_conn_data import PubMsgLabel, DataMsg
from simulation.lib.public_data import (create_Phasic, create_SignalScheme, create_NodeReferenceID,
                                        create_DateTimeFilter, create_TimeCountingDown, create_PhaseState, create_Phase,
                                        create_DF_IntersectionState, create_SignalPhaseAndTiming, create_PhasicExec,
                                        create_SignalExecution, signalized_intersection_name_decimal, ImplementTask,
                                        InfoTask, SimStatus, PhasicValidator)


class TLStatus(Enum):
    RED = 'r'
    YELLOW = 'y'
    GREEN = 'g'

    def lower_name(self):
        return self.name.lower()


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


def get_related_movement_from_state(state: str) -> List[int]:
    """根据sumo中相位的信号状态判断相位对应控制的流向"""
    return [i for i, light in enumerate(state) if light.lower() != 'r']


def get_phase_status(state: str) -> TLStatus:
    """根据sumo中相位的信号状态判断相位对应的放行(灯色)类型"""
    # TODO: 右转常绿如何判断
    if 'y' in state or 'Y' in state:
        return TLStatus.YELLOW  # 黄灯应该有最高优先级，存在右转常绿的情况
    elif 'g' in state or 'G' in state:
        return TLStatus.GREEN
    else:
        return TLStatus.RED


def phase_gather(phases: List[traci.trafficlight.Phase]) -> Tuple[List[EasyPhaseTiming], List[List[int]]]:
    """根据sumo中相位信息转换成按控制车流的相位划分形式"""
    gather_res = []
    index_ptr = None
    state_strings = []
    for phase in phases:
        status = get_phase_status(phase.state)  # 表示各junctionlink的信号放行状态
        if index_ptr is None:
            gather_res.append(EasyPhaseTiming.arbitrary_init(phase.duration, status))
            state_strings.append(get_related_movement_from_state(phase.state))  # 保存放行的信号控制机的关联状态
            index_ptr = 0
            continue
        if status is TLStatus.GREEN:
            gather_res.append(EasyPhaseTiming(green=phase.duration))
            index_ptr += 1  # 出现绿灯时新增一个相位，指针后移一位
            state_strings.append(get_related_movement_from_state(phase.state))
        elif status is TLStatus.YELLOW:
            gather_res[index_ptr].yellow = phase.duration
        elif status is TLStatus.RED:
            gather_res[index_ptr].allred = phase.duration

    # 对于绿灯不是作为phases list首位的情况进行合并处理, 将最先相序的黄灯或全红移动到最后相序的绿灯中
    if not gather_res[0].green_yellow_completed():
        first_item = gather_res.pop(0)
        last_item = gather_res[-1]
        success_flag = last_item.integrate_instance(first_item)
        if not success_flag:
            raise ValueError(
                f'not complete signal timing, cannot integrate together, this: {last_item}, other: {first_item}')

    # 没有all red的情况进行填充
    return [item.all_red_complete() for item in gather_res], state_strings


ConnInfo = namedtuple('ConnInfo', ['turn', 'from_edge'])


class SignalController:
    _net = None

    def __init__(self, ints_id: str):
        self.ints_id = ints_id
        self._ints_tl_mapping_from_connection()  # traffic light id, 交叉口内部连接转向，进口道信息

    @classmethod
    def load_net(cls, net: sumolib.net.Net):
        """加载SignalController的路网"""
        cls._net = net

    def subscribe_info(self):
        """订阅消息"""
        traci.trafficlight.subscribe(self.tls_id, (tc.TL_CURRENT_PROGRAM, tc.TL_CURRENT_PHASE,
                                                   tc.TL_NEXT_SWITCH, tc.TL_COMPLETE_DEFINITION_RYG))

    def _ints_tl_mapping_from_connection(self):
        """
        从connection建立交叉口id和信号灯id的映射，能应对id不直接相当的情况
        Returns: 交叉口信号控制id，connection的信息

        See Also: https://sumo.dlr.de/docs/Simulation/Traffic_Lights.html#defining_signal_groups

        """
        node: sumolib.net.node.Node = self._net.getNode(self.ints_id)
        connections: List[sumolib.net.Connection] = node.getConnections()
        assert len(connections)
        any_connection = connections[0]
        self.tls_id = any_connection.getTLSID()
        self.conn_info = entry_movement_sorted(connections, node)

        # 按照link index排序，此后可以按照edge变化来判断movement
        # connections = sorted(connections, key=lambda x: x.getTLLinkIndex())

        # conn_index_info = {}  # 交叉口连接道路的信息
        #
        #
        # for conn in connections:
        #     link_index = conn.getTLLinkIndex()
        #     from_edge = conn.getFrom()
        #     turn = Turn(conn.getDirection())
        #     conn_index_info[link_index] = ConnInfo(turn=turn, from_edge=from_edge)

    # @SimStatus.cache_property  # 似乎使用速度会慢一些
    def get_subscribe_info(self) -> Dict[int, Any]:
        """获取traffic light订阅的数据，通过traci.constant获取字典内的数据"""
        return traci.trafficlight.getSubscriptionResults(self.tls_id)

    def get_current_signal_scheme(self) -> dict:
        """获取当前交叉口的信号控制方案"""
        sub_info = self.get_subscribe_info()
        current_program_id = sub_info[tc.TL_CURRENT_PROGRAM]
        curr_logic = self.get_current_logic()
        local_phases: List[traci.trafficlight.Phase] = curr_logic.getPhases()
        gather_phases, movements = phase_gather(local_phases)  # 按照相位传统定义(车流控制)从SUMO中的相位中进行集合转换处理
        assert len(gather_phases) == len(movements), \
            f'phase count is not equivalent to movement group count in intersection {self.ints_id}'

        offset = traci.trafficlight.getParameter(self.tls_id, 'offset')
        phases = []
        cycle_length = 0
        for index, (timing, mov) in enumerate(zip(gather_phases, movements), start=1):
            phasic_res = create_Phasic(phase_id=index,
                                       order=index,
                                       scat_no='',
                                       movements=[str(item) for item in mov],
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
                                            offset=offset,
                                            phases=phases)
        return signal_scheme

    def get_current_signal_execution(self) -> dict:
        """获取当前交叉口执行的信号控制方案, 建议使用signal execution而不是signal scheme"""
        current_program_id = self.get_subscribe_info()[tc.TL_CURRENT_PROGRAM]
        curr_logic = self.get_current_logic()
        local_phases: List[traci.trafficlight.Phase] = curr_logic.getPhases()
        gather_phases, movements = phase_gather(local_phases)  # 按照相位传统定义(车流控制)从SUMO中的相位中进行集合转换处理
        assert len(gather_phases) == len(movements), \
            f'phase count is not equivalent to movement group count in intersection {self.ints_id}'

        cycle_length = 0
        phases = []
        for index, (timing, mov) in enumerate(zip(gather_phases, movements), start=1):

            phasic_exec = create_PhasicExec(phasic_id=index,
                                            order=index,
                                            movements=self.conn_info.get_connections_movements_str(mov),
                                            green=timing.green,
                                            yellow=timing.yellow,
                                            allred=timing.allred)  # TODO: movement怎么和MAP对应，可以按照东西南北的逻辑，但是MAP对不对得齐需要确认
            phases.append(phasic_exec)
            cycle_length += timing.time_sum

        node_id = create_NodeReferenceID(signalized_intersection_name_decimal(self.ints_id))
        signal_execution = create_SignalExecution(node_id=node_id,
                                                  sequence=0,
                                                  control_mode=0,
                                                  cycle=cycle_length,
                                                  base_signal_scheme_id=int(current_program_id),
                                                  start_time=SimStatus.start_real_unix_timestamp(),
                                                  phases=phases)
        return signal_execution

    def get_phases_time_countdown(self) -> Tuple[List[dict], List[int]]:
        """
        获取交叉口所有相位的时间倒计时
        Returns: 1) 各相位time countdown 结构数据 2) 各相位信号灯状态对应的枚举值，参考数据结构中的LightState

        """
        subscribe_info = self.get_subscribe_info()
        curr_logic = self.get_current_logic()
        local_phases: List[traci.trafficlight.Phase] = curr_logic.getPhases()  # TODO: check index从0还是还是1开始
        current_phase_index = subscribe_info[tc.TL_CURRENT_PHASE]
        next_switch_time = subscribe_info[tc.TL_NEXT_SWITCH]  # absolute simulation time
        cycle_length = sum(phase.duration for phase in local_phases)

        timing, lights = [], []
        yellow_insert_index = None  # 灯色为黄灯单独修改灯色
        for phase_index, phase in enumerate(local_phases):
            status = get_phase_status(phase.state)
            if status is not TLStatus.GREEN:
                if phase_index == current_phase_index and status is TLStatus.YELLOW:
                    # 处理绿灯不是第一个周期的情况，插入index为-1时修改lights最后一位，对应最后一个相位
                    yellow_insert_index = len(lights) - 1
                continue

            # 当前为绿灯周期
            if phase_index == current_phase_index:
                start_time = 0
                likely_end_time = next_switch_time - SimStatus.sim_time_stamp
                next_start_time = cycle_length - (phase.duration - likely_end_time)
                light_state_val = 6  # protected movement allowed(green)
            elif phase_index > current_phase_index:
                # assert phase_index - current_phase_index > 1
                start_time = sum(local_phases[_index].duration for _index in
                                 range(current_phase_index + 1, phase_index)) + next_switch_time
                likely_end_time = start_time + phase.duration
                next_start_time = start_time + cycle_length
                light_state_val = 3  # stopAndRemain(red)
            else:
                # assert current_phase_index - phase_index > 1
                start_time = cycle_length - (sum(local_phases[_index].duration
                                                 for _index in range(phase_index, current_phase_index))
                                             + phase.duration - next_switch_time)
                likely_end_time = start_time + phase.duration
                next_start_time = start_time + cycle_length
                light_state_val = 3

            delta_min = phase.minDur - phase.duration
            delta_max = phase.maxDur - phase.duration
            min_end_time = likely_end_time + delta_min
            max_end_time = likely_end_time + delta_max
            next_duration = phase.duration  # 假设信控方案不变化

            lights.append(light_state_val)
            timing.append(create_TimeCountingDown(start_time=start_time,
                                                  min_end_time=min_end_time,
                                                  max_end_time=max_end_time,
                                                  likely_end_time=likely_end_time,
                                                  time_confidence=0,
                                                  next_start_time=next_start_time,
                                                  next_duration=next_duration))
        if yellow_insert_index is not None:
            lights[yellow_insert_index] = 7  # intersectionClearance(yellow)
        return timing, lights

    def get_current_spat(self) -> dict:
        """获取当前交叉口的SPAT消息"""
        timings, lights = self.get_phases_time_countdown()
        phase_states = [create_PhaseState(light=light, timing=time_countdown) for time_countdown, light in
                        zip(timings, lights)]
        phases = [create_Phase(phase_id=index, phase_states=[item]) for index, item in enumerate(phase_states, start=1)]

        node_id = create_NodeReferenceID(signalized_intersection_name_decimal(self.ints_id))
        intersection_status_object = {'status': 5}  # fix timing
        moy = SimStatus.current_moy()
        timestamp = SimStatus.current_timestamp_in_minute()
        intersection_state = create_DF_IntersectionState(intersection_id=node_id,
                                                         status=intersection_status_object,
                                                         moy=moy,
                                                         timestamp=timestamp,
                                                         time_confidence=0,
                                                         phases=phases)
        spat = create_SignalPhaseAndTiming(moy=moy,
                                           timestamp=timestamp,
                                           name=self.tls_id,
                                           intersections=[intersection_state])
        return spat

    def create_spat_pub_msg(self) -> Tuple[bool, PubMsgLabel]:
        """创建SPAT推送消息"""
        newly_spat = self.get_current_spat()
        return True, PubMsgLabel(newly_spat, DataMsg.SignalPhaseAndTiming, convert_method='flatbuffers')

    def create_signal_scheme_pub_msg(self) -> Tuple[bool, PubMsgLabel]:
        """
        创建signal scheme推送消息
        推送当前信控方案应当用signal execution, 现临时使用signal scheme
        Returns:

        """
        current_ss = self.get_current_signal_scheme()
        return True, PubMsgLabel(current_ss, DataMsg.SignalScheme, convert_method='flatbuffers')

    def create_signal_execution_pub_msg(self) -> Tuple[bool, PubMsgLabel]:
        current_se = self.get_current_signal_execution()
        return True, PubMsgLabel(current_se, DataMsg.SignalExecution, convert_method='flatbuffers')

    def get_current_logic(self) -> traci.trafficlight.Logic:
        subscribe_info = self.get_subscribe_info()
        all_programs: List[traci.trafficlight.Logic] = subscribe_info[tc.TL_COMPLETE_DEFINITION_RYG]
        current_program_id = subscribe_info[tc.TL_CURRENT_PROGRAM]
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
        subscribe_info = self.get_subscribe_info()
        curr_phase = subscribe_info[tc.TL_CURRENT_PHASE]
        phases: List[traci.trafficlight.Phase] = self.get_current_logic().getPhases()
        next_start_time = subscribe_info[tc.TL_NEXT_SWITCH] - curr_time
        # 处于最后一个相位，直接返回
        if curr_phase == len(phases) - 1:
            return next_start_time

        # 加上剩余的相位持续时间
        for phase in islice(phases, curr_phase + 1, None):
            next_start_time += phase.duration

        return next_start_time

    def create_control_task(self, signal_scheme: dict) -> Optional[ImplementTask]:
        """
        创建更新信号配时方案任务
        Args:
            signal_scheme: 信号配时数据

        Returns: 执行方案任务，None表示无任务生成

        """
        phases: List[dict] = signal_scheme.get('phases')
        if phases is None or not len(phases):
            logger.info('invalid signal scheme without phases argument, cannot create control')
            return None

        updated_phases_list = []
        phases.sort(key=lambda x: x['order'] if 'order' in x else 0)  # 按order排序，若无order则不变排序

        # Note: 允许空的Movement
        # has_movements = all('movements' in phase for phase in phases)  # 判断是否存在movements字段，否则在当前相位相序和流向基础上更新参数
        # if not has_movements:
        #     current_logic = self.get_current_logic()
        #     phase_len = len(phases)
        #     phase_light_spilt_len = len(current_logic.getPhases())  # SUMO内划分了灯色的相位
        #     if phase_light_spilt_len % phase_len != 0:
        #         logger.info('phase count does not match current traffic light,  cannot create control')
        #         return None  # SUMO中相位数无法被signalscheme相位数整除，则不能实现分配
        #     light_count_per_phase = phase_light_spilt_len // phase_len
        #     light_display_order = ['green', 'yellow', 'allred']
        #
        #     for phase_index, phase in enumerate(phases):
        #         green = phase.get('green')
        #         yellow = phase.get('yellow')
        #         if green is None or yellow is None:
        #             logger.info('green or yellow argument missed, cannot create control')
        #             return None
        #
        #         # movements字段为空时，直接使用当前connection控制组合
        #         for light_index in range(light_count_per_phase):
        #             phase_light_spilt_index = phase_index * light_count_per_phase + light_index
        #             duration = getattr(phase, light_display_order[light_index], 0)  # 按灯色依次读取时间
        #             this_phase = current_logic.getPhases()[phase_light_spilt_index]
        #             this_phase.duration = duration
        #     updated_logic = current_logic
        # else:
        #     for phase in phases:
        #         movements = phase.get('movements')
        #         green = phase.get('green')
        #         yellow = phase.get('yellow')
        #         if green is None or yellow is None:
        #             logger.info('green or yellow argument missed, cannot create control')
        #             return None
        #
        #         connection_indexes = []
        #         for movement in movements:
        #             if not movement.isnumeric():
        #                 logger.info(f'movement {movement} is not defined in intersection {self.ints_id}')
        #             conn_res = self.conn_info.get_movement_connections(int(movement))
        #             if conn_res is None:
        #                 logger.warn(f'Movement {movement} not in junction {self.ints_id}')
        #                 continue
        #             connection_indexes.extend(conn_res)
        #         print(connection_indexes)
        #
        #         # connection和TLS的编号规则有差异，前者是从1开始后者从0开始
        #         green_state = ''.join(
        #             TLStatus.GREEN.value if index in connection_indexes else TLStatus.RED.value for index in
        #             range(len(self.conn_info)))
        #         yellow_state = ''.join(
        #             TLStatus.YELLOW.value if index in connection_indexes else TLStatus.RED.value for index in
        #             range(len(self.conn_info)))
        #         updated_phases_list.append(traci.trafficlight.Phase(green, green_state))
        #         updated_phases_list.append(traci.trafficlight.Phase(yellow, yellow_state))
        #         all_red = phase.get('allred')
        #         if all_red:
        #             all_red_state = 'r' * len(self.conn_info)
        #             updated_phases_list.append(traci.trafficlight.Phase(all_red, all_red_state))
        #
        #     new_program_id = int(self.get_subscribe_info()[tc.TL_CURRENT_PROGRAM]) + 1
        #     updated_logic = traci.trafficlight.Logic(str(new_program_id), 0, 0, phases=updated_phases_list)

        # 不允许空的Movement, 使用Pydantic做校验
        for phase in phases:
            PhasicValidator.model_validate(phase, context={'valid_movements': self.conn_info.valid_sumo_MAP_movement_ext_id()})
            movements = phase.get('movements')
            green = phase.get('green')
            yellow = phase.get('yellow')
            if green is None or yellow is None:
                logger.info('green or yellow argument missed, cannot create control')
                return None

            connection_indexes = []
            for movement in movements:
                if not movement.isnumeric():
                    logger.info(f'movement {movement} is not defined in intersection {self.ints_id}')
                conn_res = self.conn_info.get_movement_connections(int(movement))
                if conn_res is None:
                    logger.warn(f'Movement {movement} not in junction {self.ints_id}')
                    continue
                connection_indexes.extend(conn_res)
            print(connection_indexes)

            # connection和TLS的编号规则有差异，前者是从1开始后者从0开始
            green_state = ''.join(
                TLStatus.GREEN.value if index in connection_indexes else TLStatus.RED.value for index in
                range(len(self.conn_info)))
            yellow_state = ''.join(
                TLStatus.YELLOW.value if index in connection_indexes else TLStatus.RED.value for index in
                range(len(self.conn_info)))
            updated_phases_list.append(traci.trafficlight.Phase(green, green_state))
            updated_phases_list.append(traci.trafficlight.Phase(yellow, yellow_state))
            all_red = phase.get('allred')
            if all_red:
                all_red_state = 'r' * len(self.conn_info)
                updated_phases_list.append(traci.trafficlight.Phase(all_red, all_red_state))

        new_program_id = int(self.get_subscribe_info()[tc.TL_CURRENT_PROGRAM]) + 1
        updated_logic = traci.trafficlight.Logic(str(new_program_id), 0, 0, phases=updated_phases_list)

        exec_time = self.get_next_cycle_start() + SimStatus.sim_time_stamp
        logger.info(f'signal update task of junction {self.ints_id} created')
        return ImplementTask(self._inner_set_program_logic, args=(self.tls_id, updated_logic), exec_time=exec_time)

    @staticmethod
    def _inner_set_program_logic(tls_id, updated_logic):
        traci.trafficlight.setProgramLogic(tls_id, updated_logic)
        return True, None
