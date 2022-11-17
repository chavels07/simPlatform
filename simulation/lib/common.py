# -*- coding: utf-8 -*-
# @Time        : 2022/11/17 23:12
# @File        : common.py
# @Description : 通用的工具

import logging

logging.basicConfig(format='%(asctime)s.%(msecs)03d [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s',
                    datefmt='## %Y-%m-%d %H:%M:%S')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
