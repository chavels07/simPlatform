# -*- coding: utf-8 -*-
# @Time        : 2022/11/17 18:00
# @File        : participants.py
# @Description : 交通参与者信息提取

from typing import Tuple, List, Optional

import traci

from simulation.lib.public_data import create_SafetyMessage, DataMsg
from simulation.connection.mqtt import PubMsgLabel


def get_vehicle_info(region: set = None) -> List[dict]:
    """
    获取车辆消息
    Args:
        region: 所选的交叉口范围

    Returns:

    """
    vehicles_info = []
    for veh_id in traci.vehicle.getIDList():
        lng = 0
        lat = 1

        safety_message = create_SafetyMessage(..., ..., ..., ...)
        vehicles_info.append(safety_message)

    return vehicles_info


def safety_message_pub_msg(region: set = None) -> Tuple[bool, Optional[PubMsgLabel]]:
    """
    获取已经做好发送准备的车辆消息
    Args:
        region:

    Returns:

    """
    vehicles_info = get_vehicle_info(region)  # 调用traci接口获取在region范围内所有车辆的消息
    pub_label = PubMsgLabel(vehicles_info, DataMsg.SafetyMessage, convert_method='flatbuffers', multiple=True)
    return True, pub_label
