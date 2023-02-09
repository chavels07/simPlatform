# -*- coding: utf-8 -*-
# @Time        : 2022/11/18 19:33
# @File        : traffic.py
# @Description : 交通流数据的存储，更新，读取

import string
from typing import Tuple, Callable, Set, Dict, List, Iterable
from warnings import warn

import traci
import traci.constants as tc
import sumolib

from simulation.lib.public_data import (create_TrafficFlowStat, create_TrafficFlow, create_NodeReferenceID, SimStatus,
                                        signalized_intersection_name_decimal)
from simulation.lib.public_conn_data import PubMsgLabel, DataMsg
from simulation.information.participants import VehInfo


# class FlowCounter:
#     def __init__(self, lane_id: str):
#         self.lane_id = lane_id
#         self.flow_storage = 0
#         self.mean_speed = 0.
#         self.last_vehicles_set = set()  # 暂时存储车辆ID, 防止两个相近时间步长检测到同一辆车计数多次
#         self.record_start_time = None
#
#     def reset(self):
#         """重置计数器状态"""
#         self.flow_storage = 0
#         self.record_start_time = None
#
#
# # TODO: traffic flow改为从trajectory里面去读取
# class Flow:
#     def __init__(self):
#         self.flow_counter: Dict[str, FlowCounter] = {}
#         self.detector_location: Dict[str, List[str]] = {}  # 记录检测器与交叉口的关联关系
#
#     def initialize_counter(self, net: sumolib.net.Net, nodes: Set[str] = None):
#         """
#         初始化车辆计数检测器
#         Args:
#             net: 路网信息
#             nodes: 如给定nodes则只更新所选link上的检测器状态和发送TrafficFlow
#
#         Returns:
#
#         """
#         for detector_id in traci.lanearea.getIDList():
#             lane_id = traci.lanearea.getLaneID(detector_id)
#             lane: sumolib.net.lane.Lane = net.getLane(lane_id)
#             edge: sumolib.net.edge.Edge = lane.getEdge()
#             # edge_id = edge.getID()
#             intersection_id = edge.getToNode().getID()
#             if nodes is not None and intersection_id not in nodes:
#                 continue
#
#             # 订阅经过的车辆id,平均速度
#             traci.lanearea.subscribe(detector_id, (tc.LAST_STEP_VEHICLE_ID_LIST, tc.LAST_STEP_MEAN_SPEED))
#             self.flow_counter[detector_id] = FlowCounter(lane_id)
#             self.detector_location.setdefault(intersection_id, []).append(detector_id)
#
#     def update_vehicle_set(self, detector: str):
#         """
#         从检测器数据更新流量信息
#         Args:
#             detector: 检测器id
#         """
#         detector_counter = self.flow_counter[detector]
#         if detector_counter.record_start_time is None:
#             detector_counter.record_start_time = SimStatus.sim_time_stamp
#
#         sub_res = traci.lanearea.getSubscriptionResults(detector)
#         this_step_vehicles = set(sub_res[tc.LAST_STEP_VEHICLE_ID_LIST])
#         new_arrivals = this_step_vehicles - detector_counter.last_vehicles_set
#         detector_counter.flow_storage += len(new_arrivals)
#         # detector_counter.last_vehicles_set = detector_counter.last_vehicles_set | this_step_vehicles
#         detector_counter.last_vehicles_set.update(new_arrivals)
#         detector_counter.mean_speed = sub_res[tc.LAST_STEP_MEAN_SPEED]
#
#     def get_flow(self, detector: str) -> Tuple[int, float]:
#         """
#         流量获取
#         Args:
#             detector: 检测器id
#
#         Returns: 时段内的流量，时段时长
#         """
#         if detector not in self.flow_counter:
#             return -1, -1.
#
#         detector_counter = self.flow_counter[detector]
#         current_timestamp = SimStatus.sim_time_stamp
#         flow_fixed_period = detector_counter.flow_storage
#         period = current_timestamp - detector_counter.record_start_time
#         if period < 1e-4:
#             warn('period is zero, get_flow function was called too often')
#             return -1, -1.
#         detector_counter.reset()  # 重置记录时间和流量记录
#         return flow_fixed_period, period
#
#     def create_traffic_flow_pub_msg(self, intersections: List[str] = None) -> Tuple[bool, PubMsgLabel]:
#         """
#         创建TrafficFlow推送消息，
#         Args:
#             intersections: 推送TF数据的交叉口
#
#         Returns: 推送消息实例
#
#         """
#         tf_msgs = []
#         timestamp = SimStatus.current_real_timestamp()
#         for node_id, detectors_in_node in self.detector_location.items():
#             if intersections is not None and node_id not in intersections:
#                 continue  # 不在所选范围内调过
#             node = create_NodeReferenceID(signalized_intersection_name_decimal(node_id))
#             tf_stats = []
#             period = 0
#             for detector_id in detectors_in_node:
#                 detector = self.flow_counter[detector_id]
#                 flow_fixed_period, period = self.get_flow(detector_id)
#                 if flow_fixed_period < 0:
#                     continue  # 获取流量数据失败
#                 hourly_volume = flow_fixed_period / period * 3600
#                 mean_speed = detector.mean_speed if detector.mean_speed > 0 else 0
#                 tf_stat = create_TrafficFlowStat(map_element=detector.lane_id,
#                                                  ptc_type=1,
#                                                  veh_type="passenger_Vehicle_TypeUnknown",
#                                                  volume=hourly_volume,
#                                                  speed_area=mean_speed)
#                 tf_stats.append(tf_stat)
#             stat_type = {'interval': int(period)}
#             if tf_stats:
#                 traffic_flow = create_TrafficFlow(node=node,
#                                                   gen_time=timestamp,
#                                                   stat_type=stat_type,
#                                                   stat_type_type="DE_TrafficFlowStatByInterval",
#                                                   stats=tf_stats)
#                 tf_msgs.append(traffic_flow)
#
#         return True, PubMsgLabel(tf_msgs, DataMsg.TrafficFlow, convert_method='flatbuffers', multiple=True)
#
#     def flow_update_task(self) -> Callable[[], None]:
#         """创建在每次仿真时更新所有检测器所在路段流量的任务，返回可调用函数"""
#         def wrapper():
#             for detector in self.flow_counter:
#                 self.update_vehicle_set(detector)
#         return wrapper
#
#     def clear(self):
#         """清除检测器的流量记录"""
#         self.flow_counter.clear()


class FlowStopLine:
    _net = None

    def __init__(self, node_id):
        self.node_id = node_id
        self.record_start_time = -1
        self.vehicle_cache: Dict[int, VehInfo] = {}
        self.lane_flow_counter: Dict[str, int] = self.initialize_counter()

    @classmethod
    def load_net(cls, net: sumolib.net.Net):
        """加载JunctionVehContainer的路网"""
        cls._net = net

    def initialize_counter(self):
        """初始化车辆计数检测器"""
        lane_flow_counter = {}
        for edge in self._net.getNode(self.node_id).getIncoming():
            for lane in edge.getLanes():
                lane_id = lane.getID()
                lane_flow_counter[lane_id] = 0
        return lane_flow_counter

    def update_vehicle_cache(self, curr_vehicles: List[VehInfo]):
        if self.record_start_time < 0:
            self.record_start_time = SimStatus.sim_time_stamp

        for veh_info in curr_vehicles:
            veh_id = veh_info.ptcId
            last_step_veh_info = self.vehicle_cache.get(veh_id)
            if last_step_veh_info is None:
                continue

            if self.enter_intersection(veh_info, last_step_veh_info):
                through_lane = last_step_veh_info.lane_id  # 增加counter
                self.lane_flow_counter[through_lane] += 1

        self.vehicle_cache = {veh.ptcId: veh for veh in curr_vehicles}

    @staticmethod
    def enter_intersection(curr_status: VehInfo, last_status: VehInfo):
        # 由于展示交叉口edge命名规则有异于嘉定路网，以edge id规则区分是否进入交叉口
        if curr_status.edge_id.startswith(':') and not set(curr_status.edge_id) & set(string.ascii_letters) and not last_status.edge_id.startswith(':'):
            return True
        else:
            return False

    def get_traffic_flow(self):
        record_end_time = SimStatus.sim_time_stamp
        record_duration_sec = record_end_time - self.record_start_time

        tf_stats = []
        for lane_id, flow in self.lane_flow_counter.items():
            flow_hour = flow / record_duration_sec * 3600
            tf_stat = create_TrafficFlowStat(map_element=lane_id,
                                             ptc_type=1,
                                             veh_type="passenger_Vehicle_TypeUnknown",
                                             volume=flow_hour,
                                             speed_area=0)

            tf_stats.append(tf_stat)
        stat_type = {'interval': int(record_duration_sec)}
        node = create_NodeReferenceID(1)  # int(self.node_id)  TODO:给定的node id数字太大，无法发送，以1代替

        traffic_flow = create_TrafficFlow(node=node,
                                          gen_time=SimStatus.current_real_timestamp(),
                                          stat_type=stat_type,
                                          stat_type_type="DE_TrafficFlowStatByInterval",
                                          stats=tf_stats)
        self.reset()  # 取出TrafficFlow数据后重置状态
        return traffic_flow

    def create_traffic_flow_pub_msg(self) -> Tuple[bool, PubMsgLabel]:
        traffic_flow = self.get_traffic_flow()
        return True, PubMsgLabel(traffic_flow, DataMsg.TrafficFlow, convert_method='flatbuffers')

    def reset(self):
        self.record_start_time = -1
        for lane_id in self.lane_flow_counter.keys():
            self.lane_flow_counter[lane_id] = 0
        self.vehicle_cache.clear()