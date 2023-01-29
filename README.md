#### 简介
SUMO仿真平台
#### 配置要求

* 版本

  Python >= 3.7
  SUMO >= 1.8.0

* 依赖包

  paho-mqtt

  traci/sumolib（需添加SUMO工具包目录至PYTHONPATH）

#### 实现功能
* 仿真场景测试
* 算法性能评测

#### 开始使用
1. **SUMO安装(上官网)**

2. **仿真场景文件**
  仿真场景文件存储于**data/network/**目录下，其中包含

  * SUMO仿真配置文件`.sumocfg`
  * 路网文件`.net.xml`
  * 检测器文件`detector.xml`(可选)
  * 车辆输入文件`.rou.xml`(目录下route文件夹内)

  仿真场景文件编写请参考SUMO官网的指导，需确保各文件的正确性，否则会在加载仿真场景时出现错退导致程序退出。
  各模块配置文件是以通过参数传递的形式输入仿真中，无需在`.sumocfg`文件中配置，若在此文件中以指定，程序会在下一步读取程序初始化配置文件中的入口文件并进行覆盖。

  使用测评功能时应提供测评程序所需的交叉口基础地图`json`文件，保存于**data/junction/**目录下。该文件可从路网MAP的`json`文件中解析获取生成。

3. **初始化配置文件**
  程序启动前会预先读取`setting.json`文件中指定的参数和输入文件路径完成程序的初始化配置。根据对应模块可分为三类配置内容：1) preliminary输入设定 2) simulation仿真参数 3) connection通信配置。下面给出各类别中参数的具体含义

  **preliminary**

  仿真未进行前设置的参数，其中各文件路径以相对路径的形式给出，顶层为SimPlatform文件夹

  * config_file_path：SUMO仿真配置文件路径
  * network_file_path：路网文件路径
  * route_file_path：车辆输入文件路径
  * detector_file_path：检测器文件路径
  * test_name：仿真测试名称
  * arterial_mode：干线信号灯拓展模式（需要进行干线信号协调控制为`true`）
  * await_start_cmd：仿真等待开始指令（立即执行仿真为`false`）

  **simulation**

  仿真运行过程中设置的参数，直接控制仿真的运行过程。拓展广播消息类型直接在pub_msg中添加对应字段

  * pub_msg：仿真运行过程中需要广播传输的消息内容，需要设置消息发送频率 (s)，频率为-1表示不发送该类消息
  * junction_region：路网中参与仿真的交叉口场景，空列表表示激活路网所有信号控制交叉口
  * sim_time_step：仿真单步步长 (s)
  * sime_time_limit：仿真时间时长 (s)

  **connection**

  仿真通信模块参数，暂只支持使用MQTT协议交互广播消息和控制指令

  * broker：消息服务器地址
  * port：端口号


4. **仿真运行**

   程序收到开始控制指令或自动运行后，会打开SUMO仿真软件的GUI窗口，仿真开始。仿真达到最大设置时间后运行结束，窗口自动关闭，每个参与仿真的交叉口场景的车辆轨迹信息将以`json`文件的形式保存在**data/trajectory/**目录下。程序通过CMD命令启动测评系统，将交叉口地图信息和车辆历史轨迹信息作为输入生成测评结果。

5. **测评结果输出**

   仿真运行的测评结果通过MQTT发送至服务器

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


#### 代码设计风格（推荐）
* 供外部其他模块调用的函数需要添加Type hint，为了兼容Python3.7版本，请使用Typing库中的List, Dict, Tuple等而非基础内置数据结构list, dict, tuple，注解示例`x: List[int]`(√, python>=3.7)   `x: list[int]`(×, python>=3.8)
* 注释风格建议使用Google，也可以使用reStructuredText，根据函数的复杂程度和入参数量灵活选择注释的详略程度，必要时需提供入参的注释说明

#### 其他注意事项

* 代码提交时应在.gitignore中过滤临时文件、仿真输出结果文件等，避免冗余文件上传
* 如有在每个迭代步通过Traci接口读取SUMO内部数据的重复需求时，使用**subscribe**而不是**getxxxx**方法，提高运行速度

**Task**

在仿真运行中需要与SUMO产生交互的任意一项事务或周期性动作定义为任务(Task)，根据信息传输的方向可以分为执行类任务(ImplementTask)和消息类任务(InfoTask)，前者对应平台向SUMO下发控制指令，后者对应平台从SUMO读取所需消息并进行后续发送或处理工作。每个任务创建时需要初始化所执行的函数、传递的参数、任务执行的时刻、循环周期时间(当任务需循环调用时赋值)和任务名称。系统平台维护一个任务堆，根据仿真时间确定应当执行堆中的哪些任务，执行时通过execute方法调用对应的函数，任务执行完毕后将从堆中移除。如果任务中循环周期时间给定，该任务为周期性任务，系统平台执行此任务后不会将其从任务堆中移除，并自动更新其下次需要执行对应的时刻。

任意需要对SUMO中的对象(车辆、信号灯等)进行控制的模块，均定义一个**create_xxx_task**方法，用于创建相应的执行类任务。该方法会被注册在平台核心**SimCore**类中的**task_create_func**容器中，并与接收的控制指令消息类型绑定，采用接收*SpeedGuide*、*SignalScheme*等消息后被动触发式的控制逻辑。

消息类任务一般是周期性执行的，因此在仿真运行前创建。根据初始化配置文件中定义各类消息的开关状态，调用**SimCore**类中的**activate_xxx_publish**函数创建这些任务，周期性任务一般不会从任务池中移除，因而无需在仿真运行过程中重复动态创建消息类任务。

**Event**

仿真运行到某一节点时(如开始、结束、评测结果输出等)对应一类事件，每一类事件出现之后触发该事件订阅的一系列回调函数。订阅信息由**core**模块中的**eval_event_subscribers**存储，并通过调用**subscribe_eal_event**函数订阅。在每一个节点处调用**emit_eval_event**函数执行所有的回调函数，由于这些回调函数可能需要传递不同的参数，因此在调用时有必要将所有可能需要使用传参以关键词参数的方式输入。回调函数命名形式统一为**handle_xxx_event**。

#### 参考资料
* SUMO信号灯控制
* SUMO车辆控制