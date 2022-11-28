# -*- coding: utf-8 -*-
# @Time        : 2022/11/18 21:33
# @File        : simulation_test.py
# @Description :

import unittest

from simulation.core import SimCore


class SimulationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sim = SimCore('../data/network/anting.sumocfg', '../data/network/anting.net.xml')
        sim.connect('121.36.231.253', 1883)
        sim.initialize('../data/network/route/arterial/arterial.rou.xml', '../data/network/detector_1.xml')
        cls.sim = sim

    def test_run(self):
        pass
