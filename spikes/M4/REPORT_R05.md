# M4-R05｜转换计数专项

日期：2026-10-29。synthetic / prototype_only。当前小轮验证通过，M4 整体 PARTIAL。

## 开发内容
新增 transitions.py 统一计数函数，state_features 配置绑定入口新增 flow_change_count，特征语义版本升为 m4-r05-v1。流量只比较窗内相接的有效统计区间；活动按配置阈值判断，未知/缺口不连接。单个区间缺少比较证据则为null；明确连续比较且无变化才为0。
人员窗尾观测虽不贡献时长，但当之前有效状态严格未过TTL时，可以构成转换证据。补上这类终点计数：20秒有人、30秒无人、TTL20时计1；TTL10时恰过期，不推断转换。未知中断同样不连接。窗口左边界不从未提供的窗外状态推断变化。

## 自检和交叉核对
- 流量 active→inactive→active 手算2次；有缺口不比较；连续同状态为0。
- 人员窗尾变化、同状态、TTL相等和unknown中断专项检查。
- 100组固定随机布尔序列，以直接相邻比较为独立参考核对计数。
- 单独运行专项与完整M3/M4/契约/启动回归。实际完整108 passed in 6.25s；日志 evidence/r05_tests.txt、r05_isolated_tests.txt。
- 本轮未发现回归失败，检查的是上述限定口径；同代理自查不代替独立Reviewer。

## 运行
```powershell
.\.venv-app\Scripts\python.exe -m pytest spikes/M4/tests/test_transitions.py -q -p no:cacheprovider
.\.venv-app\Scripts\python.exe -m pytest spikes/M4/tests spikes/SP-03/tests tests/contracts tests/smoke -q -p no:cacheprovider
```

## 剩余工作
十二项特征目前分布于基础流量、配置绑定状态和历史持续时长三个原型，并非完整统一输出。持续时长尚未接入统一配置与引用验证，也没有持久化检查点。下一小轮先做统一计算入口和结果对照，再做检查点与恢复，不以分散函数存在认定M4已验收。
