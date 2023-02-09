# -*- coding: utf-8 -*-
# time: 2022/8/14 15:55
# file: SumoToMap_v3.py
# author: soul
# -*- coding: utf-8 -*-
# time: 2022/8/2 15:00
# file: SumoToMap.py
# author: soul

import sumolib
import datetime
import json
from tqdm import tqdm
from xml.etree.ElementTree import parse


node_id_global = 0


def MSG_MAP(nodes):
    """
    构建地图MSC_MAP结构体
    :param nodes: 交叉口（Node）列表
    :return: MAP字典
    """
    now = datetime.datetime.now()   # 获取当前日期时间
    first_day_of_year = datetime.datetime(now.year, 1, 1, 0, 0, 0)  # 当前年份第一天0时0分0秒
    ts = (now - first_day_of_year).total_seconds()      # 生成时刻为当前年份的第几秒
    msg_map = {"timeStamp": int(ts / 60), "nodes": nodes}

    return msg_map


def NodenameToId(node_name):
    """
    将交叉口名称（字符串）转换为id（整数）
    :param node_name: 交叉口名称
    :return: 交叉口id
    """
    global node_id_global
    if node_name != '':
        node_id_global += 1

    return node_id_global


def DF_Node(net_node, links, net):
    """
    构建交叉口DF_Node结构体
    :param net_node: 交叉口对象
    :param links: 进入该交叉口的所有道路Link列表
    :param net: 路网对象
    :return: Node字典
    """
    node_name = net_node.getID()    # 获取交叉口id/名称
    node_id = NodenameToId(node_name)   # 将字符串id转换为整型id

    (x, y) = net_node.getCoord()    # 获取交叉口xy坐标
    coord = net.convertXY2LonLat(x, y)      # 转换为经纬度坐标

    if net_node.getType() == "traffic_light":
        if_tl = "true"
    else:
        if_tl = "false"

    df_node = {
        "name": node_name,
        "id": {
            "region": 1,
            "id": node_id
        },
        "refPos": {
            "lat": int(10000000*coord[1]),
            "lon": int(10000000*coord[0])
        },
        "inLinks_ex": links,
        "trafficLight": if_tl
    }

    return df_node


def Road_Class(link_type):
    """
    获取MAP结构中规定的道路种类
    :param link_type: sumo中对应的道路类型
    :return: MAP结构中对应的道路类型
    """
    private_list = ['highway.residential', 'highway.service', 'highway.path', 'highway.track', 'highway.pedestrian',
                    'highway.cycleway', 'highway.living_street', 'highway.footway', 'highway.steps']
    if "tertiary" in link_type:
        return "BRANCH"
    elif link_type in private_list:
        return "PRIVATE"
    elif "secondary" in link_type:
        return "FEEDER"
    elif "primary" in link_type:
        return "ARTERIAL"
    elif ("motorway" in link_type) or ("trunk" in link_type):
        return "EXPRESSWAY"
    else:
        return "UNCLASSIFIED"


def DF_LinkEx(net_node, movements_ex, sections, net):
    """
    构建道路DF_LinkEx结构体
    :param net_node: Link对应的交叉口对象
    :param movements_ex: DF_MovementEx结构体列表
    :param sections: DF_Section结构体列表
    :param net: 路网对象
    :return: Link字典
    """
    road_point_list = []    # 构成道路参考线的坐标点列表
    coord_list = [net.getEdge(sections[0]['ext_id']).getShape()[0]]
    intersection_lon = net.convertXY2LonLat(net_node.getCoord()[0], net_node.getCoord()[1])[0] * 10000000
    intersection_lat = net.convertXY2LonLat(net_node.getCoord()[0], net_node.getCoord()[1])[1] * 10000000
    for section in sections:
        section_obj = net.getEdge(section['ext_id'])
        xy_coord = section_obj.getShape()[1:]
        coord_list += xy_coord
    for xy_coord in coord_list:
        node_lon = net.convertXY2LonLat(xy_coord[0], xy_coord[1])[0] * 10000000
        node_lat = net.convertXY2LonLat(xy_coord[0], xy_coord[1])[1] * 10000000
        road_point_list.append({
            "posOffset": {
                "offsetLL": {
                    "lon": int(node_lon - intersection_lon),
                    "lat": int(node_lat - intersection_lat)
                }
            }
        })

    direction_dict = lambda s, x, y: {
        0.414213 < s <= 2.414213 and x > 0: "NE", -0.414213 < s <= 0.4142123 and x > 0: "E", -2.4142123 < s <= -0.414213
        and x > 0: "SE", 0.414213 < s <= 2.414213 and x < 0: "SW", -0.414213 < s <= 0.414213 and x < 0: "W",
        -2.414213 < s <= -0.414213 and x < 0: "NW", (s > 2.414213 or s < -2.414213) and y > 0: "N", (s > 2.414213 or
                                                                                                     s < -2.414213) and y < 0: "S"
    }   # 根据斜率确定Link方向

    first_section = net.getEdge(sections[0]["ext_id"])  # 获取section列表中的第一个section
    speed_limit = int(first_section.getSpeed() / 0.02)
    upstreamNode = first_section.getFromNode()      # 第一个section的起点，作为Link的起点
    link_name = upstreamNode.getID() + "_To_" + net_node.getID()
    upstreamNode_id = NodenameToId(upstreamNode.getID())    # 将上游交叉口字符串id转换为对应的整型id

    delta_x = net_node.getCoord()[0]-upstreamNode.getCoord()[0]
    delta_y = net_node.getCoord()[1]-upstreamNode.getCoord()[1]
    if delta_x == 0:
        if delta_y > 0:
            direction = "N"
        else:
            direction = "S"
    else:
        slope = delta_y / delta_x
        direction = direction_dict(slope, delta_x, delta_y)[True]

    link_type = Road_Class(first_section.getType())     # 以第一个section的道路类型作为Link的类型
    link_length = 0

    # 计算Link长度（将各section的长度相加）
    for section in sections:
        section_obj = net.getEdge(section["ext_id"])
        link_length += section_obj.getLength()

    df_linkex = {
        "name": link_name,
        "upstreamNodeId": {
            "region": 1,
            "id": upstreamNode_id
        },
        "speedLimits": speed_limit,
        "refLine": road_point_list,
        "movements_ex": movements_ex,
        "sections": sections,
        "ext_id": link_name,
        "direction": direction,
        "road_class": link_type,
        "length": int(link_length)
    }

    return df_linkex


def Edge_Direction(x1, y1, x2, y2, direction):
    """
    获取进口道转向对应编号（1-16）,从正北方向顺时针编号,一个方向存在四个转向(左,直,右,行人)
    :param x1: edge起点横坐标
    :param y1: edge起点纵坐标
    :param x2: edge终点横坐标
    :param y2: edge终点纵坐标
    :param direction: 转向
    :return: 交叉口转向编号
    """
    delta_x = x2 - x1
    delta_y = y2 - y1

    # 道路方向为正南或正北
    if delta_x == 0 and delta_y > 0:
        judge = lambda x: {x == 'l': '9', x == 's': '10', x == 'r': '11'}
        return judge(direction)[True]
    elif delta_x == 0 and delta_y < 0:
        judge = lambda x: {x == 'l': '1', x == 's': '2', x == 'r': '3'}
        return judge(direction)[True]
    # 正南正北外的其他方向
    else:
        slope = delta_y / delta_x
        # 南进口
        if (slope > 1 or slope < -1) and delta_y > 0:
            judge = lambda x: {x == 'l': '9', x == 's': '10', x == 'r': '11'}
            return judge(direction)[True]
        # 北进口
        elif (slope > 1 or slope < -1) and delta_y < 0:
            judge = lambda x: {x == 'l': '1', x == 's': '2', x == 'r': '3'}
            return judge(direction)[True]
        # 西进口
        elif -1 < slope < 1 and delta_x > 0:
            judge = lambda x: {x == 'l': '13', x == 's': '14', x == 'r': '15'}
            return judge(direction)[True]
        # 东进口
        else:
            judge = lambda x: {x == 'l': '5', x == 's': '6', x == 'r': '7'}
            return judge(direction)[True]


def DF_MovementEx(net_node, remote_node, incoming_section, direction, phase_id=0):
    """
    构建上下游连接器DF_MovementEx
    :param net_node: 交叉口对象
    :param remote_node: 下游交叉口对象
    :param incoming_section: 直接进入交叉口的section
    :param direction: 转向
    :param phase_id: 转向对应的phaseId，从1开始，若无信控，则为0
    :return: Movement字典
    """
    remote_node_id = NodenameToId(remote_node.getID())  # 下游交叉口字符串id转换为整型id
    direct_to_behavior = lambda x: {x == 's': 1, x == 'l': 1 << 1, x == 'r': 1 << 2}     # 转向对应behavior编号，采用bit位的方式表示maneuver

    coord_list = incoming_section.getShape()
    (x1, y1) = coord_list[-2]
    (x2, y2) = coord_list[-1]

    # ext_id = net_node.getID() + "_" + Edge_Direction(x1, y1, x2, y2, direction)     # Movement_Id
    ext_id = Edge_Direction(x1, y1, x2, y2, direction)     # Movement_Id

    movement_ex = {
        "remoteIntersection": {
            "region": 1,
            "id": remote_node_id
        },
        "phaseId": phase_id,
        "turnDirection": {
            "behavior": direct_to_behavior(direction.lower())[True]
        },
        "ext_id": ext_id
    }

    return movement_ex


def DF_Section(edge_obj, lanes):
    """
    构建DF_Section结构体
    :param edge_obj: section路段对象
    :param lanes: section包含的车道列表
    :return: section字典
    """
    ext_id = edge_obj.getID()

    section = {
        "secID": 1,
        "lanes": lanes,
        "ext_id": ext_id
    }

    return section


def DF_LaneEx(net, net_node, lane_obj, turnbehavior, connectsTo_ex, intersection=False):
    """
    构建DF_LaneEx结构体
    :param net: 路网对象
    :param net_node: 对应交叉口对象
    :param lane_obj: 车道对象
    :param turnbehavior: 转向行为编号
    :param connectsTo_ex: DF_ConnectionEx结构体列表
    :param intersection: intersection标识，表征车道是否与交叉口直接连接
    :return: lane字典
    """
    lane_point_list = []  # 构成道路参考线的坐标点列表
    coord_list = lane_obj.getShape()
    intersection_lon = net.convertXY2LonLat(net_node.getCoord()[0], net_node.getCoord()[1])[0] * 10000000
    intersection_lat = net.convertXY2LonLat(net_node.getCoord()[0], net_node.getCoord()[1])[1] * 10000000

    for xy_coord in coord_list:
        node_lon = net.convertXY2LonLat(xy_coord[0], xy_coord[1])[0] * 10000000
        node_lat = net.convertXY2LonLat(xy_coord[0], xy_coord[1])[1] * 10000000
        lane_point_list.append({
            "posOffset": {
                "offsetLL": {
                    "lon": int(node_lon - intersection_lon),
                    "lat": int(node_lat - intersection_lat)
                }
            }
        })

    lane_num = len(lane_obj.getEdge().getLanes())
    lane_index = int(lane_obj.getIndex())
    if lane_num % 2 == 0:
        if lane_index < lane_num / 2:
            lane_ref_id = lane_index - int(lane_num / 2)
        else:
            lane_ref_id = lane_index + 1 - int(lane_num / 2)
    else:
        lane_ref_id = lane_index - int(lane_num / 2)
    lane_width = lane_obj.getWidth()    # 车道宽度

    if lane_obj.allows("passenger"):
        lanetype_type = "DF_LaneAttributesVehicle"
        lanetype = 0
        sharewith = 3
    elif lane_obj.allows("bicycle"):
        lanetype_type = "DF_LaneAttributesBike"
        lanetype = 2
        sharewith = 7
    elif lane_obj.allows("rail"):
        lanetype_type = "DF_LaneAttributesTrackedVehicle"
        lanetype = 6
        sharewith = 8
    else:
        lanetype_type = "DF_LaneAttributesCrosswalk"
        lanetype = 1
        sharewith = 9

    ext_id = lane_obj.getID()

    # 交叉口进口车道
    if intersection:
        lane = {
            "laneRefId": lane_ref_id,
            "refLine": lane_point_list,
            "laneWidth": lane_width,
            "laneAttributes": {
                "shareWith": {
                    "shareWith": sharewith
                },
                "laneType_type": lanetype_type,
                "laneType": {
                    "vehicle": lanetype
                }
            },
            "maneuvers": {
                "behavior": turnbehavior
            },
            "connectsTo_ex": connectsTo_ex,
            "ext_id": ext_id
        }
    # 路段中间车道
    else:
        lane = {
            "laneRefId": lane_ref_id,
            "refLine": lane_point_list,
            "laneWidth": lane_width,
            "laneAttributes": {
                "shareWith": {
                    "shareWith": sharewith
                },
                "laneType_type": lanetype_type,
                "laneType": {
                    "vehicle": lanetype
                }
            },
            "connectsTo_ex": connectsTo_ex,
            "ext_id": ext_id
        }

    return lane


def DF_ConnectionEx(remote_node, connectinglanes, turndirection, intersection=False):
    """
    构建DF_ConnectionEx结构体
    :param remote_node: 下游交叉口对象
    :param connectinglanes: 下游连接车道列表
    :param turndirection: 转向
    :param intersection: intersection标识，表征车道是否与交叉口直接连接
    :return: connection字典
    """
    # 交叉口进口车道
    if intersection:
        connection = {
            "remoteIntersection": {
                "region": 1,
                "id": NodenameToId(remote_node.getID())
            },
            "connectingLane": connectinglanes,
            "turnDirection": turndirection,
            "ext_id": "connect_" + connectinglanes[0]["ext_id"]
        }
    # 路段中间车道
    elif (not intersection) and len(connectinglanes) > 0:
        connection = {
            "connectingLane": connectinglanes,
            "ext_id": "connect_" + connectinglanes[0]["ext_id"]
        }
    else:
        connection = {
            "connectingLane": connectinglanes,
            "ext_id": "connect_none"
        }

    return connection


def DF_ConnectingLaneEx(lane_obj):
    """
    构建DF_ConnectingLaneEx结构体
    :param lane_obj: 车道Lane对象
    :return: connectionlane字典
    """
    target_lane = int(lane_obj.getIndex())      # 车道index
    connectinglanewidth = lane_obj.getWidth()   # 车道宽度
    ext_id = lane_obj.getID()

    connectinglane = {
        "target_section": 1,
        "target_lane": target_lane,
        "connectingLaneWidth": connectinglanewidth,
        "ext_id": ext_id
    }

    return connectinglane


def SumoToMSG(file_name):
    net = sumolib.net.readNet(file_name)  # 读取路网
    data = parse(file_name)
    tl_logics = data.iterfind("tlLogic")
    tl_dict = {}
    for tl_logic in tl_logics:
        tl_dict[tl_logic.get('id')] = tl_logic
    nodes = net.getNodes()  # 获取路网中的所有节点
    intersections = []  # 用于存储路网中的交叉口
    # direct_to_behavior = lambda x: {x == 's': 0, x == 'l': 1, x == 'r': 2}     # 转向对应behavior取值

    for node in nodes:
        # 如果节点对应的上游节点有两个以上，则将其判断为交叉口
        if len(node.getIncoming()) != 2 or len(node.getNeighboringNodes()) > 2:
            intersections.append(node)

    node_list = []  # 交叉口列表
    for intersection in tqdm(intersections):
        try:
            if intersection.getType() == 'traffic_light':
                tlsId = intersection.getConnections()[0].getTLSID()
                # tlsId = intersection.getIncoming()[0].getLanes()[0].getOutgoing()[0].getTLSID()
                incoming_sections = intersection.getIncoming()  # 获取进入该交叉口的所有Edge（Section）
                link_list = []  # 道路列表
                link_name_list = []

                tl_logic = tl_dict[tlsId]
                state_list = []
                for phase in tl_logic.iterfind("phase"):
                    state = phase.get('state')
                    if 'G' in state or 'g' in state:
                        state_list.append(state)
                # 对从各方向进入交叉口的Edge（Section）进行遍历
                for incoming_section in incoming_sections:

                    temp_incoming_section = incoming_section  # 直接进入交叉口的section
                    from_node = temp_incoming_section.getFromNode()  # 获取section的起点
                    incoming_section_list = [temp_incoming_section]  # 存储从当前交叉口到上游交叉口之间的sections

                    # 当section起点的上游节点数小于3，说明该section起点不是交叉口，继续向上依次寻找（顺序为从下游至上游）直到section起点为交叉口
                    while len(from_node.getIncoming()) < 3 and len(from_node.getOutgoing()) < 3 and len(
                            from_node.getNeighboringNodes()) < 3:
                        # print(from_node.getID(), from_node.getIncoming(), len(from_node.getNeighboringNodes()))
                        if len(from_node.getNeighboringNodes()) == 1:
                            break
                        try:
                            if len(from_node.getIncoming()) == 1 and from_node.getIncoming()[0].getFromNode() == \
                                    intersection:
                                break
                        except IndexError:
                            pass
                        if len(from_node.getIncoming()) == 0:
                            break
                        for direction_section in from_node.getIncoming():
                            # 保证顺着上游向上查找
                            if direction_section.getFromNode() != temp_incoming_section.getToNode():
                                temp_incoming_section = direction_section  # 更新section
                                break
                        from_node = temp_incoming_section.getFromNode()  # 更新section起点
                        incoming_section_list.append(temp_incoming_section)  # 向列表中添加section
                    incoming_section_list.reverse()  # 将上游section列表按从上游到下游的顺序排列

                    # 获取下游转向关系movement
                    remoteintersection_list = []  # 下游交叉口列表
                    movement_ex_list = []  # 转向列表
                    for lane in incoming_section.getLanes():
                        connections = lane.getOutgoing()  # 获取车道对应的所有连接器
                        for connection in connections:
                            connection_index = connection.getTLLinkIndex()
                            direction = connection.getDirection().lower()  # 获取连接器方向
                            # 忽略掉头
                            if direction == 't':
                                continue
                            # 寻找转向到达的交叉口
                            else:
                                tolane = connection.getToLane()
                                tolane_edge = tolane.getEdge()
                                tolane_edge_endpoint = tolane_edge.getToNode()
                                while len(tolane_edge_endpoint.getOutgoing()) < 3 and len(
                                        tolane_edge_endpoint.getIncoming()) < 3 and len(
                                        tolane_edge_endpoint.getNeighboringNodes()) < 3:
                                    # print(tolane_edge_endpoint.getID(), tolane_edge_endpoint.getOutgoing(),
                                    #       len(tolane_edge_endpoint.getNeighboringNodes()))
                                    if len(tolane_edge_endpoint.getNeighboringNodes()) == 1:
                                        break
                                    if len(tolane_edge_endpoint.getOutgoing()) == 0:
                                        break
                                    for direction_tolane_edge in tolane_edge_endpoint.getOutgoing():
                                        # 保证顺着下游向下寻找
                                        if direction_tolane_edge.getToNode() != tolane_edge.getFromNode():
                                            tolane_edge = direction_tolane_edge
                                            tolane_edge_endpoint = tolane_edge.getToNode()
                                            break

                                remoteintersection = tolane_edge_endpoint
                            if remoteintersection in remoteintersection_list:
                                continue
                            else:
                                phase_id = 0
                                for i, tl_state in enumerate(state_list):
                                    connection_state = tl_state[connection_index]
                                    if connection_state == 'g' or connection_state == 'G':
                                        phase_id = i + 1
                                remoteintersection_list.append(remoteintersection)
                                movement_ex = DF_MovementEx(intersection, remoteintersection, incoming_section,
                                                            direction, phase_id)
                                movement_ex_list.append(movement_ex)

                    # 对incoming_section_list进行遍历
                    section_list = []  # section列表
                    for i, incoming_section_1 in enumerate(incoming_section_list):
                        lanes_list = []  # 车道列表

                        # 中间路段
                        if i < len(incoming_section_list) - 1:
                            lanes = incoming_section_1.getLanes()  # 获取section的车道
                            for lane in lanes:
                                connection_ex_list = []  # connection列表
                                connections = lane.getOutgoing()  # 获取车道对应连接器
                                connectinglane_ex_list = []  # connectinglane列表
                                for connection in connections:
                                    outgoinglane = connection.getToLane()
                                    connectinglane_ex_list.append(DF_ConnectingLaneEx(outgoinglane))
                                connection_ex = DF_ConnectionEx(None, connectinglane_ex_list, None)
                                connection_ex_list.append(connection_ex)
                                lane_ex = DF_LaneEx(net, intersection, lane, None, connection_ex_list)
                                lanes_list.append(lane_ex)
                        # 直接与交叉口连接的路段
                        else:
                            lanes = incoming_section_1.getLanes()
                            for lane in lanes:
                                connection_ex_list = []  # connection列表
                                direction_lane_dict = {1: [[]], 2: [[]], 4: [[]]}
                                # 第二层列表存储各转向对应下游车道，第一层列表第二项存储下游交叉口
                                connections = lane.getOutgoing()
                                for connection in connections:
                                    direction1 = connection.getDirection().lower()
                                    direction = 1 if direction1 == 's' else 1 << 1 if direction1 == 'l' else 1 << 2 if direction1 == \
                                        'r' else direction1
                                    if direction == "t":
                                        continue
                                    else:
                                        outgoinglane = connection.getToLane()
                                        outgoinglane_edge = outgoinglane.getEdge()
                                        outgoinglane_edge_endpoint = outgoinglane_edge.getToNode()
                                        while len(outgoinglane_edge_endpoint.getOutgoing()) < 3 and len(
                                                outgoinglane_edge_endpoint.getIncoming()) < 3 and len(
                                                outgoinglane_edge_endpoint.getNeighboringNodes()) < 3:
                                            # print(outgoinglane_edge_endpoint.getID(), outgoinglane_edge_endpoint.getOutgoing(),
                                            #       len(outgoinglane_edge_endpoint.getNeighboringNodes()))
                                            if len(outgoinglane_edge_endpoint.getNeighboringNodes()) == 1:
                                                break
                                            if len(outgoinglane_edge_endpoint.getOutgoing()) == 0:
                                                break
                                            for direction_tolane_edge in outgoinglane_edge_endpoint.getOutgoing():
                                                # 保证顺着下游向下寻找
                                                if direction_tolane_edge.getToNode() != outgoinglane_edge.getFromNode():
                                                    outgoinglane_edge = direction_tolane_edge
                                                    outgoinglane_edge_endpoint = outgoinglane_edge.getToNode()
                                                    break
                                        remote_intersection = outgoinglane_edge_endpoint
                                        direction_lane_dict[direction][0].append(DF_ConnectingLaneEx(outgoinglane))
                                        direction_lane_dict[direction].append(remote_intersection)
                                turn_behavior = ''
                                for direct, connectinglanes_remoteintersection in direction_lane_dict.items():
                                    if len(connectinglanes_remoteintersection[0]) != 0:
                                        turn_behavior = direct  # direct_to_behavior(direct)[True]
                                        connection_ex_list.append(DF_ConnectionEx(connectinglanes_remoteintersection[1],
                                                                                  connectinglanes_remoteintersection[0],
                                                                                  direct,
                                                                                  True))

                                # 构建lane结构体
                                lane_ex = DF_LaneEx(net, intersection, lane, turn_behavior, connection_ex_list, True)
                                lanes_list.append(lane_ex)

                        # 构建section结构体
                        section = DF_Section(incoming_section_1, lanes_list)
                        section_list.append(section)

                    # 构建link结构体
                    link = DF_LinkEx(intersection, movement_ex_list, section_list, net)
                    temp_i = 0
                    if link['name'] in link_name_list:
                        temp_i += 1
                        link['name'] = link['name'] + "_" + str(temp_i)
                        link['ext_id'] = link['name']
                        link_name_list.append(link['name'])
                        link_list.append(link)
                    else:
                        link_name_list.append(link['name'])
                        link_list.append(link)

                # 构建node结构体
                node = DF_Node(intersection, link_list, net)
                node_list.append(node)

            else:
                incoming_sections = intersection.getIncoming()  # 获取进入该交叉口的所有Edge（Section）
                link_list = []      # 道路列表
                link_name_list = []

                # 对从各方向进入交叉口的Edge（Section）进行遍历
                for incoming_section in incoming_sections:

                    temp_incoming_section = incoming_section    # 直接进入交叉口的section
                    from_node = temp_incoming_section.getFromNode()     # 获取section的起点
                    incoming_section_list = [temp_incoming_section]      # 存储从当前交叉口到上游交叉口之间的sections

                    # 当section起点的上游节点数小于3，说明该section起点不是交叉口，继续向上依次寻找（顺序为从下游至上游）直到section起点为交叉口
                    while len(from_node.getIncoming()) < 3 and len(from_node.getOutgoing()) < 3 and len(
                            from_node.getNeighboringNodes()) < 3:
                        # print(from_node.getID(), from_node.getIncoming(), len(from_node.getNeighboringNodes()))
                        if len(from_node.getNeighboringNodes()) == 1:
                            break
                        try:
                            if len(from_node.getIncoming()) == 1 and from_node.getIncoming()[0].getFromNode() == \
                                    intersection:
                                break
                        except IndexError:
                            pass
                        if len(from_node.getIncoming()) == 0:
                            break
                        for direction_section in from_node.getIncoming():
                            # 保证顺着上游向上查找
                            if direction_section.getFromNode() != temp_incoming_section.getToNode():
                                temp_incoming_section = direction_section  # 更新section
                                break
                        from_node = temp_incoming_section.getFromNode()       # 更新section起点
                        incoming_section_list.append(temp_incoming_section)      # 向列表中添加section
                    incoming_section_list.reverse()     # 将上游section列表按从上游到下游的顺序排列

                    # 获取下游转向关系movement
                    remoteintersection_list = []  # 下游交叉口列表
                    movement_ex_list = []  # 转向列表
                    for lane in incoming_section.getLanes():
                        connections = lane.getOutgoing()    # 获取车道对应的所有连接器
                        for connection in connections:
                            direction = connection.getDirection().lower()   # 获取连接器方向
                            # 忽略掉头
                            if direction == 't':
                                continue
                            # 寻找转向到达的交叉口
                            else:
                                tolane = connection.getToLane()
                                tolane_edge = tolane.getEdge()
                                tolane_edge_endpoint = tolane_edge.getToNode()
                                counter = 0
                                while len(tolane_edge_endpoint.getOutgoing()) < 3 and len(
                                        tolane_edge_endpoint.getIncoming()) < 3 and len(
                                        tolane_edge_endpoint.getNeighboringNodes()) < 3:
                                    # print(tolane_edge_endpoint.getID(), tolane_edge_endpoint.getOutgoing(),
                                    #       len(tolane_edge_endpoint.getNeighboringNodes()))
                                    if len(tolane_edge_endpoint.getNeighboringNodes()) == 1:
                                        break
                                    if len(tolane_edge_endpoint.getOutgoing()) == 0:
                                        break
                                    for direction_tolane_edge in tolane_edge_endpoint.getOutgoing():
                                        # 保证顺着下游向下寻找
                                        if direction_tolane_edge.getToNode() != tolane_edge.getFromNode():
                                            tolane_edge = direction_tolane_edge
                                            tolane_edge_endpoint = tolane_edge.getToNode()
                                            break
                                    # TODO: test无限循环
                                    if counter > 100:
                                        tolane_edge = direction_tolane_edge
                                        tolane_edge_endpoint = tolane_edge.getToNode()
                                        break
                                    counter += 1


                                remoteintersection = tolane_edge_endpoint
                            if remoteintersection in remoteintersection_list:
                                continue
                            else:
                                remoteintersection_list.append(remoteintersection)
                                movement_ex = DF_MovementEx(intersection, remoteintersection, incoming_section, direction)
                                movement_ex_list.append(movement_ex)

                    # 对incoming_section_list进行遍历
                    section_list = []   # section列表
                    for i, incoming_section_1 in enumerate(incoming_section_list):
                        lanes_list = []     # 车道列表

                        # 中间路段
                        if i < len(incoming_section_list) - 1:
                            lanes = incoming_section_1.getLanes()   # 获取section的车道
                            for lane in lanes:
                                connection_ex_list = []     # connection列表
                                connections = lane.getOutgoing()    # 获取车道对应连接器
                                connectinglane_ex_list = []     # connectinglane列表
                                for connection in connections:
                                    outgoinglane = connection.getToLane()
                                    connectinglane_ex_list.append(DF_ConnectingLaneEx(outgoinglane))
                                connection_ex = DF_ConnectionEx(None, connectinglane_ex_list, None)
                                connection_ex_list.append(connection_ex)
                                lane_ex = DF_LaneEx(net, intersection, lane, None, connection_ex_list)
                                lanes_list.append(lane_ex)
                        # 直接与交叉口连接的路段
                        else:
                            lanes = incoming_section_1.getLanes()
                            for lane in lanes:
                                connection_ex_list = []     # connection列表
                                direction_lane_dict = {'l': [[]], 's': [[]], 'r': [[]]}
                                # 第二层列表存储各转向对应下游车道，第一层列表第二项存储下游交叉口
                                connections = lane.getOutgoing()
                                for connection in connections:
                                    direction = connection.getDirection().lower()
                                    if direction == "t":
                                        continue
                                    else:
                                        outgoinglane = connection.getToLane()
                                        outgoinglane_edge = outgoinglane.getEdge()
                                        outgoinglane_edge_endpoint = outgoinglane_edge.getToNode()
                                        counter = 0
                                        while len(outgoinglane_edge_endpoint.getOutgoing()) < 3 and len(
                                                outgoinglane_edge_endpoint.getIncoming()) < 3 and len(
                                                outgoinglane_edge_endpoint.getNeighboringNodes()) < 3:
                                            # print(outgoinglane_edge_endpoint.getID(), outgoinglane_edge_endpoint.getOutgoing(),
                                            #       len(outgoinglane_edge_endpoint.getNeighboringNodes()))
                                            if len(outgoinglane_edge_endpoint.getNeighboringNodes()) == 1:
                                                break
                                            if len(outgoinglane_edge_endpoint.getOutgoing()) == 0:
                                                break
                                            for direction_tolane_edge in outgoinglane_edge_endpoint.getOutgoing():
                                                # 保证顺着下游向下寻找
                                                if direction_tolane_edge.getToNode() != outgoinglane_edge.getFromNode():
                                                    outgoinglane_edge = direction_tolane_edge
                                                    outgoinglane_edge_endpoint = outgoinglane_edge.getToNode()
                                                    break
                                            if counter > 100:
                                                outgoinglane_edge = direction_tolane_edge
                                                outgoinglane_edge_endpoint = outgoinglane_edge.getToNode()
                                                break
                                            counter += 1
                                        remote_intersection = outgoinglane_edge_endpoint
                                        direction_lane_dict[direction][0].append(DF_ConnectingLaneEx(outgoinglane))
                                        direction_lane_dict[direction].append(remote_intersection)
                                turn_behavior = ''
                                for direct, connectinglanes_remoteintersection in direction_lane_dict.items():
                                    if len(connectinglanes_remoteintersection[0]) != 0:
                                        turn_behavior = direct  # direct_to_behavior(direct)[True]
                                        connection_ex_list.append(DF_ConnectionEx(connectinglanes_remoteintersection[1],
                                                                                  connectinglanes_remoteintersection[0], direct,
                                                                                  True))

                                # 构建lane结构体
                                lane_ex = DF_LaneEx(net, intersection, lane, turn_behavior, connection_ex_list, True)
                                lanes_list.append(lane_ex)

                        # 构建section结构体
                        section = DF_Section(incoming_section_1, lanes_list)
                        section_list.append(section)

                    # 构建link结构体
                    link = DF_LinkEx(intersection, movement_ex_list, section_list, net)
                    temp_i = 0
                    if link['name'] in link_name_list:
                        temp_i += 1
                        link['name'] = link['name'] + "_" + str(temp_i)
                        link['ext_id'] = link['name']
                        link_name_list.append(link['name'])
                        link_list.append(link)
                    else:
                        link_name_list.append(link['name'])
                        link_list.append(link)

                # 构建node结构体
                node = DF_Node(intersection, link_list, net)
                node_list.append(node)
        except Exception as e:
            continue

    # 构建map结构体
    msg_map = MSG_MAP(node_list)

    return msg_map


if __name__ == '__main__':
    msg_map_dict = SumoToMSG('../../data/network/anting.net.xml')  # ../../data/tmp/display/yutanglu1207.net.xml
    # msg_map_dict = SumoToMSG('D:/Desktop/sumo项目/安研路安拓路-新/anting.net.xml')
    dict_json = json.dumps(msg_map_dict, indent=2)
    with open('yutanglu.json', 'w+') as file:
        file.write(dict_json)
