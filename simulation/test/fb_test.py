# -*- coding: utf-8 -*-
# @Time        : 2022/12/5 15:21
# @File        : fb_test.py
# @Description :

import json

from simulation.connection.python_fbconv.fbconv import FBConverter

fb_converter = FBConverter()
# msg = {'node_id': {'region': 1, 'id': 81}, 'sequence': 0, 'control_mode': 0, 'cycle': 90, 'base_signal_scheme_id': 0,
#        'start_time': 1671554970, 'phases': [
#         {'phasic_id': 1, 'order': 1, 'movements': ['5', '11', '6', '12'], 'green': 20, 'yellow': 6, 'allred': 0},
#         {'phasic_id': 2, 'order': 2, 'movements': ['4', '10'], 'green': 6, 'yellow': 6, 'allred': 0},
#         {'phasic_id': 3, 'order': 3, 'movements': ['9', '7', '6', '8'], 'green': 20, 'yellow': 6, 'allred': 0},
#         {'phasic_id': 4, 'order': 4, 'movements': ['3', '2', '1', '12'], 'green': 20, 'yellow': 6, 'allred': 0}]}
msg = {'node': {'region': 1, 'id': 31011}, 'gen_time': 1675780125, 'stat_type': {'interval': 89},
       'stat_type_type': 'DE_TrafficFlowStatByInterval', 'stats': [
        {'map_element': {'ext_id': '-4xnhzLD_vP.143.8795332000_0'}, 'map_element_type': 'DE_LaneStatInfo',
         'ptc_type': 1, 'veh_type': 'passenger_Vehicle_TypeUnknown', 'volume': 32359, 'speed_area': 0},
        {'map_element': {'ext_id': '-4xnhzLD_vP.143.8795332000_1'}, 'map_element_type': 'DE_LaneStatInfo',
         'ptc_type': 1, 'veh_type': 'passenger_Vehicle_TypeUnknown', 'volume': 20224, 'speed_area': 0},
        {'map_element': {'ext_id': '-4xnhzLD_vP.143.8795332000_2'}, 'map_element_type': 'DE_LaneStatInfo',
         'ptc_type': 1, 'veh_type': 'passenger_Vehicle_TypeUnknown', 'volume': 0, 'speed_area': 0},
        {'map_element': {'ext_id': '-HK3TRJVTf7.294.0683777000_0'}, 'map_element_type': 'DE_LaneStatInfo',
         'ptc_type': 1, 'veh_type': 'passenger_Vehicle_TypeUnknown', 'volume': 0, 'speed_area': 0},
        {'map_element': {'ext_id': '-HK3TRJVTf7.294.0683777000_1'}, 'map_element_type': 'DE_LaneStatInfo',
         'ptc_type': 1, 'veh_type': 'passenger_Vehicle_TypeUnknown', 'volume': 0, 'speed_area': 0},
        {'map_element': {'ext_id': '-HK3TRJVTf7.294.0683777000_2'}, 'map_element_type': 'DE_LaneStatInfo',
         'ptc_type': 1, 'veh_type': 'passenger_Vehicle_TypeUnknown', 'volume': 4044, 'speed_area': 0},
        {'map_element': {'ext_id': '0KUyAFxYUW.0.0000000000_0'}, 'map_element_type': 'DE_LaneStatInfo', 'ptc_type': 1,
         'veh_type': 'passenger_Vehicle_TypeUnknown', 'volume': 8089, 'speed_area': 0},
        {'map_element': {'ext_id': '0KUyAFxYUW.0.0000000000_1'}, 'map_element_type': 'DE_LaneStatInfo', 'ptc_type': 1,
         'veh_type': 'passenger_Vehicle_TypeUnknown', 'volume': 8089, 'speed_area': 0},
        {'map_element': {'ext_id': '0KUyAFxYUW.0.0000000000_2'}, 'map_element_type': 'DE_LaneStatInfo', 'ptc_type': 1,
         'veh_type': 'passenger_Vehicle_TypeUnknown', 'volume': 0, 'speed_area': 0},
        {'map_element': {'ext_id': 'AyE3bDm3uL.0.0000000000_0'}, 'map_element_type': 'DE_LaneStatInfo', 'ptc_type': 1,
         'veh_type': 'passenger_Vehicle_TypeUnknown', 'volume': 52584, 'speed_area': 0},
        {'map_element': {'ext_id': 'AyE3bDm3uL.0.0000000000_1'}, 'map_element_type': 'DE_LaneStatInfo', 'ptc_type': 1,
         'veh_type': 'passenger_Vehicle_TypeUnknown', 'volume': 28314, 'speed_area': 0},
        {'map_element': {'ext_id': 'AyE3bDm3uL.0.0000000000_2'}, 'map_element_type': 'DE_LaneStatInfo', 'ptc_type': 1,
         'veh_type': 'passenger_Vehicle_TypeUnknown', 'volume': 0, 'speed_area': 0}]}
msg = json.dumps(msg).encode('utf-8')
error_code, msg_body = fb_converter.json2fb(0x25, msg)

print(error_code, msg_body)
