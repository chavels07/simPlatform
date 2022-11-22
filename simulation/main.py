# -*- coding: utf-8 -*-
# @Time        : 2022/11/17 17:20
# @File        : main.py
# @Description : 仿真运行主程序

from simulation.core import SimCore, AlgorithmEval


if __name__ == '__main__':
    algorithm_eval = AlgorithmEval()
    algorithm_eval.connect('121.36.231.253', 1883)
    algorithm_eval.eval_task_from_directory(r'..\data\network\route\arterial', r'..\data\network\detector_1.xml', step_limit=300)

    # 等待start指令发出
    # algorithm_eval.eval_mode_setting(False, sce_dir_fp=r'..\data\network\route\arterial', detector_fp=r'..\data\network\detector_1.xml', step_limit=300)
    # algorithm_eval.loop_start()


    # simulation_core = SimCore()
    # simulation_core.initialize('')
    # simulation_core.connect('121.36.231.253', 1883)
    # simulation_core.run()
