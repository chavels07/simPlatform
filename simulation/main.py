# -*- coding: utf-8 -*-
# @Time        : 2022/11/17 17:20
# @File        : main.py
# @Description : 仿真运行主程序

import os
import sys
import time

from collections import OrderedDict
from typing import List, Dict, Optional

from simulation.lib.common import logger, singleton
from simulation.lib.sim_data import ImplementTask, InfoTask, NaiveSimInfoStorage, ArterialSimInfoStorage
from simulation.connection.mqtt import MQTTConnection


# 校验环境变量中是否存在SUMO_HOME
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

import sumolib
import traci


@singleton
class SimCore:
    def __init__(self, network_fp: str = '../data/network/anting.net.xml', arterial_storage: bool = False):
        self._net_fp = network_fp
        self.net = sumolib.net.readNet(network_fp)  # 路网对象化数据
        self.connection = MQTTConnection()  # 通信接口实现数据外部交互
        self.step_limit = None  # 默认限制仿真运行时间, None为无限制
        self.storage = ArterialSimInfoStorage if arterial_storage else NaiveSimInfoStorage  # 仿真部分数据存储
        self.info_tasks: OrderedDict[int, InfoTask] = OrderedDict()  # TODO:后面还需要实现OD的继承数据结构来保证时间按序排列的
        self.implement_tasks: OrderedDict[int, ImplementTask] = OrderedDict()

    def initialize(self, route_fp: str, detector_fp: Optional[str] = None, step_limit: int = None):
        """
        初始化SUMO路网
        Args:
            route_fp: 车辆路径文件路径
            detector_fp: 检测器文件路径
            step_limit: 限制仿真运行时间(s), None为无限制

        Returns:

        """
        sumoBinary = sumolib.checkBinary('sumo-gui')
        sumoCmd = [sumoBinary, '-c', self._net_fp, '-r' + route_fp]
        if detector_fp is not None:
            sumoCmd.extend(['-a', detector_fp])
        traci.start(sumoCmd)
        self.step_limit = step_limit

    def connect(self, broker: str, port: int, topics=None):
        """通过MQTT通信完成与服务器的连接"""
        self.connection.connect(broker, port, topics)

    def run(self, step_len: float = 0):
        """

        Args:
            step_len: 每一步仿真的更新时间间距(s)

        Returns:

        """
        logger.info('仿真开始')
        while traci.simulation.getMinExpectedNumber() >= 0:
            traci.simulationStep(step=step_len)

            current_timestamp = traci.simulation.getTime()

            # 控制下发
            for effect_time, implement_task in self.implement_tasks.items():
                if effect_time > current_timestamp:
                    break  # 如果任务需要执行的时间大于当前仿真时间，提前退出
                success, res = implement_task.execute()  # TODO: 如果控制函数执行后需要在main中修改状态，需要通过返回值传递

            # 读取数据
            for effect_time, info_task in self.info_tasks.items():
                if effect_time > current_timestamp:
                    break  # 如果任务需要执行的时间大于当前仿真时间，提前退出
                success, msg_label = info_task.execute()  # 返回结果: 执行是否成功, 需要发送的消息Optional[PubMsgLabel]
                if msg_label is not None and success:
                    self.connection.publish(msg_label)

            if self.step_limit is not None and current_timestamp > self.step_limit:
                break  # 完成仿真任务提前终止仿真程序


if __name__ == '__main__':
    simulation_core = SimCore()
    simulation_core.initialize('')
    simulation_core.connect('121.36.231.253', 1883)
    simulation_core.run()
