# M4-R03 开发报告与项目技术验证进度

日期：2026-10-29。synthetic / prototype_only。M4 本轮原型验证通过，整体 PARTIAL；非独立验收。

## 内容与思路
新增 src/state_features.py：通过重建候选配置摘要核对窗口版本与宽度，然后按观测引用计算状态区间。实现 water_contact、presence_state、presence_occupied_ratio、presence_transition_count 及三源固定等权 data_coverage_ratio。与前轮流量函数组合，但不输出完整 FeatureWindow。
配置绑定只在新 state_features 入口强制执行；原 R02 calculate 是低层实验工具，仍不能独立当作正式完整入口。跨 boot 引用拒绝，避免未确定的恢复策略混入计算。
人员变化只在相邻已知区间接触时计数；未知或 TTL 缺口不连接。当前计数要求至少存在一对相邻已知区间，否则 null。单个持续区间是否足以输出0仍需口径评审。转换点恰在窗尾的计数规则也尚待后续专项定义。

## 多重检查
- 两窗三源黄金输入，状态与覆盖对照 M3；反转输入顺序不影响结果。
- 手算人员10秒在场与10秒未检出，占比1/2、变化1次；插入未知后占比1/3，不跨缺口计转换。
- 30组固定随机逐秒状态，以直接布尔求和和相邻比较作为独立参考，检查比例、变化数和终态。
- 缺失、TTL相等、配置错配及跨boot拒绝场景。
- 单独模块运行与全量受影响回归，日志 evidence/r03_isolated_tests.txt、r03_tests.txt。

运行：
```powershell
.\.venv-app\Scripts\python.exe -m pytest spikes/SP-03-features/tests spikes/SP-03/tests tests/contracts tests/smoke -q -p no:cacheprovider
```

## 技术验证阶段进度
|部分|已具备|尚未通过/实现|
|---|---|---|
|运行与契约|本地API启动基线、候选DTO及结构测试|候选契约会签、正式业务闭环|
|M3 / SP-03|模拟窗口、TTL、迟到、容量/追赶、三源黄金与流式对照|硬件时间、可信boot、精确跨重启覆盖、独立验收|
|M4|字典和内部接口提案、流量三特征、水接触/人员特征、总覆盖原型|flow_change_count、连续时长、检查点、完整FeatureWindow及综合恢复|
|M5 / SP-04|已有规则/模型实验规划|情境规则实现、trial采集、模型对比|
|M6/M7相关原型|仓库有SP-06 SQLite/Mock资料和代码|本轮未复验，不将其计为完整集成通过|
|硬件/MQTT/IoTDA|有任务与接入规划|本轮无实物/网络/云端验证证据|

不提供百分比：当前测试数量反映回归范围，不是整个项目完成比例。

## 下一轮
先明确转换计数（包含flow_change_count和窗尾点）、连续性判据，再实现跨窗流水/水接触/未检出人员持续时长。继续在独立原型内推进，不把M3候选口径当正式冻结。检查点与崩溃恢复后续独立轮次完成。
