# -*- coding: utf-8 -*-
# @Time        : 2022/11/17 18:01
# @File        : sim_data.py
# @Description : 存放仿真运行环节需要记录的数据

from collections import namedtuple
from dataclasses import dataclass
from abc import abstractmethod
from typing import Tuple, Dict, Callable, Any, Optional, TypeVar, NewType, List, Set

import sumolib
import traci

from simulation.lib.common import logger, timer
from simulation.lib.public_data import ImplementTask, InfoTask, signalized_intersection_name_str
from simulation.lib.public_conn_data import PubMsgLabel
from simulation.information.traffic import Flow
from simulation.information.participants import safety_message_pub_msg
from simulation.application.signal_control import SignalController
from simulation.application.vehicle_control import VehicleController

# IntersectionId = NewType('IntersectionId', str)


@dataclass
class TransitionIntersection:
    intersection_id: str
    current_phase_index: int


class NaiveSimInfoStorage:
    """针对单点交叉口的运行数据存储"""
    def __init__(self, net):
        self.flow_status = Flow()  # 流量信息存储
        self.signal_controllers = self._initialize_sc(net)  # 信号转换计划
        self.vehicle_controller = VehicleController()  # 车辆控制实例
        self.update_module_method: List[Callable[[], None]] = []

    @staticmethod
    def _initialize_sc(net: sumolib.net.Net):
        """初始化sc控制器"""
        SignalController.load_net(net)  # 初始化signal controller的地图信息
        nodes = net.getNodes()
        scs = {}
        for node in nodes:
            node_type = node.getType()
            if node_type != 'traffic_light':
                continue

            tl_node_id: str = node.getID()
            sc = SignalController(tl_node_id)
            scs[tl_node_id] = sc
        return scs

    @timer
    def update_storage(self):
        """执行数据模块中需要执行的更新操作"""
        for update_func in self.update_module_method:
            update_func()

    def quick_init_update_execute(self, net: sumolib.net.Net, links: Set[str] = None):
        """
        快速初始化每一步对sim_data数据更新需要执行的函数
        Args:
            net: 地图文件
            links: 选定的links

        Returns:

        """
        self.flow_status.initialize_counter(net, links)
        flow_update_func = self.flow_status.flow_update_task()
        self.update_module_method.append(flow_update_func)

        # TODO: only for test
        # for sc in self.signal_controllers.values():
        #     self.update_module_method.append(sc.get_current_spat)

    def initialize_sc_after_start(self):
        """调用start建立traci连接后为traffic_light添加订阅"""
        for sc in self.signal_controllers.values():
            sc.subscribe_info()

    def create_signal_update_task(self, signal_scheme: dict) -> Optional[ImplementTask]:
        node = signal_scheme.get('node_id')
        if node is None:
            return None
        node_id = node.get('id')
        if node_id is None:
            return None

        node_name = signalized_intersection_name_str(node_id)
        sc = self.signal_controllers.get(node_name)
        if sc is None:
            logger.info(f'cannot find intersection {node_name} in the network for signal scheme data')
            return None

        sc_control_task = sc.create_control_task(signal_scheme)
        return sc_control_task

    @staticmethod
    def create_safety_message_info_task(target_topic: str = None, region: set = None):
        """
        创建获取车辆安全消息任务
        Args:
            target_topic: 发送的目标topic
            region: 所选的交叉口范围

        Returns:

        """
        return InfoTask(safety_message_pub_msg, args=(region,), target_topic=target_topic)  # TODO: 等待core执行传入的函数，并发送到topic

    def create_speedguide_task(self, MSG_SpeedGuide_list: List[dict]) -> Optional[List[ImplementTask]]:
        """
        根据传入时刻创建车速引导任务：首先获取车速引导信息，创建车速引导任务，删除多余储存
        Args:
            MSG_SpeedGuide_list:当前时刻传入的多条车速引导指令的列表。指令内容详见https://code.zbmec.com/mec_core/mecdata/-/wikis/8-典型应用场景/1-车速引导
        Returns:
            车速引导指令。[{veh_id: guide}]
        """
        # TODO: msg_speed_guide 应从list[dict]转为 dict，对一条speed_guide_msg生成一个task (Zhu)
        current_time = traci.simulation.getTime()
        self.vehicle_controller.get_speedguide_info(MSG_SpeedGuide_list)  # 获取车速引导信息

        _guidance = {veh_id: guide for veh_id, guidances in self.vehicle_controller.SpeedGuidanceStorage.items()
                     for time, guide in guidances.items() if time == current_time}  # 找出当前时刻的指令
        if len(_guidance) == 0:
            return None
        else:
            _task = []  # 创建车速引导任务
            for veh_id, guide in _guidance.items():
                _task.append(ImplementTask(traci.vehicle.setMaxSpeed(veh_id, guide+0.01), exec_time=current_time))
                _task.append(ImplementTask(traci.vehicle.setSpeed(veh_id, guide), exec_time=current_time))
            
            self.vehicle_controller.update_speedguide_info(current_time)  # 删除多余存储

            return _task

    def reset(self):
        """清空当前保存的运行数据"""
        self.flow_status.clear()
        self.vehicle_controller.clear_speedguide_info()


class ArterialSimInfoStorage(NaiveSimInfoStorage):
    """新增干线的运行数据存储"""
    def __init__(self, net):
        super().__init__(net)
        self.transition_status: Dict[str, TransitionIntersection] = {}

    def reset(self):
        """清空当前保存的运行数据"""
        super().reset()
        self.transition_status.clear()
        self.vehicle_controller.clear_speedguide_info()

