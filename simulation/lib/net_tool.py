# -*- coding: utf-8 -*-
# @Time        : 2022/12/17 21:27
# @File        : net_tool.py
# @Description :

import math
from collections import defaultdict
from enum import Enum
from typing import Tuple, List, Dict, Set, Optional, Iterable

import sumolib


class Direction(Enum):
    WEST = 1
    SOUTH = 2
    EAST = 3
    NORTH = 4

    @property
    def opposite_direction(self):
        return Direction((self.value + 1) % 4 + 1)

    @classmethod
    def from_angle(cls, angle: float) -> Tuple['Direction', Optional['Direction']]:
        """
        从向量来判断方位，默认上北下南
        Args:
            angle:

        Returns: 1) 主方位 2) 副方位, 方向为正时返回None

        """
        _orientation = {
            0: (cls.NORTH, cls.EAST),
            1: (cls.EAST, cls.NORTH),
            2: (cls.EAST, cls.SOUTH),
            3: (cls.SOUTH, cls.EAST),
            4: (cls.SOUTH, cls.WEST),
            5: (cls.WEST, cls.SOUTH),
            6: (cls.WEST, cls.NORTH),
            7: (cls.NORTH, cls.WEST)
        }
        div, mod = divmod(angle, 45)
        major_orientation, vice_orientation = _orientation[int(div)]
        if angle % 45 == 0:
            vice_orientation = None
        return major_orientation, vice_orientation


class Turn(Enum):
    STRAIGHT = 's'
    LEFT = 'l'
    RIGHT = 'r'
    TURN = 't'
    PARTIALLY_LEFT = 'L'
    PARTIALLY_RIGHT = 'R'

    def ignore_upper(self):
        value = self.value
        if value.isupper():
            value = value.lower()
        return self.__class__(value)


class Entry:
    def __init__(self):
        self.conn_index_info: Dict[Turn, List[int]] = defaultdict(list)

    def __getitem__(self, item):
        if isinstance(item, Turn):
            return self.conn_index_info[item]
        else:
            raise TypeError('get item method only supports Turn instance')

    def add_connection(self, turn: Turn, connection_idx: int):
        """添加connection与turn的映射"""
        self.conn_index_info[turn].append(connection_idx)

    def is_complete(self):
        pass


class JunctionConns:
    MOVEMENT_MAPPING = {
        1: (Direction.SOUTH, Turn.LEFT),
        2: (Direction.SOUTH, Turn.STRAIGHT),
        3: (Direction.SOUTH, Turn.RIGHT),
        4: (Direction.EAST, Turn.LEFT),
        5: (Direction.EAST, Turn.STRAIGHT),
        6: (Direction.EAST, Turn.RIGHT),
        7: (Direction.NORTH, Turn.LEFT),
        8: (Direction.NORTH, Turn.STRAIGHT),
        9: (Direction.NORTH, Turn.RIGHT),
        10: (Direction.WEST, Turn.LEFT),
        11: (Direction.WEST, Turn.STRAIGHT),
        12: (Direction.WEST, Turn.RIGHT),
        20: (Direction.SOUTH, Turn.TURN),  # TODO:掉头临时定义，需要确定
        21: (Direction.EAST, Turn.TURN),
        22: (Direction.NORTH, Turn.TURN),
        23: (Direction.WEST, Turn.TURN)
    }

    # movement mapping的逆映射
    INVERSE_MOVEMENT_MAPPING = {value: key for key, value in MOVEMENT_MAPPING.items()}

    def __init__(self):
        self.entries: Dict[Direction, Entry] = defaultdict(Entry)
        self.movement_of_connection: Dict[int, int] = {}

    def __len__(self):
        connection_count = 0
        for entry in self.entries.values():
            for turn_conn in entry.conn_index_info.values():
                connection_count += len(turn_conn)
        return connection_count

    def add_connection(self, direction: Direction, turn: Turn, conn_idx: int):
        self.entries[direction][turn].append(conn_idx)
        self.movement_of_connection[conn_idx] = self.INVERSE_MOVEMENT_MAPPING[(direction, turn.ignore_upper())]

    def get_connections_movements_str(self, connection_indexes: List[int]) -> List[str]:
        movement_set = {str(self.movement_of_connection[index]) for index in connection_indexes}
        return list(movement_set)

    def get_movement_connections(self, movement: int) -> Optional[List[int]]:
        res = self.MOVEMENT_MAPPING.get(movement)
        if res is None:
            return None

        direction, turn = res
        entry = self.entries.get(direction)
        if entry is None:
            return None

        connections = entry.conn_index_info.get(turn)
        if connections is None:
            return None

        return connections


def get_vector_angle_degree(x: float, y: float):
    """
    计算向量与正北方向的夹角
    Args:
        x:
        y:

    Returns: 0~360 degree

    """
    # 在y轴上
    if x == 0:
        if y > 0:
            return 0
        else:
            return 180

    degree = math.degrees(math.atan(y / x))
    if x < 0:
        degree = 270 - degree  # 旋转到0-360°内
    else:
        degree = 90 - degree
    return degree


def get_entry_angle_orientation(edge: sumolib.net.edge.Edge, junction: sumolib.net.node.Node):
    """

    Args:
        edge:
        junction:

    Returns:

    """
    junction_x, junction_y = junction.getCoord()
    shape = edge.getShape()
    assert len(shape) >= 2
    last_section_start, last_section_end = shape[-2:]  # link最后一个section起点到终点
    edge_x, edge_y = last_section_start
    entry_vec_x, entry_vec_y = edge_x - junction_x, edge_y - junction_y
    degree = get_vector_angle_degree(entry_vec_x, entry_vec_y)
    return degree, Direction.from_angle(degree)


def entry_movement_sorted(connections: Iterable[sumolib.net.connection.Connection],
                          junction: sumolib.net.node.Node) -> JunctionConns:
    junction_connections = JunctionConns()
    for connection in connections:
        from_edge = connection.getFrom()  # 提取进口道
        _, (major_orientation, vice_orientation) = get_entry_angle_orientation(from_edge, junction)
        turn = Turn(connection.getDirection())
        connection_index = connection.getTLLinkIndex()
        junction_connections.add_connection(major_orientation, turn, connection_index)

    return junction_connections

