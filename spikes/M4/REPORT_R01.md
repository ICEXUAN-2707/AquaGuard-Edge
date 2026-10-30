# M4-R01 开发报告｜特征定义与手算

日期：2026-10-29。状态：本轮定义基础 PASS，M4 整体 PARTIAL。独立 Reviewer 待指定。synthetic / prototype_only。

## 开发内容和思路
先固定含义再写计算引擎：data/feature_dictionary.csv 列出候选十二项特征、单位和缺失规则；INPUT_DESIGN.md 设计可追溯内部输入；data/hand_cases.json 保存四组人工预期。tests/test_definitions.py 只是独立算术核对，不是正式特征引擎。

四组例子分别说明：10秒6 L/min不因20秒缺失变成2；10秒6与20秒0的加权均值才是2；全缺失保留null；人员未知区间不当作无人，已知20秒中在场10秒占比为1/2。

## 代码自检与交叉检查
首次字典对候选 Schema 校验发现 data_coverage_ratio 字段前多一个空格；修复后通过。此校验不修剪字段，防止问题被掩盖。手算值与独立算术逐项对照，十二字段与当前候选 Schema 精确对应，运行 M3/契约/启动回归。

实际命令及日志：
```powershell
.\.venv-app\Scripts\python.exe -m pytest spikes/M4/tests spikes/SP-03/tests tests/contracts tests/smoke -q -p no:cacheprovider
```
结果见 evidence/r01_tests.txt。测试通过仅说明字典字段与四组算术一致，不代表已实现全部特征或 M4 行为验证通过。

## 未完成与下一轮
十二特征中本轮仅对五项基础计算提供四组手算，不宣称十二项黄金值完整。下一轮实现有效时间段与基础流量特征，扩充不等采样、重叠冲突、窗尾点、缺引用和配置错版本反例。持续状态、检查点、FeatureWindow 完整输出后续逐轮实现。M3 未完成口径仍明确继承为实验假设。
