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
    """仿真直接调用通信类"""

    def __init__(self):
        self.state = False
        self.__msg_transfer = MessageTransfer()
        self.__sub_thread = None
        self.__pub_client = None

    # def _publish(self, topic, msg):
    #     """向指定topic推送消息，未连接状态则不进行推送"""
    #     return self._state.publish(topic, msg)

    def publish(self, msg_label: 'PubMsgLabel'):
        """向指定topic推送消息，未连接状态则不进行推送"""
        return self.__pub_client.publish(msg_label)

    def loading_msg(self, msg_type: Type[DetailMsgType]) -> Iterator[Tuple[DetailMsgType, MsgInfo]]:
        """获取当前的所有消息，以遍历形式读取"""
        return self.__msg_transfer.loading_msg(msg_type)

    def connect(self, broker, port, topics):
        """

        Args:
            broker: 服务器ip
            port: 端口号
            topics: 需要订阅的一系列主题，若为空则订阅所有可用MSG_TYPE中的主题
        """
        self.__sub_thread = SubClientThread(broker, port, topics)
        self.__pub_client = PubClient(broker, port)
        self.__sub_thread.start()
        self.state = True


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
    def loading_msg(cls, msg_type: Type[DetailMsgType]) -> Iterator[Tuple[DetailMsgType, MsgInfo]]:
        """
        获取当前的所有消息，使用for循环读取
        Returns: 生成器:(消息的类型, 内容对应的字典)，可能为空
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
            yield from ()  # 生成一个空的迭代器

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


def on_disconnect(client, userdata, rc):
    if rc != 0:
        print('Attempting to reconnect')
        try:
            client.reconnect()
            logger.info('Reconnect successfully')
        except Exception as e:
            logger.warn('Reconnection failed, data publish stopped')


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
        msg_info = self.client.publish(topic, msg)
        if msg_info.rc != 0:
            logger.info(f'fail to send message to topic {topic}, return code: {msg_info.rc}')

    def publish(self, msg_label: PubMsgLabel):
        target_topic, fb_code = MSG_TYPE_INFO.get(msg_label.msg_type)
        if msg_label.multiple:
            for single_msg in msg_label.raw_msg:
                self.publish_single_msg(single_msg, msg_label.msg_type, msg_label.convert_method, fb_code, target_topic)
        else:
            self.publish_single_msg(msg_label.raw_msg, msg_label.msg_type, msg_label.convert_method, fb_code, target_topic)

    def publish_single_msg(self, raw_msg, msg_type: DetailMsgType, convert_method: str, fb_code, target_topic: str):
        if convert_method == 'flatbuffers':
            if fb_code is None:
                raise ValueError(f'no flatbuffers structure for msg type {msg_type}')
            _msg = json.dumps(raw_msg).encode('utf-8')
            print(_msg)

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
