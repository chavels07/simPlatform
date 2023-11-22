# -*- coding: utf-8 -*-
# @Time        : 2022/11/30 22:19
# @File        : easy_test.py
# @Description : 简单测试用例

import json

from paho.mqtt.client import Client

from simulation.connection.python_fbconv.fbconv import FBConverter

client = Client()
client.connect('121.36.231.253', 1883)

send_cmd = {"docker": "algo/test-v0.0.0|"}
send_cmd = json.dumps(send_cmd)
client.publish('MECUpload/1/Start', send_cmd)

# fb_converter = FBConverter()
#
# send_speed_guide = {
#     'mec_id': 'MEC_0',
#     'veh_id': 2,
#     'time': 0,
#     'guide_info': [
#         {
#             'time': 0,
#             'speed': 1,
#             'guide': 1,
#         }
#     ]
# }
# send_speed_guide = json.dumps(send_speed_guide).encode('utf-8')
# ret_code, ret_val = fb_converter.json2fb(0x34, send_speed_guide)
# print(ret_val)
# client.publish('MECUpload/1/SpeedGuide', ret_val)
