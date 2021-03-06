# coding: utf-8
# Type: Private Author: BaoChuan Wang


'''
描述:
纯粹模仿学习效果测试!
在Town2中模拟,城市环境,同时过街过后岔路少,不会出现太多agent车道线和车辆行驶路线不一致的情况
carla agent没有红绿灯行为
添加action噪声到carla agent,使RL agent学会纠正

FIXME: 长时间运行后会有carla agent控制的车或者其他车消失

TODO: 增加红绿灯等state(根据Agent里面的代码),测试全模仿学习

FIXME
 推荐在UE中绘制出车道线来debug
 debug发现,是因为90弯道的拟合效果不太好,所以这里放宽一些车道线条件!

TODO:任务来源查看readme,或使用ide查看TODO

在极其复杂的城市道路,而不是高速环境下进行学习

由于carla agent绘制的车道线和车辆行驶路线存在不一致的情况!
所以在Town1或者Town2等岔路少的地方模拟


'''



from ReinforcementLearning.ImitationLearning.ModelTrainers.ModelTrainers import CarlaAgentOfLaneFollowFloatActionTrainer_v1
import random
import time
import numpy as np
from ReinforcementLearning.Modules.Environments.Rewards import SafeDriveDistanceCost
from ReinforcementLearning.Modules.Agents.DDPG_Agent import DDPG_Agent_GAL_v1
from ReinforcementLearning.Modules.Environments.Environments_laneFollow import LaneFollowEnv_v1
from ReinforcementLearning.Modules.Environments.Actions import ContinuousSteeringVelocityBrakeAction_v1
from ReinforcementLearning.ImitationLearning.ModelTrainers.ModelTrainers import FloatActionTrainer

server_config = {
    "10.10.9.128": [2000],
}
# RL的agent只有3个
n_workers_in_each_port = 3


env_dict = {}
worker_kwargs = {}
model_kwargs = {}
carla_egg_path="/home/wang/Desktop/carla/PythonAPI/carla/dist/carla-0.9.5-py2.7-linux-x86_64.egg"
carla_pythonAPI_path="/home/wang/Desktop/carla/PythonAPI/carla"
use_pre_calculated_g = False
gamma = 0.99
for ip in server_config:
    for port in server_config[ip]:
        for i in range(n_workers_in_each_port):
            name = 'W_%s' % (str(ip) + "_" + str(port) + "_" + str(i))  # worker name
            env = LaneFollowEnv_v1(
                #'''
                # 有些地方道路曲率大(90度),车道线拟合不好导致认为出了车道,因此放宽车道条件
                # 但是放宽了条件后注意车辆会出现随意切换车道的现象!
                # 不过只要预先训练好,就根本不会出现变道的情况
                #'''
                maximum_distance_to_lane=0.5,
                # 建议只在debug阶段plot
                plot_lane_on_UE=False,
                use_random_start_point=True,
                carla_egg_path=carla_egg_path,
                carla_pythonAPI_path=carla_pythonAPI_path,
                carla_UE_ip=ip,
                carla_UE_port=port,
                wait_time_after_apply_action=0.1,
                action_replace=ContinuousSteeringVelocityBrakeAction_v1(),
                reward_replace=SafeDriveDistanceCost(),
                minimum_velocity=0.5,
                drive_time_after_reset=2.0,
                kwargs_for_done_condition={
                    "minimum_action_taken_on_low_velocity": 0
                }
            )
            env_dict[name] = env
            model_kwargs[name] = {
                "use_pre_calculated_g": use_pre_calculated_g,
                "gamma":gamma
            }
            worker_kwargs[name] = {
                # 因为主要模仿,所以不进行学习
                "do_RL_learn": False,
                #"start_variance_for_each_action": (1.0, 1.0),
                "start_variance_for_each_action": (.0, .0),
                "variance_decay_ratio_for_each_action": (0.995, 0.995),
                "variance_decay_step": 10,
                "start_offset_for_each_action": (0.0, 0.0),
                "offset_decay_value_for_each_action": (0.00, 0.00),
                "offset_decay_step": 2000
            }

agent = DDPG_Agent_GAL_v1(env_prototype_dict_for_workers=env_dict,
                  save_dir="./ddpg_ckpt_IL/",
                  # 这两个参数是嵌套字典
                  kwargs_for_model_dict=model_kwargs,
                  kwargs_for_worker_dict=worker_kwargs,
                  kwargs_for_global_model={
                      # 预先求得准确q值给数据集
                      "use_pre_calculated_g":use_pre_calculated_g,
                        "gamma":gamma
                  })
carla_model_trainer = CarlaAgentOfLaneFollowFloatActionTrainer_v1(
    # 引导RL学习,需要将lr调低,主要模仿则调高一些
    lr=0.001,
    # 给agent添加一定噪声
    variance_for_each_action=(.5,.5),
    # 输入state
    input_placeholder=agent.global_model.S,
    # 输出state的频率
    output_graph=agent.global_model.a,
    action_space_size=(agent.action_space,),
    tf_sess=agent.sess,
    # 无视红绿灯
    ignore_traffic_light=True,
    kwargs_for_env={
        'plot_lane_on_UE':False,
        'carla_egg_path':carla_egg_path,
        'carla_pythonAPI_path':carla_pythonAPI_path,
            # 随意选择一个ip和port
        'carla_UE_ip':list(server_config.keys())[0],
        'carla_UE_port':server_config[list(server_config.keys())[0]][0],
    }
)
# 然后agent先启动
agent.start()

# 之后以一定频率每次给一个数据集训练,state随机,但是action只是油门1,转向0,预期学习到在任何情况下都是油门1,转向0
while 1:
    # carla train里面内置训练和频率控制函数
    carla_model_trainer.step()
