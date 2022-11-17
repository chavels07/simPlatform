# -*- coding: utf-8 -*-
# @Time        : 2022/11/17 18:01
# @File        : sim_data.py
# @Description : 存放仿真运行环节需要记录的数据

from collections import namedtuple

_MsgProperty = namedtuple('MsgProperty', ['topic_name', 'fb_code'])
MSG_TYPE = {
    'MECLocal/SignalScheme': _MsgProperty('SignalScheme', 0x24),
    'MECLocal/SpeedGuide': _MsgProperty('SpeedGuide', 0x34)
}