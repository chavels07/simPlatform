# -*- coding: utf-8 -*-
# @Time        : 2022/11/17 18:00
# @File        : participants.py
# @Description : 交通参与者信息提取

import string
from dataclasses import dataclass
from typing import Tuple, List, Dict, Optional

import traci
import traci.constants as tc
import sumolib

from simulation.lib.public_data import (create_SafetyMessage, create_RoadsideSafetyMessage, create_ParticipantData,
                                        create_NodeReferenceID, create_BSM_Baidu,
                                        create_trajectory, SimStatus, veh_name_from_flow_decimal,
                                        signalized_intersection_name_decimal)
from simulation.lib.public_conn_data import DataMsg, PubMsgLabel


# Jia Zuoning
# def get_vehicle_info(net: str) -> List[dict]:
#     """
#     获取车辆消息
#     Args:
#         net: 路网文件
#     Returns:
#         所有车辆bsm
#     """
#     vehicles_list = traci.vehicle.getIDList()  # 获取当前路网中所有车辆
#     vehicles_info = []  # 创建bsm list
#
#     # 从SimStatus中读数据
#     moy = SimStatus.current_moy()
#     timeStamp = SimStatus.current_timestamp_in_minute()
#
#     for veh_id in vehicles_list:
#         vehicle = VehInfo(veh_id, net)  # 创建车辆实例
#         vlane = vehicle.getLane()
#         vclass = vehicle.veh_class
#         vlength, vwidth, vheight = vehicle.getVehSize()
#         vspeed = vehicle.getSpeed()
#         vaccel = vehicle.getAcceleration()
#         vdirection = vehicle.getdirection()
#         x, y = vehicle.getXY4veh()
#         lon, lat = vehicle.getLonLat4veh()
#         obu_id = vehicle.getObuid()
#
#         vid_num = veh_id.split('.')[-1]  # 提取sumo的到的车辆id中数字部分
#
#         if vlane != '' and 'point' not in vlane:  # 交叉口内部
#             lane_obj = vehicle.net.getLane(vlane)
#             lane_num = len(lane_obj.getEdge().getLanes())
#             lane_index = int(lane_obj.getIndex())
#             edge_id = lane_obj.getEdge().getID()
#             lane_id = lane_obj.getID()
#
#             if lane_num % 2 == 0:
#                 if lane_index < lane_num / 2:
#                     lane_ref_id = lane_index - int(lane_num / 2)
#                 else:
#                     lane_ref_id = lane_index + 1 - int(lane_num / 2)
#             else:
#                 lane_ref_id = lane_index - int(lane_num / 2)
#         else:  # 交叉口外部
#             edge_id = 'inter'
#             lane_id = 'inter'
#             lane_ref_id = 0
#
#         safety_message = create_SafetyMessage(
#             ptcId=int(vid_num),
#             moy=moy,
#             secMark=timeStamp,
#             lat=int(lat * 10000000),
#             lon=int(lon * 10000000),
#             x=int(x),
#             y=int(y),
#             lane_ref_id=lane_ref_id,
#             speed=int(vspeed / 0.02),
#             direction=vdirection,
#             width=int(vwidth * 100),
#             length=int(vlength * 100),
#             classification=vclass,
#             edge_id=edge_id,
#             lane_id=lane_id,
#             obuId=obu_id
#         )  # 创建bsm
#         vehicles_info.append(safety_message)
#
#     return vehicles_info
#
#
# def safety_message_pub_msg(step: int, net: str) -> Tuple[bool, Optional[PubMsgLabel]]:
#     """
#     获取已经做好发送准备的车辆消息
#     Args:
#         step: 仿真步
#         net: 路网文件
#     Returns:
#
#     """
#     vehicles_info = get_vehicle_info(net)  # 调用traci接口获取所有车辆的消息
#     pub_label = PubMsgLabel(vehicles_info, DataMsg.SafetyMessage, convert_method='flatbuffers', multiple=True)
#     return True, pub_label
#
#
# class NetInfo:
#     def __init__(self, net) -> None:
#         self.net = sumolib.net.readNet(net)
#
#
# class VehInfo:
#     def __init__(self, veh_id, net) -> None:
#         self.net = NetInfo(net).net  #
#         self.veh_id = veh_id  # 车辆id
#         self.veh_type = traci.vehicle.getTypeID(self.veh_id)  # 车辆typeid
#         self.veh_class = traci.vehicletype.getVehicleClass(self.veh_type)  # 车辆class
#
#     def getVehSize(self) -> tuple:
#         """
#         获取车辆尺寸信息
#
#         Returns:
#             车辆尺寸：长宽高（m）
#         """
#         vlength = traci.vehicletype.getLength(self.veh_type)  # 车辆长度
#         vwidth = traci.vehicletype.getWidth(self.veh_type)  # 车辆宽度
#         vheight = traci.vehicletype.getHeight(self.veh_type)  # 车辆高度
#         return vlength, vwidth, vheight
#
#     def getSpeed(self) -> float:
#         """
#         获取车辆速度信息
#
#         Returns:
#             车辆速度（m/s）
#         """
#         vspeed = traci.vehicle.getSpeed(self.veh_id)
#         return vspeed
#
#     def getAcceleration(self) -> float:
#         """
#         获取车辆加速度信息
#
#         Returns:
#             车辆行驶方向加速度
#         """
#         vaccel = traci.vehicle.getAcceleration(self.veh_id)
#         return vaccel
#
#     def getLane(self) -> str:
#         """
#         获取车辆所在车道
#
#         Returns:
#             车辆所在车道
#         """
#         vlane = traci.vehicle.getLaneID(self.veh_id)
#         return vlane
#
#     def getClass(self) -> str:
#         """
#         获取bsm中定义的车辆类型
#
#         Returns:
#             "xx_TypeUnknown"
#         """
#         class_dict = {
#             "passenger": "passenger_Vehicle_TypeUnknown",
#             "emergency": "emergency_TypeUnknown",
#             "motorcycle": "motorcycle_TypeUnknown",
#             "bus": "transit_TypeUnknown"
#         }
#         if self.veh_class in class_dict:
#             return class_dict[self.veh_class]
#         else:
#             return "unknownVehicleClass"
#
#     def getdirection(self) -> int:
#         """
#         获取车辆行驶方向
#
#         Returns:
#             车辆行驶方向
#         """
#         vdirection = int(traci.vehicle.getAngle(self.veh_id) / 0.0125)
#         return vdirection
#
#     def getXY4veh(self) -> tuple:
#         """
#         获取车辆在路网中的坐标值
#
#         Returns:
#             车辆xy坐标
#         """
#         x, y = traci.vehicle.getPosition(self.veh_id)
#         return x, y
#
#     def getLonLat4veh(self) -> tuple:
#         """
#         获取车辆的经纬度值
#
#         Returns:
#             车辆LON，Lat
#         """
#         x, y = self.getXY4veh()
#         lon, lat = self.net.convertXY2LonLat(x, y)
#         return lon, lat
#
#     def getObuid(self) -> Optional[List[int]]:
#         if self.veh_type == 'CV':
#             obu_id = [0] * (8 - len(self.veh_id))
#             obu_id.extend(int(item) for item in str(self.veh_id))
#             return obu_id
#         else:
#             return None

# Jimmy Zhu
def get_vehicle_class(veh_class: str):
    class_mapping = {
        'passenger': 'passenger_Vehicle_TypeUnknown',
        'emergency': 'emergency_TypeUnknown',
        'motorcycle': 'motorcycle_TypeUnknown',
        'bus': 'transit_TypeUnknown'
    }
    return class_mapping.get(veh_class, 'unknownVehicleClass')


@dataclass(frozen=True)
class VehInfo:
    ptcId: int
    lat: float
    lon: float
    local_x: float
    local_y: float
    lane_ref_id: int
    speed: float
    direction: float
    width: float
    length: float
    acceleration: float
    classification: str
    edge_id: str
    lane_id: str


class JunctionVehContainer:
    _net = None

    # class _MsgCache:
    #     # 用于内部的生成的轨迹或BSM缓存，避免重复调用接口获取数据
    #     def __init__(self):
    #         self.sm: List[dict] = []
    #         self.trajectory: Dict[str, dict] = {}
    #         self.last_update_time = -1

    def __init__(self, junction_id: str):
        self.junction_id = junction_id
        self.central_x, self.central_y = self._net.getNode(junction_id).getCoord()
        self.central_lon, self.central_lat = self._net.convertXY2LonLat(self.central_x, self.central_y)
        self.vehs_info: List[VehInfo] = []

    @classmethod
    def load_net(cls, net: sumolib.net.Net):
        """加载JunctionVehContainer的路网"""
        cls._net = net

    def subscribe_info(self, region_dis: int = 200):
        sub_vars = [tc.VAR_POSITION, tc.VAR_SPEED, tc.VAR_ACCELERATION, tc.VAR_ANGLE, tc.VAR_LENGTH, tc.VAR_WIDTH,
                    tc.VAR_HEIGHT, tc.VAR_VEHICLECLASS, tc.VAR_ROAD_ID, tc.VAR_LANE_ID, tc.VAR_LANE_INDEX]
        traci.junction.subscribeContext(self.junction_id, tc.CMD_GET_VEHICLE_VARIABLE, region_dis, sub_vars)

    # def get_vehicle_info(self) -> Tuple[List[dict], Dict[str, dict]]:
    #     # 同一时间步且数据已有则直接返回数据
    #     _cache = self.msg_cache
    #     if _cache.last_update_time == SimStatus.sim_time_stamp and _cache.sm and _cache.trajectory:
    #         return _cache.sm, _cache.trajectory
    #
    #     # 新的时间步清空缓存的数据
    #     _cache.sm.clear()
    #     _cache.trajectory.clear()
    #     sub_res: dict = traci.junction.getContextSubscriptionResults(self.junction_id)
    #
    #     node = create_NodeReferenceID(int(self.junction_id[:4])) if sub_res else None
    #     # safety_msgs, trajectories = [], {}
    #
    #     for veh_id, veh_info in sub_res.items():

    def update_vehicle_info(self):
        """更新交叉口范围内车辆信息，用于后续构造消息或记录轨迹"""
        self.vehs_info = []  # 重置当前的vehicle数据
        sub_res = traci.junction.getContextSubscriptionResults(self.junction_id)
        for veh_id, sub_veh_info in sub_res.items():
            veh_id_num = veh_name_from_flow_decimal(veh_id)
            local_x, local_y = sub_veh_info[tc.VAR_POSITION]
            lon, lat = self._net.convertXY2LonLat(local_x, local_y)

            edge_id = '' if 'point' in sub_veh_info[tc.VAR_ROAD_ID] or 'J' in sub_veh_info[tc.VAR_ROAD_ID] \
                else sub_veh_info[tc.VAR_ROAD_ID]  # 交叉口内部的edge_id为空

            veh_info = VehInfo(ptcId=veh_id_num,
                               lat=lat,
                               lon=lon,
                               local_x=local_x,
                               local_y=local_y,
                               lane_ref_id=sub_veh_info[tc.VAR_LANE_INDEX],
                               speed=sub_veh_info[tc.VAR_SPEED],
                               direction=sub_veh_info[tc.VAR_ANGLE],
                               width=sub_veh_info[tc.VAR_WIDTH],
                               length=sub_veh_info[tc.VAR_LENGTH],
                               acceleration=sub_veh_info[tc.VAR_ACCELERATION],
                               classification=get_vehicle_class(sub_veh_info[tc.VAR_VEHICLECLASS]),
                               edge_id=edge_id,
                               lane_id=sub_veh_info[tc.VAR_LANE_ID])
            self.vehs_info.append(veh_info)

    def get_trajectories(self) -> Dict[str, dict]:
        trajectories = {}
        """生成用于测评的车辆轨迹数据"""
        for veh_info in self.vehs_info:
            edge_id = veh_info.edge_id

            # 在交叉口内部,edge设为空
            if edge_id.startswith(self.junction_id):
                edge_id = ''
            elif edge_id.endswith(string.digits) and edge_id[-2] == '_':
                continue  # 除了交叉口外其他junction连接段不保存数据
            trajectories[str(veh_info.ptcId)] = create_trajectory(ptcId=veh_info.ptcId,
                                                                  lat=veh_info.lat,
                                                                  lon=veh_info.lon,
                                                                  node=self.junction_id,
                                                                  speed=veh_info.speed,
                                                                  direction=veh_info.direction,
                                                                  acceleration=veh_info.acceleration,
                                                                  edge_id=edge_id)
        return trajectories

    def get_vehicle_info(self) -> List[dict]:
        """生成车辆的SafetyMessage消息"""

        sm_msgs = [
            create_BSM_Baidu(ptcId=veh_info.ptcId,
                             secMark=SimStatus.current_timestamp_in_minute(),
                             moy=SimStatus.current_moy(),
                             timestamp=round(SimStatus.current_real_timestamp(), 1),
                             lat=veh_info.lat,
                             lon=veh_info.lon,
                             speed=veh_info.speed,
                             direction=veh_info.direction)
            for veh_info in self.vehs_info
        ]

        return sm_msgs

    def create_bsm_pub_msg(self) -> Tuple[bool, PubMsgLabel]:
        """创建BSM的推送信息"""
        newly_multiple_bsm = self.get_vehicle_info()
        return True, PubMsgLabel(newly_multiple_bsm, DataMsg.SafetyMessage, convert_method='flatbuffers', multiple=True)

    def get_rsm(self) -> dict:
        participants = [
            create_ParticipantData(ptc_id=veh_info.ptcId,
                                   moy=SimStatus.current_moy(),
                                   secMark=SimStatus.current_timestamp_in_minute(),
                                   lat=veh_info.lat - self.central_lat,  # lat和lon均表示为中心偏移量
                                   lon=veh_info.lon - self.central_lon,
                                   x=veh_info.local_x - self.central_x,
                                   y=veh_info.local_y - self.central_y,
                                   speed=veh_info.speed,
                                   heading=veh_info.direction,
                                   acceleration=veh_info.acceleration,
                                   width=veh_info.width,
                                   length=veh_info.length,
                                   classification=veh_info.classification,
                                   node=create_NodeReferenceID(signalized_intersection_name_decimal(self.junction_id)),
                                   edge_id=veh_info.edge_id,
                                   lane_id=veh_info.lane_id)
            for veh_info in self.vehs_info
        ]
        rsm = create_RoadsideSafetyMessage(node_id=signalized_intersection_name_decimal(self.junction_id),
                                           lat=self.central_lat,
                                           lon=self.central_lon,
                                           participants=participants)
        return rsm

    def create_rsm_pub_msg(self) -> Tuple[bool, PubMsgLabel]:
        """创建RSM的推送消息"""
        newly_rsm = self.get_rsm()
        return True, PubMsgLabel(newly_rsm, DataMsg.RoadsideSafetyMessage, convert_method='flatbuffers')

    def reset(self):
        self.vehs_info = []
