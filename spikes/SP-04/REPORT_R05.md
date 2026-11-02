# M5-R05｜基线与阈值对照

日期：2026-10-29。synthetic / prototype_only。M5整体PARTIAL。

## 开发内容
新增src/scenarios.py独立标准库数据构造；data/evaluation_trials.json人工描述8个操作场景与二元候选目标；evaluate.py经M3/M4实际计算比较B0单流水筛查、B1即时多源、B2时序规则（5/10/15秒）。比较任务统一为“是否产生可能无人流水候选”，不把B0称三分类模型。
B1/B2使用同一质量门控；B0只要求flow证据，不要求人员，这是特征可用性差异，不能把全部收益归因于时序。

## 实际结果（仅这8个合成场景）
|方案|命中正例|误触发|拒判正例|拒判负例|
|---|---|---|---|---|
|B0 flow|3|4|0|0|
|B1即时|2|3|1|0|
|B2 5秒|2|3|1|0|
|B2 10秒|2|1|1|2|
|B2 15秒|1|1|2|2|

10秒相对即时少两次误触发，但这两例变为UNKNOWN，不能算正确负例。15秒进一步丢失10秒正例。默认继续按用户批准10秒，不用这8个合成样本宣称最优。所有拒判在指标中单列，positive_recall_all分母包含被拒正例。

## 独立真值与不可区分反例
场景目标来自手写操作注释，而非规则输出；但这是人为构造的模拟目标，不是实际人员实验日志。短暂离开后将返回的未来操作对当前窗口不可见，因此延后提醒/拒判有合理性，不能由此声称识别了操作者未来意图。
“实际静止在场但传感器未检出”与“离开20秒”的原始输入相同、目标相反，所有规则给出相同候选，误触发无法通过当前观测消除。说明传感能力边界，不暗改标签掩盖错误。

## Review与回归
首次独立运行发现导入顺序依赖，改为先加载门控以建立M4/M3路径。新增指标交叉核对：每方案tp/fp/tn/fn与两类拒判合计8；手算B0/B1/B2计数；不可区分输入输出相同。
完整回归166 passed in 12.48s（含既有M3/M4/契约/启动），日志evidence/r05_tests.txt。同代理自查，非独立验收。

## 重跑与输出
```powershell
.\.venv-app\Scripts\python.exe spikes/SP-04/evaluate.py
.\.venv-app\Scripts\python.exe -m pytest spikes/SP-04/tests spikes/SP-03-features/tests spikes/SP-03/tests tests/contracts tests/smoke -q -p no:cacheprovider
```
逐场景输出/指标：evidence/r05/comparison.json；真实快照：evidence/r05/checkpoints/。

## 限制与下一轮
无训练/调参数据集或真实trial，不能报告泛化性能；8场景不足以得出统计结论。本轮没有测试真实延迟或训练ML。下一轮验证检查点恢复与未中断分类一致、重复评估与故障拒绝，再进行M5阶段收尾review。
