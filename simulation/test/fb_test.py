# -*- coding: utf-8 -*-
# @Time        : 2022/12/5 15:21
# @File        : fb_test.py
# @Description :

import json

from simulation.connection.python_fbconv.fbconv import FBConverter

fb_converter = FBConverter(102400)
msg = {'node_id': {'region': 1, 'id': 81}, 'sequence': 0, 'control_mode': 0, 'cycle': 90, 'base_signal_scheme_id': 0,
       'start_time': 1671554970, 'phases': [
        {'phasic_id': 1, 'order': 1, 'movements': ['5', '11', '6', '12'], 'green': 20, 'yellow': 6, 'allred': 0},
        {'phasic_id': 2, 'order': 2, 'movements': ['4', '10'], 'green': 6, 'yellow': 6, 'allred': 0},
        {'phasic_id': 3, 'order': 3, 'movements': ['9', '7', '6', '8'], 'green': 20, 'yellow': 6, 'allred': 0},
        {'phasic_id': 4, 'order': 4, 'movements': ['3', '2', '1', '12'], 'green': 20, 'yellow': 6, 'allred': 0}]}
msg = {"id": 1, "refPos": {"lat": 1, "lon": 2}, "participants": []}
msg = json.dumps(msg).encode('utf-8')
error_code, msg_body = fb_converter.json2fb(0x1c, msg)

print(error_code, msg_body)
