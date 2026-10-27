# I-002 契约联合评审稿（待 A/B/C 裁决）

> 2026-10-27：本草稿的技术建议已具体化为 `reference/reference_02/00_Contracts_V1.2_修订候选.md`、Schema/DTO/测试修订。此文件保留历史讨论记录，A/B/C 尚未会签；当前退出条件见 `CONTRACT_ACCEPTANCE.md`。

日期：2026-10-26。状态：**提案，未冻结，未用于业务实现**。依据 `CONTRACT_COMPLIANCE.md` 中 CC01–05 的实测探针、`reference/reference_02/00_Contracts_V1.1_深化规范.md` §1–3/7、M1 §5、M3 §5。`reference/` 全部保持原样。本稿可供 A/B/C 各一名评审直接逐项填写结论；三方通过前不得将这里的字段形状当作正式合同。

## 待裁决的问题和建议

|编号|建议方案|需明确的分歧与验收样例|
|---|---|---|
|CC01 三类观测 `value`|按 `sensor_type` 使用判别联合：flow 为 `pulse_count:int>=0`、`interval_ms:int>0`、`estimated_lpm:number>=0`、`calibration_id:string`；water 为 `wet:boolean|null`；presence 为 `present/moving/still:boolean|null`。保留现有外层字段和 `schema_version=1.0`，若决定更改公共结构，则一起评审版本策略。|确定 flow 心跳是否可只带质量而不带数值；`quality=valid` 时 water/presence 的 null 是否允许；`moving=true` 与 `present=false` 是否直接判 invalid。正例：三类各一条，未知 presence 一条；反例：sensor_type 与 value 类型错配。|
|CC02 未知布尔|采用 `null` 表示设备明确报告未知；字段缺失仅用于不具备该子测量或不完整原始包，接入层应标记 `quality=unknown/invalid`，不得自动补 `false`。|确认完整标准 DTO 是否允许省略某个子字段，及心跳与观测的区分。反例：失联输入被映射成 `wet=false`、`present=false`。|
|CC03 特征缺失|十二个特征键保留，但无法计算的数值允许 `null`；`water_contact` 允许 `null`；`presence_state` 使用 `present/absent/unknown`。`missing_mask` 应和源类缺失一致，计算者不得用 0 替代未知。|确认 `flow_change_count` 与 `presence_transition_count` 无连续证据时为 null 还是 0；确认 `data_coverage_ratio` 在无观测时是 0 还是 null。正例：三路全缺失；反例：`missing_mask.water=true` 且 `water_contact=false` 无新证据。|
|CC04 `sensor_summary`|建议三键 flow/water/presence，各含三态 `state`、`age_sec:number|null`、`coverage_ratio:0..1`；`state` 枚举分别 `active/inactive/unknown`、`wet/dry/unknown`、`present/absent/unknown`。保留当前机器字段 `source_observation_ids`，把 M3 的 `source_refs` 明确为文档别名。|`age_sec` 应基于窗口末端还是 `published_at`；质量标记与 coverage 计算是否计心跳；无有效观测时 `age_sec=null`。正例：一传感器沉默且窗口仍发布；反例：过 TTL 仍输出 dry/absent。|
|CC05 通用 API 错误|将 `details` 定义为按 `code` 区分的对象：`VERSION_CONFLICT` 必须带 `expected_version/actual_version`；普通 400/401/404/503 可为空对象或含有专属、安全可展示字段。|逐个列出公开错误码及细节；验证 409 能指出当前版本，不把内部堆栈返回给前端。|

## 同步确认的跨字段规则

1. `received_at` 与非空 `event_time` 必须为带时区 ISO8601。`DEVICE_SYNCED` 要有可信 `event_time`；`RECEIVED_FALLBACK` 可以为空。不可仅凭字段非空宣称设备时间可信。
2. 接入层只接收原始 `quality=valid/invalid/unknown`；`stale/duplicate/late` 是后续处理标签，不由设备自报为可信原始质量。
3. `source=hardware/simulation` 不扩充 `replay`；回放实验的 trial 身份另由受控实验元数据记录。确认 `source` 如何贯穿事件、Outbox 与 API 查询而不改现有公共事件 DTO。
4. `rules` 的 `model_score=null`。ML 的分数语义与校准状态需版本化声明；不能当事故概率展示。
5. `schema_version=1.0` 当前是九份 Schema 和样例共同值；“Contracts V1.1”是文档修订名。若改变任何已发布 DTO 的字段约束，评审需决定兼容性与版本号，不能只改一份文件。

## 评审记录栏

|工作线|评审人|日期|CC01–05 逐项结论或修改意见|确认的合同版本|
|---|---|---|---|---|
|A（采集/通信/云）|待填写|待填写|待填写|待填写|
|B（对齐/特征/推断）|待填写|待填写|待填写|待填写|
|C（事件/产品）|待填写|待填写|待填写|待填写|

## 裁决通过后的执行顺序

1. 在独立契约变更中同步更新主规范、九份 Schema 中受影响者、`examples.json` 和契约正反测试；记录每个字段的来源、单位、枚举与缺失语义，以及文件哈希。必要时新增 ADR。
2. 构造 S01–S12 固定输入与对应标准 DTO，特别覆盖三路缺失、乱序、重启、时钟降级、快速水接触和 ACK 重放。
3. 再实现 Pydantic DTO 与 I-003–I-009 模块。消费者只引用同一份正式模型，避免各模块私造兼容层。

本稿只解决审议材料的准备。I-002 的联合批准、正式合同修订、DTO 实现和验收测试仍未完成。
