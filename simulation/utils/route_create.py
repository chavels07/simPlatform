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
    'HK3TRJVTf7': Direction.EAST,  # 572
    '4xnhzLD_vP': Direction.SOUTH,  # 1749
    'AyE3bDm3uL': Direction.WEST,  # 2271
    '0KUyAFxYUW': Direction.NORTH  # 6789
})

NODE_EDGE_MAPPING = {
    572: 'HK3TRJVTf7',
    1749: '4xnhzLD_vP',
    2271: 'AyE3bDm3uL',
    6789: '0KUyAFxYUW'
}

movements_edge_mapping = {}

maneuver_pattern = re.compile(r'maneuver(\s+)_\s{4,5}_(\s+)')


def edge_str_filter(edge: str):
    edge_major = edge.split('.')[0]
    return edge_major[1:] if edge_major.startswith('-') else edge_major


def update_route_file(flow_data: dict, fp: str):
    """
    根据实时TrafficFlow数据更新route文件流量
    Args:
        flow_data: 接收的flow数据
        fp: 原始route文件路径

    Returns:

    """
    tree = ET.parse(fp)
    root: ET.Element = tree.getroot()
    route_flows = root.findall('flow')
    movement_flow_data = {}
    curr_flow_data = flow_data['trafficFlow']['trafficFlowList'][0]
    for flow in curr_flow_data['stats']:
        # assert flow['mapElementType'] == "DE_MovementStatInfo"
        movement_str = flow['mapElement']['laneStatInfo']['extId']
        match_res = maneuver_pattern.match(movement_str)
        turn = match_res.group(1)
        edge = match_res.group(2)

        edge_direction = INTERSECTION[edge]
        target_edge_direction = getattr(edge_direction, turn.lower())
        target_edge = INTERSECTION[target_edge_direction]
        movement_flow_data[edge, target_edge] = int(flow['volume'] / 100)

    for flow_element in route_flows:
        attrs = flow_element.attrib
        from_edge = edge_str_filter(attrs['from'])
        to_edge = edge_str_filter(attrs['to'])
        key = (from_edge, to_edge)
        assert key in movement_flow_data

        flow_element.set('vehsPerHour', movement_flow_data[key])

    tree.write('../../data/network/real_flow.rou.xml')


def update_route_file_alternative(flow_data: dict, fp: str):
    """
    根据实时TrafficFlow数据更新route文件流量
    Args:
        flow_data: 接收的flow数据
        fp: 原始route文件路径

    Returns:

    """
    global movements_edge_mapping

    tree = ET.parse(fp)
    root: ET.Element = tree.getroot()
    route_flows = root.findall('flow')
    movement_flow_data = {}
    curr_flow_data = flow_data['trafficFlow'][0]
    for flow in curr_flow_data['stats']:
        if 'movementStatInfo' not in flow['mapElement']:
            continue

        movement_ext_id = flow['mapElement']['extId']
        edge, target_edge = movements_edge_mapping[movement_ext_id]
        movement_flow_data[edge, target_edge] = int(flow['volume'] / 100)

    for flow_element in route_flows:
        attrs = flow_element.attrib
        from_edge = edge_str_filter(attrs['from'])
        to_edge = edge_str_filter(attrs['to'])
        key = (from_edge, to_edge)
        assert key in movement_flow_data

        flow_element.set('vehsPerHour', movement_flow_data[key])

    tree.write('../../data/network/real_flow.rou.xml')


def read_MAP_from_file(map_fp: str):
    with open(map_fp, 'r', encoding='utf-8') as f:
        node_map = json.load(f)
    node = node_map['nodes'][0]
    global movements_edge_mapping

    for link in node['inLinks_ex']:
        upstream_node = link['upstreamNodeId']['id']
        upstream_edge = NODE_EDGE_MAPPING[upstream_node]
        for movement in link['movements_ex']:
            mov_ext_id = movement['ext_id']
            downstream_node = movement['remoteIntersection']['id']
            downstream_edge = NODE_EDGE_MAPPING[downstream_node]
            movements_edge_mapping[mov_ext_id] = (upstream_edge, downstream_edge)
