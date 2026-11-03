# 水知安文档导航

A部分最新入口：[A文档导航](spikes/A_文档导航.md)，统一收录项目地图、代码算法导读、实物实验方案及零基础采集手册；实物参数待核验，未宣称已完成硬件实验。

A/B新增 [第二轮交叉核对报告](spikes/AB_第二轮交叉核对.md)：内容完整性与异常边界修复、206项联合回归及真实日志重算。

A/B当前分支交叉对接与修复：[交叉自检报告](spikes/AB_交叉自检报告.md)，含200项回归和真实MQTT→B窗口/特征证据及限制。

A软件阶段最新入口：[收尾报告](spikes/A_软件阶段收尾报告.md)、[SP-02复现说明](../spikes/SP-02/README.md)、[软硬件结合开发手册](spikes/A_软硬件结合开发手册.md)、[采购确认](spikes/A_采购确认.md)。软件证据已整理，SP-02整体PARTIAL，待独立评审及实物联调。

当前工作分两条线并行：契约线已形成 V1.2 技术修订候选，待 A/B/C 会签后成为正式合同；Spike 线用独立小实验回答技术问题。候选 Schema/DTO 已在仓库中供审查和测试，业务模块的正式接口依赖仍以会签和 `contracts/CONTRACT_ACCEPTANCE.md` 的 C0–C2 放行为准。

## 按用途查找

|类别|主文档|用途和当前状态|
|---|---|---|
|项目入口|[README](../README.md)、[开发路线](project/DEVELOPMENT_PLAN.md)|本地 API/前端运行方法、Issue 顺序；I-001 基线已建立。|
|审计基线|[仓库审计](audit/REPO_AUDIT.md)、[能力差距](audit/GAP_ANALYSIS.md)、[依赖与协作风险](audit/DEPENDENCY_RISKS.md)|原始资料、实现差距、硬件/云端缺口。作为现状依据；不是任务实施说明。|
|契约评审|[当前状态与双线对接](contracts/STATUS.md)、[V1.2 修订候选](../reference/reference_02/00_Contracts_V1.2_修订候选.md)、[验收门槛](contracts/CONTRACT_ACCEPTANCE.md)、[联合评审报告](contracts/CONTRACT_JOINT_REVIEW_REPORT.md)、[历史合规探针](contracts/CONTRACT_COMPLIANCE.md)|候选规范及机器文件已修订，静态测试通过；D1–D5 仍待 A/B/C 会签。评审报告和早期建议稿是问题与决策背景，不代表正式批准。|
|Spike 派工|[Spike 总则与 A 任务单](spikes/A_任务单.md)、[B 任务单](spikes/B_任务单.md)、[SP-06 编码计划](spikes/SP-06_编码计划.md)、[组长分发话术](spikes/组长分发话术.md)|零基础成员的执行说明、SP-06 阶段计划、验收要求和可复制消息。|
|C 部分实操|[SP-06 原型说明](../spikes/SP-06/README.md)、[人工测试操作指南](../spikes/SP-06/MANUAL_TEST_GUIDE.md)、[测试数据集](../spikes/SP-06/data/manual_cases.json)、[进度报告](../spikes/SP-06/REPORT.md)|运行 SQLite/Mock 原型、按步骤人工检查状态，并记录证据。|
|Spike 管理材料|[团队分工手册](spikes/Technical_Spike_团队分工手册.docx)、[Issue 模板](spikes/templates/SPIKE_ISSUE_TEMPLATE.md)、[报告模板](spikes/templates/SPIKE_REPORT_TEMPLATE.md)、[任务跟踪表](spikes/SPIKE_TRACKER.csv)|六项 Spike 的原始分工和记录工具。原手册早于 SP-06 由 C 负责的最新决定；以任务单和跟踪表为准。|
|技术选型与云接入|[I-001 上游与运行栈](project/UPSTREAM_REVIEW.md)、[IoTDA 集成计划](integration/IOTDA_INTEGRATION_PLAN.md)、[IoTDA 人工对接操作指南](integration/IoTDA_人工对接操作指南.md)|候选上游许可结论、已验证运行栈、控制台操作步骤和真实云端前置条件。SP-05/06 由 C 负责。|

## 两条线当前要做什么

### 契约评审线

三条工作线各安排一位评审，按 V1.2 候选规范中的 D1–D5 逐项记录决定、备选方案、字段影响、兼容策略和验收例子。候选 Schema、样例和 DTO 已同步修订并通过静态测试；联合裁决尚未完成，正式放行需按 `contracts/CONTRACT_ACCEPTANCE.md` 记录签名和证据。

### Spike 技术验证线

- A 可并行推进 SP-02（无硬件即可先做）和 SP-01（有实物且电气参数复核后做）。
- B 先做 SP-03，再根据窗口输出做 SP-04。
- C（项目统筹）做 SP-05 和 SP-06；SP-06 与 IoTDA SDK 解耦，由 SQLite+Mock Cloud 验证事务、回滚与重启恢复。
- 所有 Spike 的代码、输入、测试和证据放在 `spikes/SP-xx/`。若文件夹不存在，由 Owner 创建；先复制 Issue 与报告模板。

每个实验结束必须标记 `PASS`、`PARTIAL`、`FAIL` 或 `BLOCKED`，附真实命令、原始日志、限制和下一步。未执行不算通过；没有板卡或云账号时如实标记阻塞，不拿模拟结果冒充实物或 IoTDA 证据。

## 一次启动顺序

1. C 在任务表补齐每个 Spike 的 Reviewer、Issue 和证据目录；SP-06 Owner 已由 C 承担。
2. A/B 按各自任务单开工；契约评审会议同步安排。
3. A 把实际观测字段、时间戳和重启现象交给 B；B 把对字段质量和时间语义的疑问交回契约线。
4. B 将窗口/模型的可行性结论交给 M6 Owner；SP-06 Owner 与 SP-05 对齐 Outbox 与云回执。
5. 六份报告和 D1–D5 决议都完成后，再批准正式模块实现与合同版本。

## M4 技术验证交付
M4 离线模拟原型及各轮报告见 [M4交付入口](../spikes/SP-03-features/README.md)。十二特征、回放快照与候选DTO已演示；正式验收仍待独立复核、契约会签及硬件语义验证。

## M5 规则验证交付
[M5交付入口](../spikes/SP-04/README.md)：离线模拟规则六轮已收尾，默认10秒；SP-04整体PARTIAL，真实trial/ML/独立验收待完成。最终回归171项含既有检查，不等于项目完成率。

## B部分阅读地图与后续路线
[B部分项目地图](project/B_PROJECT_MAP_AND_NEXT_STEPS.md)：下一阶段如何做、推荐阅读顺序、逐份报告用途、代码/证据位置及验收边界。

[B部分文档自检](project/B_DOCUMENT_AUDIT.md)：2026-11-03核对文档收录、链接及共享入口。
