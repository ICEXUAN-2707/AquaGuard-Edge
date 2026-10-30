# SP-03 报告索引

当前状态 PARTIAL；回放基础已验证，完整窗口尚未实现，独立 Reviewer 待指定。

- [第 0—1 轮开发报告](REPORT_R01.md)：开发内容、思路、实际验证、限制与组会演示。
- [运行说明与口径](README.md)
- evidence/tests.txt：5 passed。
- evidence/replay.jsonl：实际回放输出。

后续每轮新增 REPORT_Rxx.md，保留历史报告，不覆盖上一轮结论。

- [第 2 轮：窗口核心与 review](REPORT_R02.md)：固定截止、TTL、覆盖率和迟到旁路；完整 SP-03 仍为 PARTIAL。

- [第 3 轮：分源 TTL 与流式基础](REPORT_R03.md)：重启隔离、容量保护、一致性与自查修复。完整 SP-03 仍 PARTIAL。

- [第 4 轮：黄金边界与迟到追溯](REPORT_R04.md)：人工预期、流式迟到审计与配置引用修复；67 项回归通过，完整 SP-03 仍 PARTIAL。

- [四轮阶段审查](STAGE_REVIEW_R01_R04.md)：新发现容量恢复、启动资格和输出上限整改项，完整 SP-03 维持 PARTIAL。

- [第 5 轮：阶段审查整改](REPORT_R05.md)：容量恢复、启动资格、分批追赶、版本和入口一致性修复。

- [第 6 轮：三源综合黄金验证](REPORT_R06.md)：21 条输入、双窗手算和流式对照。
- [待确认口径表](DECISION_TABLE.md)：供 A/B/C 评审，未会签。

- [M3 技术总结与 M4 敏捷计划](../M4/PLAN.md)：技术链路、算法复杂度、验证边界及六轮开发/检查安排。
