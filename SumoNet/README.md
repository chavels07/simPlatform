rou与det文件未在sumocfg中input，需在main函数中定义
若net文件也在main中输入，可进一步删除

sumoBinary = checkBinary('sumo-gui')

sumoCmd = [sumoBinary, '-c', 'xxx.sumocfg', '-r', 'xxx.rou.xml','-a','xxx.det.xml']

traci.start(sumoCmd)

-----------------------------------------------------------------------------------
已取消不必要输出，当前仿真结束后无任何xml文件生成；

当前已解决检测器数量限制问题，基于2022.11.29的路网更新版本生成，后续更新路网需重新生成det.xml文件

msg_map.json文件过大，无法上传，未进行更改
