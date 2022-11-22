#### 简介
SUMO仿真平台
#### 注意事项
Python >= 3.7

1. 仿真运行后会在data/network文件夹下生成检测器和轨迹结果文件，代码上传时需要将其删除(后续将修改additional文件避免这些结果文件的生成)
2. 添加.idea/.vscode此类IDE或编辑器生成的项目配置文件到.gitignore中，避免上传冗余文件

#### 代码要求
1. 外部调用的接口需要Type hint
2. 注释风格建议使用Google，也可以使用reStructuredText，在外部模块调用的函数需要提供注释