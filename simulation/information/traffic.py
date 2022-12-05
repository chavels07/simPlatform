# -*- coding: utf-8 -*-
# @Time        : 2022/11/18 19:33
# @File        : traffic.py
# @Description : 交通流数据的存储，更新，读取

from collections import defaultdict
from typing import Tuple, Iterable, Callable, Set, Dict, List
from warnings import warn

import traci
import traci.constants as tc
import sumolib

from simulation.lib.public_data import (create_TrafficFlowStat, create_TrafficFlow, create_NodeReferenceID, SimStatus,
                                        signalized_intersection_name_decimal)
from simulation.lib.public_conn_data import PubMsgLabel, DataMsg
from simulation.lib.common import timer


class FlowCounter:
    def __init__(self, lane_id: str):
        self.lane_id = lane_id
        self.flow_storage = 0
        self.mean_speed = 0.
        self.last_vehicles_set = set()  # 暂时存储车辆ID, 防止两个相近时间步长检测到同一辆车计数多次
        self.record_start_time = None

    def reset(self):
        """重置计数器状态"""
        self.flow_storage = 0
        self.record_start_time = None


class Flow:
    def __init__(self):
        self.flow_counter: Dict[str, FlowCounter] = {}
        self.detector_location: Dict[str, List[str]] = {}  # 记录检测器与交叉口的关联关系

    def initialize_counter(self, net: sumolib.net.Net, links: Set[str] = None):
        """
        初始化车辆计数检测器
        Args:
            net: 路网信息
            links: 如给定links则只更新所选link上的检测器状态和发送TrafficFlow

        Returns:

        """
        filter_flag = True if links is not None else False
        for detector_id in traci.lanearea.getIDList():
            lane_id = traci.lanearea.getLaneID(detector_id)
            lane: sumolib.net.lane.Lane = net.getLane(lane_id)
            edge: sumolib.net.edge.Edge = lane.getEdge()
            edge_id = edge.getID()
            intersection_id = edge.getToNode().getID()
            if filter_flag and edge_id not in links:
                continue

            # 订阅经过的车辆id,平均速度
            traci.lanearea.subscribe(detector_id, (tc.LAST_STEP_VEHICLE_ID_LIST, tc.LAST_STEP_MEAN_SPEED))
            self.flow_counter[detector_id] = FlowCounter(lane_id)
            self.detector_location.setdefault(intersection_id, []).append(detector_id)

    def update_vehicle_set(self, detector: str):
        """
        从检测器数据更新流量信息
        Args:
            detector: 检测器id
        """
        detector_counter = self.flow_counter[detector]
        if detector_counter.record_start_time is None:
            detector_counter.record_start_time = SimStatus.sim_time_stamp

        sub_res = traci.lanearea.getSubscriptionResults(detector)
        this_step_vehicles = set(sub_res[tc.LAST_STEP_VEHICLE_ID_LIST])
        new_arrivals = this_step_vehicles - detector_counter.last_vehicles_set
        detector_counter.flow_storage += len(new_arrivals)
        detector_counter.mean_speed = sub_res[tc.LAST_STEP_MEAN_SPEED]

    def get_flow(self, detector: str) -> Tuple[int, float]:
        """
        流量获取
        Args:
            detector: 检测器id

        Returns: 时段内的流量，时段时长
        """
        if detector not in self.flow_counter:
            return -1, -1.

        detector_counter = self.flow_counter[detector]
        current_timestamp = SimStatus.sim_time_stamp
        flow_fixed_period = detector_counter.flow_storage
        period = current_timestamp - detector_counter.record_start_time
        if period < 1e-4:
            warn('period is zero, get_flow function was called too often')
            return -1, -1.
        detector_counter.reset()  # 重置记录时间和流量记录
        return flow_fixed_period, period

    def create_traffic_flow_pub_msg(self) -> PubMsgLabel:
        """
        创建TrafficFlow推送消息，
        Args:
            *args: 可变长度的需要推送flow信息的Link，若为缺省则则输出所有检测器的交通流集计数据

        Returns: 推送消息实例

        """
        tf_msgs = []
        timestamp = SimStatus.current_real_timestamp()
        for node_id, detectors_in_node in  self.detector_location.items():
            node = create_NodeReferenceID(signalized_intersection_name_decimal(node_id))
            tf_stats = []
            period = 0
            for detector_id in detectors_in_node:
                detector = self.flow_counter[detector_id]
                flow_fixed_period, period = self.get_flow(detector_id)
                if flow_fixed_period < 0:
                    continue  # 获取流量数据失败
                tf_stat = create_TrafficFlowStat(map_element=detector.lane_id,
                                                 ptc_type=1,
                                                 veh_type="passenger_Vehicle_TypeUnknown",
                                                 volume=flow_fixed_period,
                                                 speed_area=detector.mean_speed)
                tf_stats.append(tf_stat)
            stat_type = {'interval': period}
            if tf_stats:
                traffic_flow = create_TrafficFlow(node=node,
                                                  gen_time=timestamp,
                                                  stat_type=stat_type,
                                                  stat_type_type="DE_TrafficFlowStatByInterval",
                                                  stats=tf_stats)
                tf_msgs.append(traffic_flow)

        return PubMsgLabel(tf_msgs, DataMsg.TrafficFlow, convert_method='flatbuffers', multiple=True)

    def flow_update_task(self) -> Callable[[], None]:
        """创建在每次仿真时更新所有检测器所在路段流量的任务，返回可调用函数"""
        def wrapper():
            for detector in self.flow_counter:
                self.update_vehicle_set(detector)
        return wrapper

    def clear(self):
        """清除检测器的流量记录"""
        self.flow_counter.clear()