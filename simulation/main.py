# -*- coding: utf-8 -*-
# @Time        : 2022/11/17 17:20
# @File        : main.py
# @Description : 仿真运行主程序

from simulation.core import SimCore, AlgorithmEval


if __name__ == '__main__':
    # algorithm_eval = AlgorithmEval(network_fp='../data/tmp/CJDLtest4.net.xml')
    algorithm_eval = AlgorithmEval(network_fp='../data/network/anting.net.xml')
    algorithm_eval.connect('121.36.231.253', 1883)
    algorithm_eval.initialize()

    # 初始化Storage TODO: 应该放在内部
    # algorithm_eval.sim.initialize_internal_storage(junction_list=('point93', 'point92', 'point98'))  # point93 在原路网中无信控
    algorithm_eval.sim.initialize_internal_storage(junction_list=('point79', 'point80', 'point81'))

    # 注册event
    algorithm_eval.auto_initialize_event()
    algorithm_eval.sim.activate_spat_publish()
    algorithm_eval.sim.activate_traffic_flow_publish()
    algorithm_eval.sim.activate_bsm_publish()

    # 欣朋仿真
    # algorithm_eval.sim_task_start(r'../data/tmp/flow.rou.xml', step_limit=1000)

    # 快速开始仿真
    algorithm_eval.sim_task_from_directory(r'..\data\network\route\arterial', r'..\data\network\detector_3.xml', step_limit=300)

    # 等待start指令发出
    # algorithm_eval.mode_setting(False, sce_dir_fp=r'..\data\network\route\arterial', detector_fp=r'..\data\network\detector_1.xml', step_limit=300)
    # algorithm_eval.loop_start()


    # simulation_core = SimCore()
    # simulation_core.initialize('')
    # simulation_core.connect('121.36.231.253', 1883)
    # simulation_core.run()
