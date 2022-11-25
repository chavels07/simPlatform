# -*- coding: utf-8 -*-
# @Time        : 2022/11/17 17:33
# @File        : mqtt.py
# @Description : MQTT通信

import json
import random
import threading
from collections import namedtuple
from queue import Queue
from typing import Tuple, Iterator, Iterable, Union, Optional, Any, Type

from paho.mqtt.client import Client, MQTTMessage

from simulation.connection.python_fbconv.fbconv import FBConverter
from simulation.lib.common import logger
from simulation.lib.public_data import OrderMsg, DataMsg, SpecialDataMsg, DetailMsgType

fb_converter = FBConverter()  # only used here

_MsgProperty = namedtuple('MsgProperty', ['topic_name', 'fb_code'])
MSG_TYPE_INFO = {
    # 订阅
    DataMsg.SignalScheme: _MsgProperty('MECUpload/1/SignalScheme', 0x24),
    DataMsg.SpeedGuide: _MsgProperty('MECUpload/1/SpeedGuide', 0x34),

    # 自定义数据结构，通过json直接传递，None表示无需转换fb
    OrderMsg.Start: _MsgProperty('MECUpload/1/Start', None),  # 仿真开始
    SpecialDataMsg.TransitionSS: _MsgProperty('MECUpload/1/TransitionSignalScheme', None),  # 过渡周期信控方案
    SpecialDataMsg.SERequirement: _MsgProperty('MECUpload/1/SignalExecutionRequirement', None)  # 请求发送当前执行的信控方案

    # 发布

}


class MQTTConnection:
    """仿真直接调用通信类"""

    def __init__(self):
        self._state = ClosedMQTTConnection()

    # def _publish(self, topic, msg):
    #     """向指定topic推送消息，未连接状态则不进行推送"""
    #     return self._state.publish(topic, msg)

    def publish(self, msg_label: 'PubMsgLabel'):
        """向指定topic推送消息，未连接状态则不进行推送"""
        return self._state.publish(msg_label)

    def loading_msg(self, msg_type: Type[DetailMsgType]):
        """获取当前的所有消息，以遍历形式读取，未连接状态则返回空列表"""
        return self._state.loading_msg(msg_type)

    def connect(self, broker: str, port: int, topics: Union[str, Iterable[str], None]):
        """

        Args:
            broker: 服务器ip
            port: 端口号
            topics: 需要订阅的一系列主题，若为空则订阅所有可用MSG_TYPE中的主题
        """
        self._state = OpenMQTTConnection(broker, port, topics)

    @property
    def status(self):
        """获取通信连接状态"""
        return self._state.status


CONVERT_METHOD = ['json', 'flatbuffers', 'raw']


class PubMsgLabel:
    """任意通过MQTT传输的消息均要通过转换成该类"""

    def __init__(self, raw_msg: Any, msg_type: DetailMsgType, convert_method: str, multiple: bool = False):
        """

        Args:
            raw_msg: 消息内容, most likely type: dict
            msg_type: 消息的类型
            convert_method: 发送前需要转换成的数据
            multiple: 消息是否为可迭代的多条消息，当有多条消息需要发送时raw_msg为list需要设为true

        """
        self.raw_msg = raw_msg
        self.msg_type = msg_type
        self.convert_method = convert_method
        self.multiple = multiple

    @property
    def convert_method(self):
        return self._convert_method

    @convert_method.setter
    def convert_method(self, value):
        if not isinstance(value, str) or value not in CONVERT_METHOD:
            raise ValueError(f'given convert method is not defined, allowed value: {",".join(CONVERT_METHOD)}')
        self._convert_method = value


class MessageTransfer:
    __order_queue = Queue(maxsize=1024)
    __data_queue = Queue(maxsize=1024)
    __special_queue = Queue(maxsize=1024)
    # __msg_queue = Queue(maxsize=1024)
    # __sub_msg_queue = Queue(maxsize=1024)

    @classmethod
    def append(cls, msg_type: DetailMsgType, msg_payload: dict):
        if isinstance(msg_type, DataMsg):
            cls.__data_queue.put_nowait((msg_type, msg_payload))
        elif isinstance(msg_type, SpecialDataMsg):
            cls.__special_queue.put_nowait((msg_type, msg_payload))
        elif isinstance(msg_type, OrderMsg):
            cls.__order_queue.put_nowait((msg_type, msg_payload))
        else:
            logger.debug('unspecified message type')

    @classmethod
    def loading_msg(cls, msg_type: Type[DetailMsgType]) -> Optional[Iterator[Tuple[DetailMsgType, dict]]]:
        """
        获取当前的所有消息
        Returns: 生成器:(消息的类型, 内容对应的字典)
        """
        if msg_type == DataMsg:
            _pop_queue = cls.__data_queue
        elif msg_type == SpecialDataMsg:
            _pop_queue = cls.__special_queue
        elif msg_type == OrderMsg:
            _pop_queue = cls.__order_queue
        else:
            raise TypeError(f'wrong message type: {msg_type}')
        if _pop_queue.empty():
            return None

        while not _pop_queue.empty():
            yield _pop_queue.get_nowait()


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Connected to MQTT Broker!")
    else:
        logger.info("Failed to connect, return code %d\n", rc)


VALID_TOPIC = {item.topic_name: (short_name, item.fb_code) for short_name, item in MSG_TYPE_INFO.items() if
               item.topic_name.startswith('MECUpload')}  # 选取下发的topic进行订阅


def on_message(client, user_data, msg: MQTTMessage):
    short_topic, msg_type_code = VALID_TOPIC.get(msg.topic)
    if short_topic is not None:
        msg_len = msg.payload.find(chr(0))
        msg_value = msg.payload[:msg_len]
        # type code为None时表示直接传json而不是FB
        if msg_type_code is not None:
            success, msg_value = fb_converter.fb2json(msg_type_code, msg_value)
            if success != 0:
                logger.warn(f'fb2json error occurs when receiving message, '
                            f'msg type: {short_topic.name()}, error code: {success}, msg body: {msg_value}')
                return None

        msg_ = json.loads(msg_value)  # json 转换成 dict
        MessageTransfer.append(short_topic, msg_)

    # # 交通事件主题
    # if msg.topic == 'MECLocal/TrafficEvent':
    #     info_fb['accident'] = str(msg.payload.decode(encoding="utf-8"))
    # # 协同引导主题
    # if msg.topic == 'MECLocal/RSC':
    #     info_fb['guidance'] = str(msg.payload.decode(encoding="utf-8"))
    # # 需求输入主题
    # if msg.topic == 'MECLocal/Demand':
    #     info_fb['demand'] = str(msg.payload.decode(encoding="utf-8"))
    # # 可变限速
    # if msg.topic == 'MECLocal/VSL':
    #     info_fb['VSL'] = str(msg.payload.decode(encoding="utf-8"))
    # # 专用车道
    # if msg.topic == 'MECLocal/DLC':
    #     info_fb['DLC'] = str(msg.payload.decode(encoding="utf-8"))
    # # 换道
    # if msg.topic == 'MECLocal/VMS':
    #     info_fb['VMS'] = str(msg.payload.decode(encoding="utf-8"))
    # # 信控方案
    # if msg.topic == 'MECLocal/SignalScheme':
    #     info_fb['signal'] = str(msg.payload.decode(encoding="utf-8"))
    # # 倒计时
    # if msg.topic == 'MECLocal/SPAT':
    #     info_fb['cutdown'] = str(msg.payload.decode(encoding="utf-8"))
    # # 信控方案上传
    # if msg.topic == 'MECLocal/Wildcard':
    #     info_fb['getsignal'] = str(msg.payload.decode(encoding="utf-8"))
    # # 车速引导
    # if msg.topic == 'MECLocal/SpeedGuide':
    #     info_fb['SpeedGuide'] = str(msg.payload.decode(encoding="utf-8"))


class SubClientThread(threading.Thread):
    """
    接收订阅线程
    """

    def __init__(self, broker: str, port: int, topics: Union[str, Iterable[str], None]):
        super().__init__()
        self.broker = broker
        self.port = port
        if topics is None:
            self.topics = [(topic, 0) for topic in VALID_TOPIC.keys()]
        elif isinstance(topics, str):
            self.topics = topics
        elif isinstance(topics, Iterable):
            self.topics = [(topic, 0) for topic in topics]
        else:
            raise TypeError(f'wrong topics type {type(topics)}')
        self.client = None
        self.daemon = True

    def run(self) -> None:
        self.connect_sub_mqtt()

    def connect_sub_mqtt(self):
        """通过MQTT协议创建连接，阻塞形式"""
        client_id = f'sub-{random.randint(0, 1000)}'
        client = Client(client_id)
        client.on_connect = on_connect
        client.on_message = on_message

        client.connect(self.broker, self.port)
        client.subscribe(topic=self.topics)
        client.loop_forever()
        self.client = client


class PubClient:
    """
    发布消息, 使用实例:
    """

    def __init__(self, broker, port):
        self.client = self.__connect_pub_mqtt(broker, port)

    @staticmethod
    def __connect_pub_mqtt(broker, port):
        client_id = f'pub-{random.randint(0, 1000)}'
        client = Client(client_id)
        client.on_connect = on_connect
        client.connect(broker, port)
        return client

    def _publish(self, topic: str, msg: str):
        msg_info = self.client.publish(topic, msg.encode(encoding='utf-8'))
        if msg_info.rc != 0:
            logger.info(f'fail to send message to topic {topic}, return code: {msg_info.rc}')

    def publish(self, msg_label: PubMsgLabel):
        target_topic, fb_code = MSG_TYPE_INFO.get(msg_label.msg_type)
        if msg_label.convert_method == 'flatbuffers':
            if fb_code is None:
                raise ValueError(f'no flatbuffers structure for msg type {msg_label.msg_type}')
            _msg = json.dumps(msg_label.raw_msg)
            success, _msg = fb_converter.json2fb(fb_code, _msg)
            if success != 0:
                logger.warn(f'json2fb error occurs when sending message, '
                            f'msg type: {msg_label.msg_type}, error code: {success}, msg body: {msg_label.raw_msg}')
                return None
        elif msg_label.convert_method == 'json':
            _msg = json.dumps(msg_label.raw_msg)
        elif msg_label.convert_method == 'raw':
            _msg = msg_label.raw_msg
        else:
            raise ValueError(f'cannot handle convert type: {msg_label.convert_method}')

        self._publish(_msg, target_topic)


class OpenMQTTConnection:
    status = True

    def __init__(self, broker: str, port: int, topics: Union[str, Iterable[str], None]):
        self.__msg_transfer = MessageTransfer()
        self.__sub_thread = SubClientThread(broker, port, topics)
        self.__pub_client = PubClient(broker, port)
        self.__sub_thread.start()

    def publish(self, topic, msg):
        """向指定topic推送消息"""
        self.__pub_client.publish(topic, msg)

    def loading_msg(self, msg_type: Type[DetailMsgType]):
        """获取当前的所有消息，以遍历形式读取"""
        return self.__msg_transfer.loading_msg(msg_type)

    def closed(self):
        pass


class ClosedMQTTConnection:
    status = False

    @staticmethod
    def publish(*args):
        logger.info('cannot publish before connecting')

    @staticmethod
    def loading_msg(msg_type: Type[DetailMsgType]):
        logger.info('cannot loading received message before connecting')
        return []
