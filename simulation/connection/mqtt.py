# -*- coding: utf-8 -*-
# @Time        : 2022/11/17 17:33
# @File        : mqtt.py
# @Description : MQTT通信

import json
import random
import threading
from collections import namedtuple
from queue import Queue
from typing import Tuple, Iterator, Iterable, Union, Type

from paho.mqtt.client import Client, MQTTMessage

from simulation.connection.python_fbconv.fbconv import FBConverter
from simulation.lib.common import logger
from simulation.lib.public_conn_data import OrderMsg, DataMsg, SpecialDataMsg, DetailMsgType, PubMsgLabel

FB_CACHE_SIZE = 102400
fb_converter = FBConverter(FB_CACHE_SIZE)  # only used here

_MsgProperty = namedtuple('MsgProperty', ['topic_name', 'fb_code'])
MSG_TYPE_INFO = {
    # 订阅
    DataMsg.SignalScheme: _MsgProperty('MECUpload/1/SignalScheme', 0x24),
    DataMsg.SignalRequest: _MsgProperty('MECUpload/1/SignalRequest', 0x31),
    DataMsg.SpeedGuide: _MsgProperty('MECUpload/1/SpeedGuide', 0x34),

    # 自定义数据结构，通过json直接传递，None表示无需转换fb
    OrderMsg.Start: _MsgProperty('MECUpload/1/Start', None),  # 仿真开始

    SpecialDataMsg.TransitionSS: _MsgProperty('MECUpload/1/TransitionSignalScheme', None),  # 过渡周期信控方案
    SpecialDataMsg.SERequirement: _MsgProperty('MECUpload/1/SignalExecutionRequirement', None),  # 请求发送当前执行的信控方案

    # 发布
    DataMsg.SignalPhaseAndTiming: _MsgProperty('MECCloud/1/SPAT', 0x18),  # SPAT和BSM原来1均在末位，此处进行调整
    DataMsg.TrafficFlow: _MsgProperty('MECCloud/1/TrafficFlow', 0x25),
    DataMsg.SafetyMessage: _MsgProperty('MECCloud/1/BSM', 0x17),
    DataMsg.RoadsideSafetyMessage: _MsgProperty('MECCloud/1/RSM', 0x1c),
    DataMsg.SignalExecution: _MsgProperty('MECCloud/1/SignalExecution', 0x30),
    OrderMsg.ScoreReport: _MsgProperty('MECUpload/1/AlgoImageTest', None)  # 分数上报
}

MsgInfo = Union[dict, str]  # 从通信获取的message类型为dict or str


class MQTTConnection:
    """仿真直接调用通信类，包含接收订阅消息的线程，推送消息的客户端，消息缓存中转队列"""
    def __init__(self):
        self.state = False
        self.__msg_transfer = MessageTransfer()
        self.__sub_thread = None
        self.__pub_client = None

    # def _publish(self, topic, msg):
    #     """向指定topic推送消息，未连接状态则不进行推送"""
    #     return self._state.publish(topic, msg)

    def publish(self, msg_label: PubMsgLabel):
        """向指定topic推送消息，未连接状态则不进行推送"""
        return self.__pub_client.publish(msg_label)

    def loading_msg(self, msg_type: Type[DetailMsgType]) -> Iterator[Tuple[DetailMsgType, MsgInfo]]:
        """获取当前的所有消息，以遍历形式读取"""
        return self.__msg_transfer.loading_msg(msg_type)

    def connect(self, broker, port, topics):
        """
        连接MQTT服务器
        Args:
            broker: 服务器ip
            port: 端口号
            topics: 需要订阅的一系列主题，若为空则订阅所有可用MSG_TYPE中的主题
        """
        self.__sub_thread = SubClientThread(broker, port, topics)
        self.__pub_client = PubClient(broker, port, self.__sub_thread.client)
        self.__sub_thread.start()
        self.state = True

    def clear_residual_data(self):
        self.__msg_transfer.clear_residual_info()


class MessageTransfer:
    """接收到的订阅消息缓存中转队列，按照消息类型存储到对应的队列"""
    msg_queue_collections = {
        DataMsg: Queue(maxsize=1024),
        SpecialDataMsg: Queue(maxsize=1024),
        OrderMsg: Queue(maxsize=1024)
    }

    @classmethod
    def append(cls, msg_type: DetailMsgType, msg_payload: dict):
        """
        向相应队列中插入消息
        Args:
            msg_type: 消息类型
            msg_payload: 消息内容

        Returns:

        """
        msg_queue = cls.msg_queue_collections.get(msg_type.__class__)
        if msg_queue is None:
            raise TypeError('unspecified message type')
        msg_queue.put_nowait((msg_type, msg_payload))

    @classmethod
    def loading_msg(cls, msg_type: Type[DetailMsgType]):
        """
        获取当前的所有消息，使用for循环读取
        Args:
            msg_type: 消息类型

        Returns: 生成器:(消息的类型, 内容对应的字典)，可能为空

        """
        _pop_queue = cls.msg_queue_collections.get(msg_type)
        if _pop_queue is None:
            raise TypeError(f'wrong message type: {msg_type}')

        if _pop_queue.empty():
            yield from ()  # 生成一个空的迭代器

        while not _pop_queue.empty():
            yield _pop_queue.get_nowait()

    @classmethod
    def clear_residual_info(cls):
        data_q =  cls.msg_queue_collections[DataMsg]
        special_data_q = cls.msg_queue_collections[SpecialDataMsg]
        while not data_q.empty():
            data_q.get_nowait()

        while not special_data_q.empty():
            special_data_q.get_nowait()


# 选取下发的topic进行订阅，通过topic名称筛选出需要订阅的topic
VALID_TOPIC = {item.topic_name: (short_name, item.fb_code) for short_name, item in MSG_TYPE_INFO.items() if
               item.topic_name.startswith('MECUpload') or item.topic_name.endswith('SIM')}


def on_connect(client, userdata, flags, rc):
    """MQTT连接服务器回调函数"""
    if rc == 0:
        logger.info("Connected to MQTT Broker!")
    else:
        logger.info("Failed to connect, return code %d\n", rc)


def on_message(client, user_data, msg: MQTTMessage):
    """MQTT接收订阅消息回调函数"""
    short_topic, msg_type_code = VALID_TOPIC.get(msg.topic)
    if short_topic is not None:
        # msg_len = msg.payload.find(0x00)
        # msg_value = msg.payload[:msg_len] if msg_len > 0 else msg.payload
        msg_value = msg.payload
        # type code为None时表示直接传json而不是FB
        if msg_type_code is not None:
            success, msg_value = fb_converter.fb2json(msg_type_code, msg_value)
            msg_value = msg_value.strip(str(b'\x00', encoding='utf-8'))  # 去取末尾多余的0
            if success != 0:
                logger.warn(f'fb2json error occurs when receiving message, '
                            f'msg type: {short_topic.name()}, error code: {success}, msg body: {msg_value}')
                return None
        else:
            msg_value = msg_value.decode('utf-8')
        msg_ = json.loads(msg_value)  # json 转换成 dict
        print(msg_)
        MessageTransfer.append(short_topic, msg_)


def on_disconnect(client, userdata, rc):
    """MQTT断开连接回调函数，尝试重连"""
    if rc != 0:
        print('Attempting to reconnect')
        try:
            client.reconnect()
            logger.info('Reconnect successfully')
        except Exception as e:
            logger.error('Reconnection failed, data publish stopped')


class SubClientThread(threading.Thread):
    """
    接收订阅消息的线程
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
        client = Client(client_id, clean_session=False)
        client.on_connect = on_connect
        client.on_message = on_message
        client.disconnect = on_disconnect

        client.connect(self.broker, self.port)
        client.subscribe(topic=self.topics, qos=1)
        client.loop_forever()
        self.client = client


class PubClient:
    """
    发布消息的客服端, 推送的消息需要封装成PubMsgLabel的形式传入
    """

    def __init__(self, broker, port, sub_client: Client = None):
        if sub_client is None:
            self.client = self.__connect_pub_mqtt(broker, port)
        else:
            self.client = sub_client

    @staticmethod
    def __connect_pub_mqtt(broker, port):
        """创建MQTT客户端"""
        client_id = f'pub-{random.randint(0, 1000)}'
        client = Client(client_id)
        client.on_connect = on_connect
        client.disconnect = on_disconnect
        client.reconnect_delay_set()
        client.connect(broker, port)
        return client

    def _publish(self, topic: str, msg: str):
        """通过客户端发布单条消息"""
        msg_info = self.client.publish(topic, msg)
        if msg_info.rc == 0:
            return
        logger.info(f'fail to send message to topic {topic}, return code: {msg_info.rc}')
        self.client.reconnect()
        msg_info = self.client.publish(topic, msg)
        if msg_info.rc != 0:
            raise RuntimeError('Cannot reconnect')

    def publish(self, msg_label: PubMsgLabel):
        """根据推送消息标记发布单条或多条消息"""
        target_topic, fb_code = MSG_TYPE_INFO.get(msg_label.msg_type)
        if msg_label.multiple:
            for single_msg in msg_label.raw_msg:
                self.publish_single_msg(single_msg, msg_label.msg_type, msg_label.convert_method, fb_code, target_topic)
        else:
            self.publish_single_msg(msg_label.raw_msg, msg_label.msg_type, msg_label.convert_method, fb_code, target_topic)

    def publish_single_msg(self, raw_msg, msg_type: DetailMsgType, convert_method: str, fb_code, target_topic: str):
        """
        根据消息标记完成数据转换或序列化任务，推送单条消息
        Args:
            raw_msg: 消息主体内容
            msg_type: 消息类型
            convert_method: 转换或序列化方法
            fb_code: 序列化成Flatbuffers对应的消息类型编号，若无需序列化传入None
            target_topic: 消息发布指定的topic

        Returns:

        """
        if convert_method == 'flatbuffers':
            if fb_code is None:
                raise ValueError(f'no flatbuffers structure for msg type {msg_type}')
            _msg = json.dumps(raw_msg).encode('utf-8')

            success, _msg = fb_converter.json2fb(fb_code, _msg)
            if success != 0:
                logger.warn(f'json2fb error occurs when sending message, '
                            f'msg type: {msg_type}, error code: {success}, msg body: {raw_msg}')
                return None
        elif convert_method == 'json':
            _msg = json.dumps(raw_msg)
        elif convert_method == 'raw':
            _msg = raw_msg
        else:
            raise ValueError(f'cannot handle convert type: {convert_method}')

        self._publish(target_topic, _msg)
