# -*- coding: utf-8 -*-
# @Time        : 2022/11/17 18:00
# @File        : participants.py
# @Description : 交通参与者信息提取

from typing import Tuple, List, Dict, Optional

import traci
import traci.constants as tc
import sumolib

from simulation.lib.public_data import (create_SafetyMessage, create_NodeReferenceID, create_trajectory, SimStatus,
                                        veh_name_from_flow_decimal, signalized_intersection_name_decimal)
from simulation.lib.public_conn_data import DataMsg, PubMsgLabel


def get_vehicle_info(net: str) -> List[dict]:
    """
    获取车辆消息
    Args:
        net: 路网文件
    Returns:
        所有车辆bsm
    """
    vehicles_list = traci.vehicle.getIDList()  # 获取当前路网中所有车辆
    vehicles_info = []  # 创建bsm list

    # 从SimStatus中读数据
    moy = SimStatus.current_moy()
    timeStamp = SimStatus.current_timestamp_in_minute()

    for veh_id in vehicles_list:
        vehicle = VehInfo(veh_id, net)  # 创建车辆实例
        vlane = vehicle.getLane()
        vclass = vehicle.veh_class
        vlength, vwidth, vheight = vehicle.getVehSize()
        vspeed = vehicle.getSpeed()
        vaccel = vehicle.getAcceleration()
        vdirection = vehicle.getdirection()
        x, y = vehicle.getXY4veh()
        lon, lat = vehicle.getLonLat4veh()
        obu_id = vehicle.getObuid()

        vid_num = veh_id.split('.')[-1]  # 提取sumo的到的车辆id中数字部分

        if vlane != '' and 'point' not in vlane:  # 交叉口内部
            lane_obj = vehicle.net.getLane(vlane)
            lane_num = len(lane_obj.getEdge().getLanes())
            lane_index = int(lane_obj.getIndex())
            edge_id = lane_obj.getEdge().getID()
            lane_id = lane_obj.getID()

            if lane_num % 2 == 0:
                if lane_index < lane_num / 2:
                    lane_ref_id = lane_index - int(lane_num / 2)
                else:
                    lane_ref_id = lane_index + 1 - int(lane_num / 2)
            else:
                lane_ref_id = lane_index - int(lane_num / 2)
        else:  # 交叉口外部
            edge_id = 'inter'
            lane_id = 'inter'
            lane_ref_id = 0

        safety_message = create_SafetyMessage(
            ptcId=int(vid_num),
            moy=moy,
            secMark=timeStamp,
            lat=int(lat * 10000000),
            lon=int(lon * 10000000),
            x=int(x),
            y=int(y),
            lane_ref_id=lane_ref_id,
            speed=int(vspeed / 0.02),
            direction=vdirection,
            width=int(vwidth * 100),
            length=int(vlength * 100),
            classification=vclass,
            edge_id=edge_id,
            lane_id=lane_id,
            obuId=obu_id
        )  # 创建bsm
        vehicles_info.append(safety_message)

    return vehicles_info


def safety_message_pub_msg(step: int, net: str) -> Tuple[bool, Optional[PubMsgLabel]]:
    """
    获取已经做好发送准备的车辆消息
    Args:
        step: 仿真步
        net: 路网文件
    Returns:

    """
    vehicles_info = get_vehicle_info(net)  # 调用traci接口获取所有车辆的消息
    pub_label = PubMsgLabel(vehicles_info, DataMsg.SafetyMessage, convert_method='flatbuffers', multiple=True)
    return True, pub_label


class NetInfo:
    def __init__(self, net) -> None:
        self.net = sumolib.net.readNet(net)


class VehInfo:
    def __init__(self, veh_id, net) -> None:
        self.net = NetInfo(net).net  # 
        self.veh_id = veh_id  # 车辆id
        self.veh_type = traci.vehicle.getTypeID(self.veh_id)  # 车辆typeid
        self.veh_class = traci.vehicletype.getVehicleClass(self.veh_type)  # 车辆class

    def getVehSize(self) -> tuple:
        """
        获取车辆尺寸信息

        Returns:
            车辆尺寸：长宽高（m）
        """
        vlength = traci.vehicletype.getLength(self.veh_type)  # 车辆长度
        vwidth = traci.vehicletype.getWidth(self.veh_type)  # 车辆宽度
        vheight = traci.vehicletype.getHeight(self.veh_type)  # 车辆高度
        return vlength, vwidth, vheight

    def getSpeed(self) -> float:
        """
        获取车辆速度信息

        Returns:
            车辆速度（m/s）
        """
        vspeed = traci.vehicle.getSpeed(self.veh_id)
        return vspeed

    def getAcceleration(self) -> float:
        """
        获取车辆加速度信息

        Returns:
            车辆行驶方向加速度
        """
        vaccel = traci.vehicle.getAcceleration(self.veh_id)
        return vaccel

    def getLane(self) -> str:
        """
        获取车辆所在车道

        Returns:
            车辆所在车道
        """
        vlane = traci.vehicle.getLaneID(self.veh_id)
        return vlane

    def getClass(self) -> str:
        """
        获取bsm中定义的车辆类型

        Returns:
            "xx_TypeUnknown"
        """
        class_dict = {
            "passenger": "passenger_Vehicle_TypeUnknown",
            "emergency": "emergency_TypeUnknown",
            "motorcycle": "motorcycle_TypeUnknown",
            "bus": "transit_TypeUnknown"
        }
        if self.veh_class in class_dict:
            return class_dict[self.veh_class]
        else:
            return "unknownVehicleClass"

    def getdirection(self) -> int:
        """
        获取车辆行驶方向

        Returns:
            车辆行驶方向
        """
        vdirection = int(traci.vehicle.getAngle(self.veh_id) / 0.0125)
        return vdirection

    def getXY4veh(self) -> tuple:
        """
        获取车辆在路网中的坐标值

        Returns:
            车辆xy坐标
        """
        x, y = traci.vehicle.getPosition(self.veh_id)
        return x, y

    def getLonLat4veh(self) -> tuple:
        """
        获取车辆的经纬度值

        Returns:
            车辆LON，Lat
        """
        x, y = self.getXY4veh()
        lon, lat = self.net.convertXY2LonLat(x, y)
        return lon, lat

    def getObuid(self) -> Optional[List[int]]:
        if self.veh_type == 'CV':
            obu_id = [0] * (8 - len(self.veh_id))
            obu_id.extend(int(item) for item in str(self.veh_id))
            return obu_id
        else:
            return None


def get_vehicle_class(veh_class: str):
    class_mapping = {
        'passenger': 'passenger_Vehicle_TypeUnknown',
        'emergency': 'emergency_TypeUnknown',
        'motorcycle': 'motorcycle_TypeUnknown',
        'bus': 'transit_TypeUnknown'
    }
    return class_mapping.get(veh_class, 'unknownVehicleClass')


# Jimmy Zhu
class JunctionVehContainer:
    _net = None

    def __init__(self, junction_id: str):
        self.junction_id = junction_id

    @classmethod
    def load_net(cls, net: sumolib.net.Net):
        """加载JunctionVehContainer的路网"""
        cls._net = net

    def subscribe_info(self, region_dis: int = 100):
        sub_vars = [tc.VAR_POSITION, tc.VAR_SPEED, tc.VAR_ACCELERATION, tc.VAR_ANGLE, tc.VAR_LENGTH, tc.VAR_WIDTH,
                    tc.VAR_HEIGHT, tc.VAR_VEHICLECLASS, tc.VAR_ROAD_ID, tc.VAR_LANE_ID, tc.VAR_LANE_INDEX]
        traci.junction.subscribeContext(self.junction_id, tc.CMD_GET_VEHICLE_VARIABLE, region_dis, sub_vars)

    def get_vehicle_info(self) -> Tuple[List[dict], Dict[str, dict]]:
        sub_res: dict = traci.junction.getContextSubscriptionResults(self.junction_id)

        node = create_NodeReferenceID(signalized_intersection_name_decimal(self.junction_id)) if sub_res else None
        safety_msgs, trajectories = [], {}

        for veh_id, veh_info in sub_res.items():
            veh_id_num = veh_name_from_flow_decimal(veh_id)
            local_x, local_y = veh_info[tc.VAR_POSITION]
            lon, lat = self._net.convertXY2LonLat(local_x, local_y)

            _SafetyMessage = create_SafetyMessage(ptcId=veh_id_num,
                                                  moy=SimStatus.current_moy(),
                                                  secMark=SimStatus.current_timestamp_in_minute(),
                                                  lat=lat,
                                                  lon=lon,
                                                  x=local_x,
                                                  y=local_y,
                                                  node=node,
                                                  lane_ref_id=veh_info[tc.VAR_LANE_INDEX],
                                                  speed=veh_info[tc.VAR_SPEED],
                                                  direction=veh_info[tc.VAR_ANGLE],
                                                  width=veh_info[tc.VAR_WIDTH],
                                                  length=veh_info[tc.VAR_LENGTH],
                                                  acceleration=veh_info[tc.VAR_ACCELERATION],
                                                  classification=get_vehicle_class(veh_info[tc.VAR_VEHICLECLASS]),
                                                  edge_id=veh_info[tc.VAR_ROAD_ID],
                                                  lane_id=veh_info[tc.VAR_LANE_ID])

            trajectory = create_trajectory(ptcId=veh_id_num,
                                           moy=SimStatus.current_moy(),
                                           secMark=SimStatus.current_timestamp_in_minute(),
                                           lat=lat,
                                           lon=lon,
                                           node=self.junction_id,
                                           lane_ref_id=veh_info[tc.VAR_LANE_INDEX],
                                           speed=veh_info[tc.VAR_SPEED],
                                           direction=veh_info[tc.VAR_ANGLE],
                                           acceleration=veh_info[tc.VAR_ACCELERATION],
                                           classification=get_vehicle_class(veh_info[tc.VAR_VEHICLECLASS]),
                                           edge_id=veh_info[tc.VAR_ROAD_ID])
            safety_msgs.append(_SafetyMessage)
            trajectories[str(veh_id_num)] = trajectory
        return safety_msgs, trajectories


