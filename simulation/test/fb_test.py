# -*- coding: utf-8 -*-
# @Time        : 2022/12/5 15:21
# @File        : fb_test.py
# @Description :

import json

from simulation.connection.python_fbconv.fbconv import FBConverter

fb_converter = FBConverter()
msg = {'moy': 487656, 'timeStamp': 25280, 'name': '-108702', 'intersections': [
    {'intersectionId': {'region': 1, 'id': 108702}, 'status': {'status': 5}, 'moy': 487656, 'timeStamp': 25280,
     'timeConfidence': 0, 'phases': [
        {'id': 1, 'phaseStates': [
            {'light': 6, 'timing_type': 'DF_TimeCountingDown',
             'timing': {'startTime': 0, 'minEndTime': 394,
                        'maxEndTime': 394, 'likelyEndTime': 394,
                        'timeConfidence': 0, 'nextStartTime': 874,
                        'nextDuration': 420}}]},
        {'id': 2,
         'phaseStates': [
             {'light': 3,
              'timing_type': 'DF_TimeCountingDown',
              'timing': {
                  'startTime': 450,
                  'minEndTime': 870,
                  'maxEndTime': 870,
                  'likelyEndTime': 870,
                  'timeConfidence': 0,
                  'nextStartTime': 1350,
                  'nextDuration': 420}}]}]}]}
msg = json.dumps(msg).encode('utf-8')
error_code, msg_body = fb_converter.json2fb(0x18, msg)

print(error_code)
