# -*- coding: utf-8 -*-
# @Time        : 2023/9/2 20:01
# @File        : traffic_signal_test.py
# @Description :

import json

from paho.mqtt.client import Client, MQTTMessage

from simulation.connection.python_fbconv.fbconv import FBConverter

fb_converter = FBConverter(102400)
msg = {'node_id': {'region': 1, 'id': 80}, 'time_span': {}, 'control_mode': 0, 'cycle': 90, 'base_signal_scheme_id': 0, 'phases': [
        {'id': 1, 'order': 1, 'movements': ['1', '2', '3'], 'green': 20, 'yellow': 6, 'allred': 0},
        {'id': 2, 'order': 2, 'movements': ['5', '6', '7'], 'green': 20, 'yellow': 6, 'allred': 0},
        {'id': 3, 'order': 3, 'movements': ['9', '10', '11'], 'green': 20, 'yellow': 6, 'allred': 0},
        {'id': 4, 'order': 4, 'movements': ['13', '14', '15'], 'green': 20, 'yellow': 6, 'allred': 0}]}
err_code, bytes_msg = fb_converter.json2fb(0x24, json.dumps(msg).encode())

client = Client()
client.connect('121.36.231.253', 1883)
client.publish('MECUpload/1/SignalScheme', bytes_msg)