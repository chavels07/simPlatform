# -*- coding: utf-8 -*-
# @Time        : 2022/11/18 19:33
# @File        : traffic.py
# @Description : 交通流数据的存储，更新，读取

from collections import defaultdict
from typing import Tuple, Iterable, Callable
from warnings import warn

import traci


class FlowCounter:
    def __init__(self):
        self.flow_storage = 0
        self.last_vehicles_set = set()  # 暂时存储车辆ID, 防止两个相近时间步长检测到同一辆车计数多次
        self.record_start_time = None

    def reset(self):
        """重置计数器状态"""
        self.flow_storage = 0
        self.record_start_time = None


class Flow:
    def __init__(self):
        self.flow_counter = defaultdict(FlowCounter)

    def update_vehicle_set(self, detector: str):
        """
        从检测器数据更新流量信息
        Args:
            detector: 检测器id
        """
        detector_counter = self.flow_counter[detector]
        if detector_counter.record_start_time is None:
            detector_counter.record_start_time = traci.simulation.getTime()
        this_step_vehicles = set(traci.lanearea.getLastStepVehicleIDs(detector))
        new_arrival_num = this_step_vehicles.difference(detector_counter.last_vehicles_set)
        detector_counter.flow_storage += new_arrival_num

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
        current_timestamp = traci.simulation.getTime()
        flow_fixed_period = detector_counter.flow_storage
        period = current_timestamp - detector_counter.record_start_time
        if period < 1e-4:
            warn('period is zero, get_flow function was called too often')
            return -1, -1.
        detector_counter.reset()  # 重置记录时间和流量记录
        return flow_fixed_period, period

    def flow_update_task(self, detector_list: Iterable[str]) -> Callable[[], None]:
        """创建在每次仿真时更新所有检测器所在路段流量的任务，返回可调用函数"""
        def wrapper():
            for detector in detector_list:
                self.update_vehicle_set(detector)
        return wrapper
