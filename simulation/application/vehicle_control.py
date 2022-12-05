# -*- coding: utf-8 -*-
# @Time        : 2022/11/25 22:14
# @File        : vehicle_control.py
# @Description : 对车辆进行控制

from typing import Tuple, List, Dict, Optional

import sumolib
import traci

from simulation.lib.common import logger
from simulation.lib.public_data import *


class VehicleController:
    _net = None

    def __init__(self) -> None:
        self.SpeedGuidanceStorage = {}  # {veh_id: {time: guide}}
        pass

    @classmethod
    def load_net(cls, net: sumolib.net.Net):
        """加载VehicleController的路网"""
        cls._net = net
    
    def get_speedguide_info(self, MSG_SpeedGuide: Dict) -> None:
        """
        接收MEC数据，提取有效信息转化成所需
        Args:
            MSG_SpeedGuide:当前时刻传入的车速引导指令。指令内容详见https://code.zbmec.com/mec_core/mecdata/-/wikis/8-典型应用场景/1-车速引导
        """
        if MSG_SpeedGuide['veh_id'] not in self.SpeedGuidanceStorage:
            self.SpeedGuidanceStorage[MSG_SpeedGuide['veh_id']] = {}  # 创建车速引导指令
        for guide_info in MSG_SpeedGuide['guide_info']:  # 进入同一MSG下的不同guide_info
            self.SpeedGuidanceStorage[MSG_SpeedGuide['veh_id']][guide_info['time']] = guide_info['guide'] / 10  # 更新车速引导指令

        return None

    def update_speedguide_info(self, current_time: int) -> None:
        """
        根据传入时刻更新SpeedGuidanceStorage
        Args:
            仿真时刻
        """
        for veh, guidances in self.SpeedGuidanceStorage.items():
            guidances = {time: guide for time, guide in guidances.items() if time > current_time}
        self.SpeedGuidanceStorage = {veh: guidances for veh, guidances in self.SpeedGuidanceStorage if len(guidances) != 0}

        return None

    def clear_speedguide_info(self) -> None:
        """
        清空SpeedGuidanceStorage
        """
        self.SpeedGuidanceStorage.clear()
        return None

    

        
            








    

    


        


        
