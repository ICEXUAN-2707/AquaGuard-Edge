# 契约评审线当前状态

## 当前版本

联合评审已形成 V1.2 技术修订候选，机器 DTO 的 `schema_version` 为 `1.1`。候选规范、9 份 JSON Schema、联合样例、场景 S01 与 `edge/contracts/` 已同步更新。候选版静态验证已运行：Schema 测试 45 项通过；DTO/API 模型与服务启动测试 32 项通过。运行命令和分层门槛见 [契约验收门槛](CONTRACT_ACCEPTANCE.md)。

**当前仍是候选版。** A/B/C 会签（C0）尚未完成；测试通过证明候选文件内部结构和 DTO 模型可验证，不代表接口已正式冻结，也不代表 I-003–I-009 的真实业务入口已经调用这些模型。未通过 C0 前，不要把候选 Schema 变更提交为正式冻结版本。

## Spike 线如何使用候选版

1. A/B 可以把 [V1.2 候选规范](../../reference/reference_02/00_Contracts_V1.2_修订候选.md) 和 `reference/reference_02/contracts/` 当作当前讨论基线，验证技术方案能否产出候选字段。
2. 自己新增的消息、输入文件和报告必须标明 `prototype_only`。不要把这个标记塞进 `SensorObservation` 等对象内部，因为正式 Schema 禁止未定义字段；在文件名、README、报告或单独 sidecar 标记即可。
3. 如果 Spike 发现候选字段不够用，保存最小正反例并把建议交给契约评审线；不要直接编辑 `reference/`、`edge/contracts/` 或生产 API。
4. C0 会签完成后，组长在任务表公布已批准版本、提交号/文件哈希和 `1.0` 历史读取策略。此后 Spike 结论再进入正式实现 Issue。

## 评审文件职责

- [V1.2 候选规范](../../reference/reference_02/00_Contracts_V1.2_修订候选.md)：CC01–CC12 的字段和语义技术方案。
- [联合评审报告](CONTRACT_JOINT_REVIEW_REPORT.md)：发现、D1–D5 决议包和评审范围。
- [验收门槛](CONTRACT_ACCEPTANCE.md)：C0–C5 的进入条件、可观察断言和当前证据。
- [V1.1 合规探针报告](CONTRACT_COMPLIANCE.md)：旧 1.0 Schema 的历史缺陷，不用于否定已更新的候选文件。
