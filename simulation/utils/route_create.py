# -*- coding: utf-8 -*-
# @Time        : 2023/2/8 22:40
# @File        : route_create.py
# @Description :

import json
import re
import xml.etree.ElementTree as ET
from enum import Enum


class TwoWayDict(dict):
    def __init__(self, my_dict):
        super().__init__(my_dict)
        self.rev_dict = {v: k for k, v in my_dict.items()}

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.rev_dict.__setitem__(value, key)

    def pop(self, key):
        self.rev_dict.pop(self[key])
        super().pop(key)


class Direction(Enum):
    """描述十字路口进口道方位关系"""
    EAST = 1
    SOUTH = 2
    WEST = 4
    NORTH = 8

    def left(self):
        res = self.value << 1
        if res > 8:
            res /= 8
        return self.__class__(res)

    def straight(self):
        res = self.value << 2
        if res > 8:
            res /= 8
        return self.__class__(res)

    def right(self):
        res = self.value >> 1
        if res == 0:
            res = 8
        return self.__class__(res)

    leftturn = left
    rightturn = right


INTERSECTION = TwoWayDict({
    'HK3TRJVTf7': Direction.EAST,
    '4xnhzLD_vP': Direction.SOUTH,
    'AyE3bDm3uL': Direction.WEST,
    '0KUyAFxYUW': Direction.NORTH
})

maneuver_pattern = re.compile(r'maneuver(\s+)_\s{4,5}_(\s+)')


def update_route_file(curr_flow_data: dict, fp: str):
    tree = ET.parse(fp)
    root: ET.Element = tree.getroot()
    route_flows = root.findall('flow')

    movement_flow_data = {}
    for flow in curr_flow_data['stats']:
        assert flow['map_element_type'] == "DE_MovementStatInfo"
        movement_str = flow['map_element']['ext_id']
        match_res = maneuver_pattern.match(movement_str)
        turn = match_res.group(1)
        arm = match_res.group(2)

        arm_direction = INTERSECTION[arm]
        target_arm_direction = getattr(arm_direction, turn.lower())
        target_arm = INTERSECTION[target_arm_direction]
        movement_flow_data[arm, target_arm] = flow['volume']

    for (arm, target_arm), volume in movement_flow_data.items():
        route_flows

