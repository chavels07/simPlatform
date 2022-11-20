# -*- coding: utf-8 -*-
# @Time        : 2022/11/17 17:20
# @File        : main.py
# @Description : 仿真运行主程序

from simulation.core import SimCore, AlgorithmEval




if __name__ == '__main__':
    algorithm_eval = AlgorithmEval()
    algorithm_eval.eval_task_from_directory(r'..\data\network\route\arterial', r'..\data\network\detector_1.xml')
    # simulation_core = SimCore()
    # simulation_core.initialize('')
    # simulation_core.connect('121.36.231.253', 1883)
    # simulation_core.run()
