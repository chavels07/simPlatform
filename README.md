#### 简介
SUMO仿真平台
#### 配置要求
Python >= 3.7
SUMO >= 1.8.0

#### 实现功能
* 仿真场景测试
* 算法性能评测

#### 开始使用
1. SUMO安装(上官网)
2. 仿真场景文件
3. 初始化配置文件
4. 仿真运行
5. 测评结果输出

#### 项目结构
SimPlatform
├─bin
├─data
│  ├─evaluation
│  ├─junction
│  ├─network
│  │  └─route
│  ├─output
│  └─trajectory
├─docs
├─logs
├─simulation
│  ├─application
│  ├─connection
│  ├─evaluation
│  ├─information
│  ├─lib
│  ├─test
│  └─utils
└─SumoNet
    └─DemandFile

为每一个包/文件夹添加功能说明


#### 代码设计风格要求
* 外部调用的接口需要Type hint，为了兼容3.7版本Python，请使用Typing库中的List, Dict, Tuple而非原生数据结构list, dict, tuple，注解示例`x: List[int]`(√, python>=3.7)   `x:list[int]`(×, python>=3.8)
* 注释风格建议使用Google，也可以使用reStructuredText，在外部模块调用的函数需要提供注释

#### 注意事项
* 仿真运行后会在data/network文件夹下生成检测器和轨迹结果文件，代码上传时需要将其删除(后续将修改additional文件避免这些结果文件的生成)
* 添加.idea/.vscode此类IDE或编辑器生成的项目配置文件到.gitignore中，避免上传冗余文件
* 如有在每个迭代步通过Traci接口读取SUMO内部数据的重复需求时，使用`subscribe`而不是`getxxxx`方法，提高运行速度

#### 参考资料
* SUMO信号灯控制
* SUMO车辆控制