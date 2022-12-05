#### 简介
SUMO仿真平台
#### 注意事项
Python >= 3.7

1. 仿真运行后会在data/network文件夹下生成检测器和轨迹结果文件，代码上传时需要将其删除(后续将修改additional文件避免这些结果文件的生成)
2. 添加.idea/.vscode此类IDE或编辑器生成的项目配置文件到.gitignore中，避免上传冗余文件
3. 如有在每个迭代步通过Traci接口读取SUMO内部数据的重复需求时，使用`subscribe`而不是`getxxxx`方法，提高运行速度

#### 代码要求
1. 外部调用的接口需要Type hint，为了兼容3.7版本Python，请使用Typing库中的List, Dict, Tuple而非原生数据结构list, dict, tuple，注解示例`x: List[int]`(√, python>=3.7)   `x:list[int]`(×, python>=3.8)
2. 注释风格建议使用Google，也可以使用reStructuredText，在外部模块调用的函数需要提供注释