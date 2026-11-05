# 给 Codex 的下一轮指令（只读审计与集成拆解；不要直接大规模编码）

角色：水知安 AquaGuard Edge 项目高级系统架构师、工程集成与 PR 评审工程师。

**本轮已批准且不可擅改**：第十一届华为 ICT 大赛创新赛赛题一；最终交付采用方案 B（真实实体感知台架 + 三页 Web + IoTDA 及云上可访问应用 + 可复现实验/轻量 AI）。单受控水路；ADR-001～005 不变。请先阅读 `00_DELIVERY_BASELINE_V1.0.md`、`01_INTEGRATION_ROADMAP_G0-G4.md` 并对照现有仓库 `main` 最新内容。

## 第一步：核查，不得臆测已经完成

1. 确认 main 最新 SHA，读 `docs/project/PROJECT_STATUS.md`、`docs/contracts/STATUS.md`、`docs/contracts/CONTRACT_ACCEPTANCE.md`，列出真实已实现与未完成内容。
2. 重点审查 `edge/app.py`、`web/src/main.jsx`、`web/src/c-main.jsx`、`spikes/C-business/run.py`、`b_bridge.py`、`outbox.py`、A/B 原型服务/测试，识别整合到正式 runtime 的最小路径。
3. 检查 V1.2 Contracts 的 C0 会签是否真实完成。未完成就输出候选方案和 blocked 项，不假设评审通过。
4. 核对赛题一要求：CodeArts 使用证据、华为云部署、技术文档/代码/视频；从官方资料确认而不是把 IoTDA 控制台当作已部署应用。
5. 列出需要修改/新建的具体文件、接口、依赖、测试夹具、受影响模块和回滚方式。

## 第二步：输出 Issue 就绪表

分别对 DL-001 至 DL-011 给出：`owner`、`reviewer`、依赖、触及文件、验收命令、预计影响、风险；识别可以并行的工作。必须优先推荐一条**持续模拟输入 → M3/M4/M5 → M6/SQLite/Outbox → M8 真实浏览器**的纵向集成路径，不能先全仓重构。

## 第三步：输出且仅输出本轮交付

- `docs/product/DELIVERABLE_FREEZE_V1.md` 候选（不改变已批准范围）
- `docs/integration/DELIVERY_GAP_MAIN.md`
- `docs/integration/G1_VERTICAL_SLICE_SPEC.md`（最小自动在线闭环细化；含启动方式/接口/测试）
- `docs/integration/G1_ISSUES.md`（A/B/C 分工、PR 粒度、验收与依赖）
- `docs/competition/TOPIC1_COMPLIANCE_CHECKLIST.md`（每项要求附权威来源与待验事实）

不得在本轮创建华为计费资源、提交任何密钥、伪造 SDK 回执或真实硬件证据；不擅自签署合同冻结，不把 Mock/历史日志当作最新验收，不直接实现所有 Issue。需项目统筹确认后再开始 DL-002 正式集成。
