# -*- coding: utf-8 -*-
# @Time        : 2023/1/2 14:20
# @File        : config.py
# @Description :

import json
import os
from collections import namedtuple
from typing import Optional, List

# 与配置JSON文件中消息类型的名字对应
CONFIG_MSG_NAME = {
    'BSM': 'basicSafetyMessage',
    'RSM': 'roadsideSafetyMessage',
    'SPAT': 'signalPhaseAndTiming',
    'TF': 'trafficFlow',
    'SE': 'signalExecution'
}


class SetupConfig:
    """仿真设置参数"""
    config_file_path: str = None
    network_file_path: str = None
    route_file_path: str = None
    detector_file_path: str = None
    e1detector_output_file_path: str = None
    e2detector_output_file_path: str = None
    output_file_path: str = None
    test_name: str = None
    arterial_mode: bool = True
    await_start_cmd: bool = False

    @classmethod
    def is_route_directory(cls):
        """判断route路径是文件夹还是单个文件"""
        if cls.route_file_path.endswith('xml'):
            return False
        return True


_MsgCfg = namedtuple('_MsgCfg', ['name', 'frequency'])


class SimulationConfig:
    """仿真运行参数"""
    pub_msgs: List[_MsgCfg] = []
    junction_region: Optional[List[str]] = None
    sim_time_step: float = 1
    sim_time_limit: Optional[float] = None
    warm_up_time: int = 0


class ConnectionConfig:
    """通信参数"""
    broker: str = ''
    port: int = -1


def load_config_json(cfg_path):
    with open(cfg_path, 'r') as f:
        cfg = json.load(f)

    # 仿真启动前预先设置的参数
    top_level_dir = os.path.abspath('..')  # 获取项目绝对路径
    top_level_dir = top_level_dir.replace('\\', '/')
    setup_para = cfg['preliminary']
    SetupConfig.config_file_path = '/'.join((top_level_dir, setup_para['config_file_path']))
    SetupConfig.network_file_path = '/'.join((top_level_dir, setup_para['network_file_path']))
    SetupConfig.route_file_path = '/'.join((top_level_dir, setup_para['route_file_path']))
    if setup_para['detector_file_path']:
        SetupConfig.detector_file_path = '/'.join((top_level_dir, setup_para['detector_file_path']))
    SetupConfig.test_name = setup_para.get('test_name', 'No test name')
    SetupConfig.arterial_mode = setup_para.get('arterial_mode', True)
    SetupConfig.await_start_cmd = setup_para.get('await_start_cmd', False)

    # 仿真运行时设置参数
    simulation_para = cfg['simulation']
    for key, value in simulation_para['pub_msg'].items():
        if value['frequency'] > 0:
            SimulationConfig.pub_msgs.append(_MsgCfg(key, value['frequency']))

    junction_scenarios = simulation_para['junction_region']  # 长度为0时表示场景覆盖路网所有交叉口
    if len(junction_scenarios):
        SimulationConfig.junction_region = junction_scenarios

    SimulationConfig.sim_time_step = simulation_para['sim_time_step']
    SimulationConfig.sim_time_limit = simulation_para['sim_time_limit'] if simulation_para['sim_time_limit'] > 0 else None
    SimulationConfig.warm_up_time = simulation_para['warm_up_time']

    # 通信连接参数
    conn_para = cfg.get('connection')
    if conn_para is not None:
        ConnectionConfig.broker = conn_para['broker']
        ConnectionConfig.port = conn_para['port']


import yaml


def load_config(cfg_path):
    with open(cfg_path, 'r') as f:
        cfg = yaml.safe_load(f)
    # 仿真启动前预先设置的参数
    top_level_dir = os.path.abspath('..')  # 获取项目绝对路径
    top_level_dir = top_level_dir.replace('\\', '/')
    setup_para = cfg['preliminary']
    SetupConfig.config_file_path = '/'.join((top_level_dir, setup_para['configFilePath']))
    SetupConfig.network_file_path = '/'.join((top_level_dir, setup_para['networkFilePath']))
    SetupConfig.route_file_path = '/'.join((top_level_dir, setup_para['routeFilePath']))
    if setup_para['detectorFilePath']:
        SetupConfig.detector_file_path = '/'.join((top_level_dir, setup_para['detectorFilePath']))
    if setup_para['e1detectorOutputFilePath']:
        SetupConfig.e1detector_output_file_path = '/'.join((top_level_dir, setup_para['e1detectorOutputFilePath']))
    if setup_para['e2detectorOutputFilePath']:
        SetupConfig.e2detector_output_file_path = '/'.join((top_level_dir, setup_para['e2detectorOutputFilePath']))
    SetupConfig.output_file_path = '/'.join((top_level_dir, setup_para['outputFilePath']))
    SetupConfig.test_name = setup_para.get('testName', 'No test name')
    SetupConfig.arterial_mode = setup_para.get('arterialMode', True)
    SetupConfig.await_start_cmd = setup_para.get('awaitStartCmd', False)

    # 仿真运行时设置参数
    simulation_para = cfg['simulation']
    for pub_msg in simulation_para['pubMsg']:
        if pub_msg['frequency'] > 0:
            SimulationConfig.pub_msgs.append(_MsgCfg(pub_msg['name'], pub_msg['frequency']))

    junction_scenarios = simulation_para['junctionRegion']  # 长度为0时表示场景覆盖路网所有交叉口
    if len(junction_scenarios):
        SimulationConfig.junction_region = junction_scenarios

    SimulationConfig.sim_time_step = simulation_para['simTimeStep']
    SimulationConfig.sim_time_limit = simulation_para['simTimeLimit'] if simulation_para['simTimeLimit'] > 0 else None
    SimulationConfig.warm_up_time = simulation_para['warmUpTime']

    # 通信连接参数
    conn_para = cfg.get('connection')
    if conn_para is not None:
        ConnectionConfig.broker = conn_para['broker']
        ConnectionConfig.port = conn_para['port']


