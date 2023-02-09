# -*- coding: utf-8 -*-
# @Time        : 2022/11/17 18:01
# @File        : sim_data.py
# @Description : 存放仿真运行环节需要记录的数据

from dataclasses import dataclass
from typing import Tuple, Dict, Callable, Optional, List, Iterable

import sumolib
import traci

from simulation.lib.common import logger, timer
from simulation.lib.public_data import ImplementTask, InfoTask, signalized_intersection_name_str, SimStatus
from simulation.information.traffic import FlowStopLine
from simulation.information.participants import JunctionVehContainer
from simulation.application.signal_control import SignalController
from simulation.application.vehicle_control import VehicleController


# IntersectionId = NewType('IntersectionId', str)


@dataclass
class TransitionIntersection:
    intersection_id: str
    current_phase_index: int


class SimInfoStorage:
    """存储仿真系统平台所需使用的运行数据

    Notes:
        ----------使用说明----------
        初始化过程:
        1) load_net                                  # 加载路网
        2) initialize_sc/initialize_participant      # 信号机/交通参与者记录模块状态初始化
        3) initialize_update_execute                 # 注册各模块状态更新函数
        4) storage.initialize_subscribe_after_start  # 添加订阅信息(必须等待SUMO启动后才能初始化)

        仿真运行更新过程:
        update_storage  # 调用各模块已注册的更新方法

        仿真结束:
        reset           # 重置仿真数据状态

        ----------外部更新----------
        Storage及SUMO仿真可通过外部控制命令更新信号灯、交通参与者等状态
        任意模块或对象状态更新需要提供create_xxx_task方法，输入控制命令对应的dict，输出ImplementTask实例
        所控制模块(信号灯、交通参与者等)的内部状态更新也在方法中执行，ImplementTask的生成可在模块内部完成，也可在该方法中
        控制命令响应前需要进行一定的检查(控制对象是否存在、数值合法性检查等)

    """

    def __init__(self):
        self.flow_cons: Optional[Dict[str, FlowStopLine]] = None
        self.signal_controllers: Optional[Dict[str, SignalController]] = None  # 信号转换计划
        self.junction_veh_cons: Optional[Dict[str, JunctionVehContainer]] = None  # 交叉口范围车辆管理器
        self.vehicle_controller = VehicleController()  # 车辆控制实例
        self.trajectory_info = {}

        self.update_module_method: List[Callable[[], None]] = []

    # def initialize_sc(self, net: sumolib.net.Net, junction_list: Iterable[str] = None):
    #     """
    #     初始化sc控制器
    #     Args:
    #         net: 静态路网数据
    #         junction_list: 所需选定的交叉口范围
    #
    #     Returns:
    #
    #     """
    #     SignalController.load_net(net)  # 初始化signal controller的地图信息
    #     if junction_list is None:
    #         junction_list = self._get_all_signalized_junction(net)
    #
    #     scs = {SignalController(node_id) for node_id in junction_list}
    #     self.signal_controllers = scs
    #
    # def initialize_traffic_flow(self, net: sumolib.net.Net, junction_list: Iterable[str] = None):
    #     if junction_list is None:
    #         junction_list = self._get_all_signalized_junction(net)
    #
    #     flow_containers = {FlowStopLine(node_id) for node_id in junction_list}
    #     self.flow_cons = flow_containers
    #
    # def initialize_participant(self, net: sumolib.net.Net, junction_list: Iterable[str] = None):
    #     """
    #     初始化交叉口车辆管理器
    #     Args:
    #         net: 静态路网数据
    #         junction_list: 所需选定的交叉口范围
    #
    #     Returns:
    #
    #     """
    #     JunctionVehContainer.load_net(net)
    #     if junction_list is None:
    #         junction_list = self._get_all_signalized_junction(net)
    #
    #     junction_veh_cons = {}
    #     for junction in junction_list:
    #         junction_veh_con = JunctionVehContainer(junction)
    #         junction_veh_cons[junction] = junction_veh_con
    #     self.junction_veh_cons = junction_veh_cons

    def _initialize_storage_unit(self, unit_type_str: str, net: sumolib.net.Net, junction_list: Iterable[str] = None):
        factory = {
            'sc': SignalController,
            'tf': FlowStopLine,
            'ptc': JunctionVehContainer
        }
        if unit_type_str not in factory:
            raise KeyError(f'Unknown storage unit type {unit_type_str}')
        unit_type = factory[unit_type_str]

        if junction_list is None:
            junction_list = self._get_all_signalized_junction(net)

        flow_containers = {node_id: unit_type(node_id) for node_id in junction_list}
        return flow_containers

    def initialize_signal_controller(self, net: sumolib.net.Net, junction_list: Iterable[str] = None):
        SignalController.load_net(net)
        self.signal_controllers = self._initialize_storage_unit('sc', net, junction_list)

    def initialize_traffic_flow(self, net: sumolib.net.Net, junction_list: Iterable[str] = None):
        FlowStopLine.load_net(net)
        self.flow_cons = self._initialize_storage_unit('tf', net, junction_list)

    def initialize_participant(self, net: sumolib.net.Net, junction_list: Iterable[str] = None):
        JunctionVehContainer.load_net(net)
        self.junction_veh_cons = self._initialize_storage_unit('ptc', net, junction_list)
        self.junction_veh_cons['31011410002'] = JunctionVehContainer('31011410002')

    def initialize_update_execute(self,
                                  trajectory_update: bool = True,
                                  traffic_flow_update: bool = False):
        """
        快速初始化每一步对sim_data数据更新需要执行的函数
        Args:
            trajectory_update: 执行车辆轨迹更新
            traffic_flow_update: 执行TrafficFlow更新


        Returns:

        """
        # 如果需要发送TrafficFlow，添加更新TF方法
        if traffic_flow_update:
            # self.flow_status.initialize_counter(net, set(nodes))
            # self.update_module_method.append(self.flow_status.flow_update_task())
            self.update_module_method.append(self.traffic_flow_update_task())
        # 添加更新车辆信息方法，用于发送BSM/RSM或记录轨迹信息
        if trajectory_update:
            for container in self.junction_veh_cons.values():
                self.update_module_method.append(container.update_vehicle_info)
            self.update_module_method.append(self.record_trajectories_update_task())

    def initialize_subscribe_after_start(self):
        """调用start建立traci连接后为traffic_light添加订阅"""
        if self.signal_controllers is not None:
            for sc in self.signal_controllers.values():
                sc.subscribe_info()

        if self.junction_veh_cons is not None:
            for jun_veh in self.junction_veh_cons.values():
                jun_veh.subscribe_info(region_dis=60)

    def create_signal_update_task(self, signal_scheme: dict) -> Optional[ImplementTask]:
        """
        根据SignalScheme消息创建信号更新任务
        Args:
            signal_scheme: 信号方案消息

        Returns:
            信号更新的可执行任务

        """
        node = signal_scheme.get('node_id')
        if node is None:
            return None
        node_id = node.get('id')
        if node_id is None:
            return None

        # TODO: 固定node_id转换
        if node_id == 33:
            node_name = '31011410002'
        else:
            node_name = signalized_intersection_name_str(node_id)
        sc = self.signal_controllers.get(node_name)
        if sc is None:
            logger.info(f'cannot find intersection {node_name} in the network for signal scheme data')
            return None

        sc_control_task = sc.create_control_task(signal_scheme)
        return sc_control_task

    def create_speed_guide_task(self, MSG_SpeedGuide: dict) -> Optional[List[ImplementTask]]:
        """
        根据传入时刻创建车速引导任务：首先获取车速引导信息，创建车速引导任务，删除多余储存
        Args:
            MSG_SpeedGuide:当前时刻传入的多条车速引导指令。指令内容详见https://code.zbmec.com/mec_core/mecdata/-/wikis/8-典型应用场景/1-车速引导
        Returns:
            车速引导指令。[{veh_id: guide}]
        """

        def _traci_set_speed_wrapper(vehID, speed):
            try:
                traci.vehicle.setSpeed(vehID=vehID, speed=speed)
                logger.info(f'set speed {speed} for vehicle {vehID} successfully')
                return True, None
            except traci.TraCIException as e:
                logger.warn(f'cannot set speed {speed} for vehicle {vehID}, traceback message from traci: {e.args}')
                return False, None

        def _traci_set_max_speed_wrapper(vehID, speed):
            try:
                traci.vehicle.setMaxSpeed(vehID=vehID, speed=speed)
                return True, None
            except traci.TraCIException as e:
                logger.warn(f'cannot set max speed {speed} for vehicle {vehID}, traceback message from traci: {e.args}')
                return False, None

        current_time = SimStatus.sim_time_stamp
        self.vehicle_controller.get_speedguide_info(MSG_SpeedGuide)  # 获取车速引导信息

        _guidance = {veh_id: guide for veh_id, guidances in self.vehicle_controller.SpeedGuidanceStorage.items()
                     for time, guide in guidances.items() if time == current_time}  # 找出当前时刻的指令
        if len(_guidance) == 0:
            return None
        else:
            _task = []  # 创建车速引导任务
            for veh_id, guide in _guidance.items():
                _task.append(ImplementTask(_traci_set_max_speed_wrapper, args=(veh_id, guide + 0.01)))
                _task.append(ImplementTask(_traci_set_speed_wrapper, args=(veh_id, guide)))

            self.vehicle_controller.update_speedguide_info()  # 删除多余存储

            return _task

    def record_trajectories_update_task(self, interval: float = 1.) -> Callable[[], None]:
        """创建轨迹字典记录的更新任务"""

        def _wrapper():
            # 只有到整数时记录数据
            if SimStatus.sim_time_stamp % interval:
                return None
            for junction_id, veh_container in self.junction_veh_cons.items():
                trajectories = veh_container.get_trajectories()
                if not trajectories:
                    return None

                # 记录数据
                self.trajectory_info.setdefault(junction_id, dict())[str(int(SimStatus.sim_time_stamp))] = trajectories

        return _wrapper

    def traffic_flow_update_task(self, interval: float = 1.) -> Callable[[], None]:

        def _wrapper():
            if SimStatus.sim_time_stamp % interval:
                return None
            for junction_id, flow_container in self.flow_cons.items():
                veh_container = self.junction_veh_cons.get(junction_id)

                if veh_container is None:
                    raise RuntimeError(f'traffic flow cannot be updated before initialize participant for junction {junction_id}')
                curr_veh_info = veh_container.vehs_info
                flow_container.update_vehicle_cache(curr_veh_info)

        return _wrapper

    def update_storage(self):
        """执行数据模块中需要执行的更新操作"""
        for update_func in self.update_module_method:
            update_func()

    def _reset_storage_unit(self, *units):
        for unit in units:
            if unit is None:
                return None

            for unit_obj in unit.values():
                if hasattr(unit_obj, 'reset'):
                    unit_obj.reset()  # 调用类定义的reset方法重置存储状态

    def reset(self):
        """清空当前保存的运行数据"""
        self._reset_storage_unit(self.flow_cons, self.signal_controllers, self.junction_veh_cons)
        self.vehicle_controller.clear_speedguide_info()
        self.trajectory_info = {}

    @staticmethod
    def _get_all_signalized_junction(net: sumolib.net.Net):
        return (node.getID() for node in net.getNodes() if node.getType() == 'traffic_light')


class ArterialSimInfoStorage(SimInfoStorage):
    """新增干线的运行数据存储"""

    def __init__(self):
        super().__init__()
        self.transition_status: Dict[str, TransitionIntersection] = {}

    def reset(self):
        """清空当前保存的运行数据"""
        super().reset()
        self._reset_storage_unit(self.trajectory_info)
        self.vehicle_controller.clear_speedguide_info()
