# -*- coding: utf-8 -*-
# @Time        : 2022/11/17 23:12
# @File        : common.py
# @Description : 通用的工具

import os
import logging
import time
from inspect import signature
from functools import wraps
from typing import Union

# '%(asctime)s.%(msecs)03d [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s'
# logging.basicConfig(format='%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s',
#                     datefmt='## %Y-%m-%d %H:%M:%S')
raw_logger = logging.getLogger()
raw_logger.setLevel(logging.DEBUG)

formatter = logging.Formatter(fmt='%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s',
                              datefmt='## %Y-%m-%d %H:%M:%S')
logger_handler = logging.StreamHandler()
logger_handler.setFormatter(formatter)
raw_logger.addHandler(logger_handler)

project_directory_path = os.path.dirname(os.getcwd())
file_handler = logging.FileHandler(os.path.join(project_directory_path, 'logs', 'run.log'), encoding='utf-8')
file_handler.setLevel(logging.ERROR)
file_handler.setFormatter(formatter)
raw_logger.addHandler(file_handler)


class UserLogger:
    def __init__(self, _logger: logging.Logger):
        self._logger = _logger
        self._user_info_cache = []

    def debug(self, msg: str):
        self._logger.debug(msg)

    def info(self, msg: str):
        self._logger.info(msg)

    def warning(self, msg: str):
        self._logger.warning(msg)

    def error(self, msg: str):
        self._logger.error(msg)

    def user_info(self, msg: str):
        self._user_info_cache.append(msg)
        self.info(msg)

    def pop_user_info(self):
        rv = self._user_info_cache
        self._user_info_cache = []
        return rv

    def reset_user_info(self):
        self._user_info_cache.clear()


logger = UserLogger(raw_logger)


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
            if para.annotation.__origin__ == Union:
                annotation_type = para.annotation.__args__  # Union则单独提取出来所有可能的类型，只支持基础类型的union
            else:
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
                # noinspection PyTypeHints
                if not isinstance(value, bound_types[name]):
                    raise TypeError(f'Argument {name} must be {bound_types[name]}, while {type(value)} is given')
        return func(*args, **kwargs)
    return wrapper


def common_docs(docstrings: str):
    """为装饰的对象添加相同的docstring内容"""
    def wrapper(func):
        if func.__doc__ is not None:
            func.__doc__ = '\n'.join((docstrings, func.__doc__))
        else:
            func.__doc__ = docstrings
        return func
    return wrapper


def timer(func):
    """函数运行计时装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.clock()
        res = func(*args, **kwargs)
        end = time.clock()
        print(f'函数{func.__name__}运行用时{end-start}秒')
        return res
    return wrapper


class ImplementCounter:
    def __init__(self):
        self.counter = 0

    @property
    def valid_implement(self) -> bool:
        return self.counter > 0

    def implement_reaction(self):
        self.counter += 1

    def reset(self):
        self.counter = 0
