# -*- coding: utf-8 -*-
# @Time        : 2022/11/17 23:12
# @File        : common.py
# @Description : 通用的工具

import logging
from inspect import signature
from functools import wraps
from typing import Generic, Dict

logging.basicConfig(format='%(asctime)s.%(msecs)03d [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s',
                    datefmt='## %Y-%m-%d %H:%M:%S')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


def singleton(cls):
    _instances = {}
    @wraps(cls)
    def wrapper(*args, **kwargs):
        if cls not in _instances:
            _instances[cls] = cls(*args, **kwargs)
        return _instances[cls]
    return wrapper


class Singleton(type):
    """创建单例"""
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


def typeassert(*ty_args, **ty_kwargs):
    """强制参数类型检查的装饰器，一般用于构造标准数据结构的字典防止输入类型错误，无法与typing配合使用"""
    def decorate(func):

        # Map function argument names to supplied types
        sig = signature(func)
        bound_types = sig.bind_partial(*ty_args, **ty_kwargs).arguments

        @wraps(func)
        def wrapper(*args, **kwargs):
            bound_values = sig.bind(*args, **kwargs)
            # Enforce type assertions across supplied arguments
            for name, value in bound_values.arguments.items():
                if name in bound_types:
                    if not isinstance(value, bound_types[name]):
                        raise TypeError(f'Argument {name} must be {bound_types[name]}')
            return func(*args, **kwargs)
        return wrapper
    return decorate


def alltypeassert(func):
    """强制参数类型检查的装饰器，一般用于构造标准数据结构的字典防止输入类型错误，无法与typing配合使用"""
    # if not __debug__:
    #     return func

    # Map function argument names to supplied types
    sig = signature(func)
    bound_types = {}
    for para_name, para in sig.parameters.items():
        if hasattr(para.annotation, '__origin__'):
            annotation_type = para.annotation.__origin__  # 应对Typing subscribe的情况，提取其基础数据类型，不安全
        else:
            annotation_type = para.annotation
        bound_types[para_name] = annotation_type
    # bound_types = sig.parameters  # {name: para.annotation for name, para in sig.parameters.items()}

    @wraps(func)
    def wrapper(*args, **kwargs):
        bound_values = sig.bind(*args, **kwargs)
        # Enforce type assertions across supplied arguments
        for name, value in bound_values.arguments.items():
            if name in bound_types:
                if not type(value) == bound_types[name]:
                    raise TypeError(f'Argument {name} must be {bound_types[name]}, while {type(value)} is given')
        return func(*args, **kwargs)
    return wrapper
