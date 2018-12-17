from env import AD_env
from RL_brain import DoubleDQN
import csv
import numpy as np
import pandas as pd
import copy

def run_env(budget, auc_num, e_greedy, budget_para):
    env.build_env(budget, auc_num) # 参数为训练集的(预算， 总展示次数)
    # 训练
    step = 0
    print('data loading\n')
    train_data = pd.read_csv("../../data/normalized_train_data.csv", header=None)
    train_lr = pd.read_csv("../../data/train_lr_pred.csv", header=None).iloc[:, 1].values # 读取训练数据集中每条数据的pctr
    train_avg_ctr = pd.read_csv("../../transform_precess/train_avg_ctrs.csv", header=None).iloc[:,1].values # 每个时段的平均点击率
    # 预算及剩余拍卖数量区间
    budget_scalar = budget
    auc_num_scalar = auc_num

    records_array = [] # 用于记录每一轮的最终奖励，以及赢标（展示的次数）
    for episode in range(300):
        # 初始化状态
        state = env.reset(budget, auc_num) # 参数为训练集的(预算， 总展示次数)
        # 此处的循环为训练数据的长度
        # 状态初始化为预算及拍卖数量，在循环内加上拍卖向量值

        # 重置epsilon
        RL.reset_epsilon(0.9)

        print('第{}轮'.format(episode + 1))
        total_reward = 0
        total_reward_clks = 0
        total_imps = 0
        real_clks = 0 # 数据集真实点击数（到目前为止，或整个数据集）
        for i in range(len(train_data)):
            # auction全部数据
            # random_index = np.random.randint(0, len(train_data))
            # auc_data = train_data.iloc[random_index: random_index + 1, :].values.flatten().tolist()
            auc_data = train_data.iloc[i: i + 1, :].values.flatten().tolist()
            auc_data_next = train_data.iloc[i + 1: i + 2, :].values.flatten().tolist()[0: 16]

            # auction所在小时段索引
            hour_index = auc_data[18]

            # auction特征（除去click，payprice, hour）
            feature_data = auc_data[0:16]

            # print(data.iloc[:, 0:15]) # 取前10列的数据，逗号前面的冒号表示取所有行，逗号后面的冒号表示取得列的范围，如果只有一个貌似就表示取所有列，行同理
            state[2: 18] = feature_data
            state_full = np.array(state)

            # 预算以及剩余拍卖数量缩放，避免因预算及拍卖数量数值过大引起神经网络性能不好
            # 执行深拷贝，防止修改原始数据
            state_deep_copy = copy.deepcopy(state_full)
            state_deep_copy[0], state_deep_copy[1] =  state_deep_copy[0] / budget,  state_deep_copy[1] / auc_num
            if train_lr[i] >= train_avg_ctr[int(hour_index)]:

                # RL代理根据状态选择动作
                action = RL.choose_action(state_deep_copy, train_lr[i], e_greedy)  # 1*17维,第三个参数为epsilon

                # RL采用动作后获得下一个状态的信息以及奖励
                # 下一个状态包括了下一步的预算、剩余拍卖数量以及下一条数据的特征向量
                state_, reward, done, is_win = env.step(auc_data, action, auc_data_next)
                # RL代理将 状态-动作-奖励-下一状态 存入经验池
            else:
                action = 0 # 出价为0，即不参与竞标
                state_, reward, done, is_win = env.step(auc_data, action, auc_data_next)
            # 深拷贝
            state_next_deep_copy = copy.deepcopy(state_)
            state_next_deep_copy[0], state_next_deep_copy[1] = state_next_deep_copy[0] / budget, state_next_deep_copy[1] / auc_num
            RL.store_transition(state_deep_copy.tolist(), action, reward, state_next_deep_copy)
            if is_win:
                total_reward_clks += reward
                total_imps += 1

            real_clks += int(auc_data[16])
            # 当经验池数据达到一定量后再进行学习
            if (step > 1024) and (step % 4 == 0):
                RL.learn()

            # 将下一个state_变为 下次循环的state
            state = state_

            if i % 1000 == 0:
                now_spent = budget - state_[0]
                if total_imps != 0:
                    now_cpm = now_spent / total_imps
                else:
                    now_cpm = 0
                print('episode {}: 出价数{}, 赢标数{}, 当前点击数{}, 真实点击数{}, 预算{}, 花费{}, CPM{}'.format(episode, i,
                                                                                     total_imps, total_reward_clks, real_clks,
                                                                                     budget, now_spent, now_cpm))
            # 如果终止（满足一些条件），则跳出循环
            if done:
                if state_[0] < 0:
                    spent = budget
                else:
                    spent = budget - state_[0]
                cpm = spent / total_imps
                records_array.append([total_reward_clks, i, total_imps, budget, spent, cpm, real_clks])
                break
            step += 1
        episode_record = records_array[episode]
        print('\n第{}轮: 出价数{}, 赢标数{}, 总点击数{}, 真实点击数{}, 预算{}, 总花费{}, CPM{}\n'.format(episode,
                    episode_record[1], episode_record[2], episode_record[0], episode_record[6], episode_record[3], episode_record[4],
                                                                              episode_record[5]))
        print('训练结束\n')

    records_df = pd.DataFrame(data=records_array, columns=['clks', 'bids', 'imps(wins)', 'budget', 'spent', 'cpm', 'real_clks'])
    records_df.to_csv('../../result/DQN_train_' + str(budget_para) + '.txt')


def test_env(budget, auc_num, budget_para):
    env.build_env(budget, auc_num) # 参数为测试集的(预算， 总展示次数)
    state = env.reset(budget, auc_num) # 参数为测试集的(预算， 总展示次数)

    test_data = pd.read_csv("../../data/normalized_test_data.csv", header=None)
    test_lr = pd.read_csv("../../data/test_lr_pred.csv", header=None).iloc[:, 1].values  # 读取测试数据集中每条数据的pctr
    test_avg_ctr = pd.read_csv("../../transform_precess/test_avg_ctrs.csv", header=None).iloc[:,1].values  # 测试集中每个时段的平均点击率

    result_array = []  # 用于记录每一轮的最终奖励，以及赢标（展示的次数）

    total_reward_clks = 0
    total_imps = 0
    real_clks = 0
    for i in range(len(test_data)):
        if i == 0:
            continue
        # auction全部数据
        auc_data = test_data.iloc[i: i + 1, :].values.flatten().tolist()

        # auction所在小时段索引
        hour_index = auc_data[18]

        # 二维矩阵转一维，用flatten函数
        # auction特征（除去click，payprice）
        feature_data = auc_data[0:16]
        state[2: 18] = feature_data
        state_full = np.array(state)

        state_deep_copy = copy.deepcopy(state_full)
        state_deep_copy[0], state_deep_copy[1] = state_deep_copy[0] / budget, state_deep_copy[1] / auc_num
        if test_lr[i] >= test_avg_ctr[int(hour_index)]:
            # RL代理根据状态选择动作
            action = RL.choose_best_action(state_deep_copy)

            # RL采用动作后获得下一个状态的信息以及奖励
            state_, reward, done, is_win = env.step(auc_data, action)
        else:
            action = 0
            state_, reward, done, is_win = env.step(auc_data, action)

        if is_win:
            total_reward_clks += reward
            total_imps += 1

        real_clks += int(auc_data[16])

        if done:
            if state_[0] < 0:
                spent = budget
            else:
                spent = budget - state_[0]
            cpm = spent / total_imps
            result_array.append([total_reward_clks, i, total_imps, budget, spent, cpm, real_clks])
            break

    print('测试集中: 出价数{}, 赢标数{}, 总点击数{}, 真实点击数{}, 预算{}, 总花费{}, CPM{}\n'.format(result_array[1], result_array[2],
                                                                    result_array[0], result_array[6], result_array[3],
                                                                    result_array[4], result_array[5]))
    result_df = pd.DataFrame(data=result_array, columns=['clks', 'bids', 'imps(wins)', 'budget', 'spent', 'cpm', 'real_clks'])
    result_df.to_csv('../../result/DQN_result_' + str(budget_para) + '.txt')


if __name__ == '__main__':
    e_greedy = 0.9 # epsilon

    env = AD_env()
    RL = DoubleDQN([action for action in np.arange(0, 300)], # 按照数据集中的“块”计量
              env.action_numbers, env.feature_numbers,
              learning_rate=0.01, # DQN更新公式的学习率
              reward_decay=0.9, # 奖励折扣因子
              e_greedy=e_greedy, # 贪心算法ε
              replace_target_iter=2000, # 每200步替换一次target_net的参数
              memory_size=10000, # 经验池上限
              batch_size=1024, # 每次更新时从memory里面取多少数据出来，mini-batch
              # output_graph=True # 是否输出tensorboard文件
              )

    budget_para = [1/2]
    for i in range(len(budget_para)):
        train_budget, train_auc_numbers = 22067108*budget_para[i], 328481
        test_budget, test_auc_numbers = 14560732*budget_para[i], 191335
        run_env(train_budget, train_auc_numbers, e_greedy, budget_para[i])
        test_env(test_budget, test_auc_numbers, budget_para[i])
    # RL.plot_cost() # 观看神经网络的误差曲线