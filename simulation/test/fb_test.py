# -*- coding: utf-8 -*-
# @Time        : 2022/12/5 15:21
# @File        : fb_test.py
# @Description :

import json

from simulation.connection.python_fbconv.fbconv import FBConverter

fb_converter = FBConverter()
msg = {'ptcType': 1, 'ptcId': 11000, 'source': 1, 'device': [1], 'moy': 505013, 'secMark': 28716,
       'timeConfidence': 'time000002', 'pos': {'lat': 312789909, 'lon': 1212131214},
       'referPos': {'positionX': 7512, 'positionY': 3383}, 'nodeId': {'region': 1, 'id': 80}, 'laneId': 0,
       'accuracy': {'pos': 'a2m'}, 'transmission': 'unavailable', 'speed': 0, 'heading': 17273,
       'motionCfd': {'speedCfd': 'prec1ms', 'headingCfd': 'prec0_01deg'}, 'accelSet': {'lon': 0, 'lat': 0, 'vert': 0, 'yaw': 0},
       'size': {'width': 180, 'length': 500}, 'vehicleClass': {'classification': 'passenger_Vehicle_TypeUnknown'},
       'section_ext_id': 'genE469', 'lane_ext_id': 'genE469_0'}
msg = json.dumps(msg).encode('utf-8')
error_code, msg_body = fb_converter.json2fb(0x17, msg)

print(error_code)
