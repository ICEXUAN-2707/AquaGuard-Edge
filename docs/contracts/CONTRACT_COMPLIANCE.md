# Contracts V1.1 符合性审计

> 本文记录 2026-10-26 对历史 `schema_version=1.0` 的审计探针，不是当前 `1.1` 候选 Schema 的现状报告。修订及验收状态见 `reference/reference_02/00_Contracts_V1.2_修订候选.md` 与 `CONTRACT_ACCEPTANCE.md`；原探针证据保留用于回归对比。

本报告保留全部冻结资料原样。VERIFIED 表示静态文件事实或实际探针行为；不表示生产实现通过。规范内部冲突需 A/B/C 各一名评审共同裁决，依据 `reference/reference_02/00_Contracts_V1.1_深化规范.md` §7。

## 阻塞级冲突

主规范简称 V1.1；Schema 根目录为 `reference/reference_02/contracts/`。探针命令：`.\.venv\Scripts\python.exe audit/run_audit.py`；完整输入及校验错误见 `audit/evidence/contract_probes.json`。

|编号/优先级|VERIFIED 发现与代码位置|规范依据/影响|建议处理 INFERRED|
|---|---|---|---|
|CC01 P0|`SensorObservation.schema.json#/properties/value` 强制 present/moving/still，禁止其他键；`flow payload rejected`、`water payload rejected` 均拒绝|M1 §5 的 pulse_count/interval_ms/estimated_lpm/calibration_id 和 wet 不能进入 M2 标准合同|联合评审按 sensor_type 区分载荷；不得用人体字段伪装水流|
|CC02 P0|同一 value 中 present/moving/still 必填且仅 boolean；`unknown presence null rejected` 拒绝|V1.1 §1/2 与 M1 §5 允许 null/missing 表达未知；不能以 false 替代|联合评审 nullable/缺失策略与质量规则|
|CC03 P0|`FeatureWindow.schema.json#/properties/features` 十二键必填，数值和 water_contact 禁止 null；`unknown feature null rejected` 拒绝|V1.1 §3 明确无有效覆盖/过期时特征缺失，water_contact 为 true/false/null；mask=true 也无法解除类型限制|评审 nullable 特征与 mask 一致性，不能补0或false规避|
|CC04 P0|`AlignedWindow.schema.json#/properties/sensor_summary` 只允许 presence，禁止 flow/water；`flow summary rejected` 拒绝|M3 多源对齐要求三路摘要；M3 §5 写 coverage/source_refs，schema 无 coverage 且实际叫 source_observation_ids|明确三路摘要与覆盖度结构，裁决字段名后再代码化|
|CC05 P1|`ApiError.schema.json#/properties/details` 强制 expected_version/actual_version；`generic ApiError rejected` 对 NOT_FOUND+{} 拒绝|V1.1 §4 有400/401/404/409/503，普通错误不能诚实提供事件版本|评审按错误类型表达 details，不能填虚构版本|

INFERRED：CC01–04 是合同内部“合法业务数据无法表达”的结构冲突，仅在 Pydantic 增加更严格验证无法修复。应先联合评审再实现 DTO；本轮不改 schema。CC05 的错误格式需联合定义，不通过修改冻结文件绕过。

## Schema 外壳未覆盖的语义

VERIFIED：V1.1 §1 已明确枚举、时间、跨字段由 Pydantic validator 补充；因此以下是外壳能力缺口，不能全部误报为原设计承诺 Schema 单独校验。当前无 Pydantic 业务代码，仍需实现并验证。

|探针|实际结果 VERIFIED|约束依据|
|---|---|---|
|invalid lifecycle accepted|lifecycle=BANANA 通过；SafetyEvent.properties.lifecycle 只有 string|V1.1 §2 lifecycle 枚举|
|invalid source accepted|source=BANANA 通过；SensorObservation.properties.source 只有 string|V1.1 §2 hardware/simulation|
|untrusted DEVICE_SYNCED accepted|DEVICE_SYNCED+event_time=null 通过|V1.1 §2 可信时间条件|
|bad received_at accepted|received_at=yesterday 通过；仅 string，无时间格式约束|V1.1 §1 带时区 ISO8601|
|invalid coverage accepted|data_coverage_ratio=2 通过；仅 number|V1.1 §3 0..1|
|negative attempts accepted|attempts=-1 通过；仅 integer|CloudSyncRecord 同步重试计数语义，合理非负边界需实现确认|
|rule model score accepted|rules+model_score=0.99 通过|V1.1 §2 规则输出 score=null|

VERIFIED：SensorObservation.event_time、SituationAssessment.model_score、CloudSyncRecord.next_retry_at/last_error/receipts 允许所有 JSON 类型，见各 `.properties`；非负 seq/uptime、版本连续性、ID 非空/稳定性、TTL 和窗口先后均未由当前结构测试证明。对应规范 V1.1 §1–3、6，未来 I-002/I-004/I-008/I-010。对这些字段的具体 validator 形状属于 INFERRED 实施建议。

## 版本与字段映射

|差异|等级与证据|实施裁决依据|
|---|---|---|
|V0.5 source 包含 replay；V1.1 仅 hardware/simulation|VERIFIED；Architecture 提取第57–58段；V1.1 §2|优先 V1.1；回放模式另由实验元数据记录的方案 INFERRED，需评审，不能新增 source 枚举|
|V0.5 AlignedWindow start/end/finalized_at/config_version/samples/sensor_health/late_count 与 V1.1 schema 的 window_start/window_end/published_at/alignment_config_version/sensor_summary/quality_flags/source_observation_ids 不同|VERIFIED；Architecture 第19–21段；AlignedWindow.properties|旧设计不得直接用作当前 DTO，需适配；V1.1 内部缺口先处理 CC04|
|SafetySignal 旧 kind/valid/reason_codes 与新 signal_type/value/quality/observation_refs 不同|VERIFIED；Architecture 第28–30段；SafetySignal.properties|不自动改名公共合同；新实现优先新机器字段|
|M3 文档 source_refs 与 schema source_observation_ids；M4 文档 quality 不在 schema；M7 文档 status 与 schema sync_status|VERIFIED；模块各 §5 对照各 properties，additionalProperties=false|作为 I-002 联合澄清项，不在实现时擅自新增字段|
|V0.5 示例五对象中四个不符合新 Schema，SituationAssessment 通过|VERIFIED；contract_probes 中五条 V0.5 example 记录|旧 SensorObservation 缺 time_basis/moving/still；Event 缺 schema_version/created_at；Transition 缺版本/时间/证据；Sync 缺版本/重试/回执|
|V0.6 包名/合同 V1.1 与 DTO schema_version=1.0 并存|VERIFIED；九 schema 的 const=1.0，examples 全部使用该值|版本层级差异，不擅自把 DTO 值升级到1.1|

## 接口与数据库

|项目|审计结果|证据|
|---|---|---|
|REST 七条设计路由|VERIFIED 为文字设计；UNVERIFIED 为服务。无 OpenAPI、请求模型、分页封装、LiveSnapshot/SyncStatus/Experiment schema|V1.1 §4，源清单；原测试无 HTTP 请求|
|ACK 幂等和乐观锁|UNVERIFIED；不能证明同键同负载返回原结果、不同负载409、旧版本409或权限检查|V1.1 §4；CT08/14；没有路由/持久化代码|
|三表和唯一约束|VERIFIED 为 SQL 文字草图；UNVERIFIED 为数据库实现|V1.1 §6；没有 .sql/迁移/数据库文件|
|事务原子性|UNVERIFIED；没有 event+transition+outbox 原子提交/回滚证据|V1.1 §2/6，CT09|
|单 OPEN 与版本连续|UNVERIFIED；需唯一活动事件约束、事务内版本比较和transition 去重|V1.1 §2，CT06–08；当前 Event/Transition schema 仅独立结构|
|worker 仅改同步状态|UNVERIFIED；无进程重启、SENDING 恢复、重试和ACK证据|V1.1 §6，CT10/11|

INFERRED：数据库候选实现为事务内版本 CAS、event_id+event_version 唯一、transition_id 唯一、outbox transition_id 唯一、活动事件唯一约束，以及 ACK 操作结果持久化；具体迁移在 I-008 编写并审查。这些不是本轮已存在数据库结构。

## ADR 对应验收

|ADR|不可破坏的约束|当前验证范围|
|---|---|---|
|001|未知不等于否定，情境/安全/健康分开|VERIFIED 为规范；CC02/03 阻塞表达；CT01/05 未执行|
|002|独立真值、trial 分组，不承诺 ML 胜出|VERIFIED 为规范；CT12 未实现，无数据或模型|
|003|快速与滑窗合入唯一 M6，发布窗不静默重写|VERIFIED 为规范；CT03/04/06 未实现|
|004|本地 C1、云 C2、联系人 C3 分开|VERIFIED 为规范；真实 C1/C2/C3 均未实测|
|005|确认/物理恢复/生命周期/同步分离，业务+Outbox事务|VERIFIED 为规范；CT07–11/14 未实现|

依据 V1.1“已冻结原则”、行为矩阵。INFERRED：优先联合裁决 CC01–04，再扩展语义反例与行为测试；任何修订同时更新规范、schema、fixtures、测试，保留版本与审核记录。
