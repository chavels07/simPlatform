# -*- coding: utf-8 -*-
# @Time        : 2022/11/17 17:20
# @File        : main.py
# @Description : 仿真运行主程序

from simulation.connection.mqtt import MQTTConnection
from simulation.core import Simulation, AlgorithmEval
from simulation.lib.config import load_config, SetupConfig, ConnectionConfig

if __name__ == '__main__':
    load_config('../setting.json')
    connection = MQTTConnection()
    connection.connect(ConnectionConfig.broker, ConnectionConfig.port, None)

    algorithm_eval = AlgorithmEval()
    algorithm_eval.initialize_storage()
    algorithm_eval.sim.auto_activate_publish()
    algorithm_eval.start(connection)
