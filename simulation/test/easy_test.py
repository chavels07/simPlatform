# -*- coding: utf-8 -*-
# @Time        : 2022/11/30 22:19
# @File        : easy_test.py
# @Description : 简单测试用例

import json

from paho.mqtt.client import Client

client = Client()
client.connect('121.36.231.253', 1883)

send_cmd = {"docker": "Algorithm test1"}
send_cmd = json.dumps(send_cmd)
client.publish('MECUpload/1/Start', send_cmd)


