# M5-R03｜规则引擎与候选情境输出

日期：2026-10-29。synthetic / prototype_only。R03原型通过，M5整体PARTIAL，尚非独立验收。

## 开发
新增src/rules.py，将可信门控接入IDLE/ATTENDED_FLOW/POSSIBLE_UNATTENDED_FLOW/UNKNOWN分支。持续交集>=10秒才输出可能无人流水，9.9秒拒判。规则分数为null，输出通过SituationAssessment候选DTO。
原因码包含主判定与水接触/人员证据降级说明；质量等级继承门控。规则语义版本和配置摘要进入model_version。assessment_id包含窗口、特征版本、规则配置和证据摘要，不依赖本机快照路径。新鲜窗口的固定结果身份不随查询时刻改变，过旧拒判身份包含评估时刻，避免覆盖原结论。

## 交叉检查
不是直接填造特征：从原始观测经M3对齐、M4计算/快照，构造9.9、10、10.1秒独立场景，核对情境与原因。另检验无流水、有人流水、wet但有人流水、恰好10秒窗口新鲜边界、过旧身份和更改规则配置身份。
专项7项通过；完整回归146 passed in 7.22s，含已有M3/M4/契约/启动。日志evidence/r03_isolated_tests.txt、r03_tests.txt。
新增demo.py，读取实际M4演示工件并保存evidence/r03_assessments.json。两个窗口分别ATTENDED_FLOW、UNKNOWN：后一窗flow没有恰好窗尾统计间隔，按M3保守语义拒判。这揭示上游限制，不绕过质量门槛制造分类。

## 运行
先有M4演示工件（没有则运行M4/demo.py）：
```powershell
.\.venv-app\Scripts\python.exe spikes/M5/demo.py
.\.venv-app\Scripts\python.exe -m pytest spikes/M5/tests/test_rules.py -q -p no:cacheprovider
.\.venv-app\Scripts\python.exe -m pytest spikes/M5/tests spikes/M4/tests spikes/SP-03/tests tests/contracts tests/smoke -q -p no:cacheprovider
```

## 自查与未完成
分支顺序先门控后分类，已知情境按flow与presence互斥分支；水接触不改分类，没有实现任何通知或安全信号取消。固定阈值合理性仍待真实trial，反例中静止人员未检出可能产生误判。规则配置完整语义校验、全部手写场景自动接入、更多恢复/故障和基线比较需后续轮次补齐。本轮同代理自检不代替独立Reviewer。
下一轮：扩展端到端场景矩阵与独立决策参考，核对原因和质量，再进行基线/阈值敏感性及恢复对照。
