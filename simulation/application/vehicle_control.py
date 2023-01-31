# -*- coding: utf-8 -*-
# @Time        : 2022/11/25 22:14
# @File        : vehicle_control.py
# @Description : 对车辆进行车速引导控制；若不同MSG对于同一车辆发出不同的speed信息，则按照最新时刻MSG进行更新储存；对于过期的车速引导信息进行删除

from typing import Tuple, List, Dict, Optional

import sumolib
import traci

from simulation.lib.common import logger
from simulation.lib.public_data import SimStatus


def flow_str_convert(veh_id: int):
    """对于Flow形式输入的交通流车辆id的转换"""
    return ''.join(('flow', str(veh_id), '.0'))


class VehicleController:
    _net = None

    def __init__(self) -> None:
        self.SpeedGuidanceStorage = {}  # {veh_id: {time: guide}}
        pass

    @classmethod
    def load_net(cls, net: sumolib.net.Net):
        """
        加载VehicleController的路网
        Args:
            net: 当前路网文件
        """
        cls._net = net
    
    def get_speedguide_info(self, MSG_SpeedGuide: Dict) -> None:
        """
        接收MEC数据，提取有效信息转化成所需
        Args:
            MSG_SpeedGuide: 当前时刻传入的车速引导指令。指令内容详见https://code.zbmec.com/mec_core/mecdata/-/wikis/8-典型应用场景/1-车速引导
        """
        veh_id_str = flow_str_convert(MSG_SpeedGuide['veh_id'])
        if veh_id_str not in self.SpeedGuidanceStorage:
            self.SpeedGuidanceStorage[veh_id_str] = {}  # 创建车速引导指令
        for guide_info in MSG_SpeedGuide['guide_info']:  # 进入同一MSG下的不同guide_info
            self.SpeedGuidanceStorage[veh_id_str][SimStatus.sim_time_stamp] = guide_info['guide'] / 10  # 更新车速引导指令
            # Jimmy: 收到指令后直接执行，时间改为当前仿真时间

        return None

    def update_speedguide_info(self) -> None:
        """
        更新SpeedGuidanceStorage
        """
        # for veh, guidances in self.SpeedGuidanceStorage.items():
        #     guidances = {time: guide for time, guide in guidances.items() if time > current_time}
        self.SpeedGuidanceStorage = {veh: guidances for veh, guidances in self.SpeedGuidanceStorage.items() if len(guidances) != 0}

        return None

    def clear_speedguide_info(self) -> None:
        """
        清空SpeedGuidanceStorage
        """
        self.SpeedGuidanceStorage.clear()
        return None

    

        
            








    

    


        


        
