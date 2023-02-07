# python_fbconv

针对MECData所管理的ZBRS公共数据结构，提供不同序列化格式转换及Flatbuffers间互转功能。

## 预定义的一些数据类型
类型对应的值  类型名
```python
1 MECInfo.fbs
2 AppStatus.fbs
3 AppInfo.fbs
4 DeviceSet.fbs
5 ErrorImmediateReport.fbs
6 DeviceOTA.fbs
7 AppOTA.fbs
8 DeviceInfo.fbs
17 VolumeLane.fbs
18 DensityLane.fbs
19 SpeedLaneArea.fbs
20 SpeedLanePoint.fbs
21 TrafficSign.fbs
22 TrafficEvent.fbs
23 SafetyMessage.fbs
24 SignalPhaseAndTiming.fbs
25 MAP.fbs
26 RoadsideCoordination.fbs
27 RoadSideInformation.fbs
28 RoadsideSafetyMessage.fbs
29 VehIntentionAndRequest.fbs
30 DedicatedLaneControl.fbs
31 VariableSpeedLimit.fbs
32 RampMetering.fbs
33 NowWeather.fbs
34 ForecastWeather.fbs
35 ForecastRain.fbs
36 SignalScheme.fbs
37 TrafficFlow.fbs
38 TrajectoryPoints.fbs
39 QueueLength.fbs
40 VariableMessageSign.fbs
41 CarbonEmission.fbs
48 SignalExecution.fbs
49 SignalRequest.fbs
50 CollisionWarning.fbs
51 RoutePlan.fbs
52 SpeedGuide.fbs
240 Ticket.fbs
255 Wildcard.fbs
```

## JSON -> Flatbuffers

以`MSG_SafetyMessage`为例：

```python
from python_fbconv.fbconv import FBConverter
    
    
test_json_str = b'{ "ptcType": 1, "ptcId": 867, "source": 4, "device": [ 0 ], "moy": 27641003, "secMark": 42374, "timeConfidence": "time000002", "pos": { "lat": 395788083, "lon": 1169048356 }, "referPos": { "positionX": -27709, "positionY": 915 }, "laneId": 1, "accuracy": { "pos": "a2m" }, "transmission": "unavailable", "speed": 1237, "heading": 12432, "motionCfd": { "speedCfd": "prec1ms", "headingCfd": "prec0_01deg" }, "size": { "width": 220, "length": 900 }, "vehicleClass": { "classification": "truck_Vehicle_TypeUnknown" } }' 
fb_convert = FBConverter()
ret_val, ret_buf = fb_convert.json2fb(23, test_json_str) ## 23是test_json_str 的类型，test_json_str 是 safetymessage类型的json字符串
```

ret_val返回0则为成功，ret_buf返回转换好的flatbuffers。

## Flatbuffers -> JSON

以`SafetyMessage`为例：

```python
from python_fbconv.fbconv import FBConverter
    

fb_convert = FBConverter()
ret_val, ret_json_val = fb_convert.fb2json(23, ret_buf) ## 23是test_json_str 的类型，ret_buf 是 safetymessage类型的flatbuffers
```

ret_val返回0则为成功，ret_json_val返回转换好的json串。



### 设置fbs文件目录

```python
from python_fbconv.fbconv import FBConverter


fb_convert = FBConverter()
fb_convert.set_schemafile_dir(b'/home/jerry/.zbmec/fbs') ## 设置fbs 文件存放路径
```


### 错误码


  0  ->  解析成功
 -1  ->  输入包含空指针
 -2  ->  Parser找不到
 -4  ->  生成JSON失败
 -8  ->  缓冲区溢出
-16  ->  未定义异常
-32  ->  解析JSON异常
