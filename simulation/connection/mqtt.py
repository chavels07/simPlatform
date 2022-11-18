# -*- coding: utf-8 -*-
# @Time        : 2022/11/17 17:33
# @File        : mqtt.py
# @Description : MQTT通信

import json
import random
import threading
from dataclasses import dataclass
from queue import Queue
from typing import Tuple, Iterator, Iterable, Union, Any

from paho.mqtt.client import Client, MQTTMessage

from simulation.connection.python_fbconv.fbconv import FBConverter
from simulation.lib.sim_data import MSG_TYPE
from simulation.lib.common import logger

fb_converter = FBConverter()  # only used here


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

    def loading_msg(self):
        """获取当前的所有消息，以遍历形式读取，未连接状态则返回空列表"""
        return self._state.loading_msg()

    def connect(self, broker: str, port: int, topics: Union[str, Iterable[str], None]):
        """

        Args:
            broker: 服务器ip
            port: 端口号
            topics: 需要订阅的一系列主题，若为空则订阅所有可用MSG_TYPE中的主题
        """
        self._state = OpenMQTTConnection(broker, port, topics)


CONVERT_METHOD = ['json', 'flatbuffers', 'raw']


class PubMsgLabel:
    """任意通过MQTT传输的消息均要通过转换成该类"""

    def __init__(self, raw_msg: Any, msg_type: str, convert_method: str):
        """

        Args:
            raw_msg: 消息内容, most likely type: dict
            msg_type: 消息的类型
            convert_method: 发送前需要转换成的数据

        """
        self.raw_msg = raw_msg
        self.msg_type = msg_type
        self.convert_method = convert_method

    @property
    def convert_method(self):
        return self._convert_method

    @convert_method.setter
    def convert_method(self, value):
        if not isinstance(value, str) or value not in CONVERT_METHOD:
            raise ValueError(f'given convert method is not defined, allowed value: {",".join(CONVERT_METHOD)}')
        self._convert_method = value


class MessageTransfer:
    __msg_queue = Queue(maxsize=1024)
    __sub_msg_queue = Queue(maxsize=1024)

    @classmethod
    def append(cls, msg_type: str, msg_payload: dict):
        cls.__msg_queue.put_nowait((msg_type, msg_payload))

    @classmethod
    def loading_msg(cls) -> Iterator[Tuple[str, dict]]:
        """
        获取当前的所有消息
        Returns: 生成器:(消息的类型, 内容对应的字典)
        """
        pop_msg = cls.__msg_queue
        cls.__msg_queue = cls.__sub_msg_queue

        while not pop_msg.empty():
            yield pop_msg.get_nowait()

        cls.__sub_msg_queue = pop_msg  # 读完数据后变成替补


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Connected to MQTT Broker!")
    else:
        logger.info("Failed to connect, return code %d\n", rc)


VALID_TOPIC = {item.topic_name: (short_name, item.fb_code) for short_name, item in MSG_TYPE.items() if
               item.topic_name.startswith('MECLocal')}  # 选取下发的topic进行订阅


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
                            f'msg type: {short_topic}, error code: {success}, msg body: {msg_value}')
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
            self.topics = VALID_TOPIC
        elif isinstance(topics, str):
            self.topics = topics
        elif isinstance(topics, Iterable):
            self.topics = ((topic, 0) for topic in topics)
        else:
            raise TypeError(f'wrong topics type {type(topics)}')
        self.client = None

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
        target_topic, fb_code = MSG_TYPE.get(msg_label.msg_type)
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
    def __init__(self, broker: str, port: int, topics: Union[str, Iterable[str], None]):
        self.__msg_transfer = MessageTransfer()
        self.__sub_thread = SubClientThread(broker, port, topics)
        self.__pub_client = PubClient(broker, port)
        self.__sub_thread.start()

    def publish(self, topic, msg):
        """向指定topic推送消息"""
        self.__pub_client.publish(topic, msg)

    def loading_msg(self):
        """获取当前的所有消息，以遍历形式读取"""
        return self.__msg_transfer.loading_msg()

    def closed(self):
        pass


class ClosedMQTTConnection:
    @staticmethod
    def publish(*args):
        logger.info('cannot publish before connecting')

    @staticmethod
    def loading_msg():
        logger.info('cannot loading received message before connecting')
        return []
