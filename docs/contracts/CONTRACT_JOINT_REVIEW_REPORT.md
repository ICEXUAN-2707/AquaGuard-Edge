# 水知安 Contract 全面联合评审报告

> 本报告是 2026-10-26 的问题基线。2026-10-27 技术修订已形成 V1.2 候选、`schema_version=1.1` Schema/DTO 和分层验收门槛；问题的实施及会签状态见 `CONTRACT_ACCEPTANCE.md`。下文“当前”等用词均指预审时点。

日期：2026-10-26
评审状态：**技术预审完成；A/B/C 联合裁决未完成；正式契约未冻结**
范围：当前工作树中的 Contracts V1.1 深化规范、9 份 JSON Schema、`examples.json`、M1–M8 模块规格、行为测试矩阵、合规探针，以及当前服务实现。`reference/` 本次未修改。

## 1. 结论与开发闸门

**结论：当前 contract 不具备直接驱动三条工作线并行开发的条件。** CC01–CC04 是合法业务数据无法通过机器契约的结构冲突，CC05 阻断通用 API 错误封装。另有来源传播、事件分组和跨对象样例等设计缺口，需要 A/B/C 明确裁决。现有通过的测试只证明单对象结构样例和启动基线；不代表端到端或业务合同通过。

建议将 I-002 的退出条件设为：A/B/C 各一名评审逐项签署决议；修订主规范、受影响 Schema、样例、负例和行为测试；确定版本及兼容策略；运行全部契约测试并保存结果。在此之前，I-003–I-009 只能依赖明确标注为草案的隔离 fixture，不得将草案 DTO 当作正式接口。

## 2. 评审方法和证据边界

1. 对照 [深化规范](../../reference/reference_02/00_Contracts_V1.1_深化规范.md)、[模块规格](../../reference/reference_02/modules)、[Schema](../../reference/reference_02/contracts)、[样例](../../reference/reference_02/contracts/examples.json)、[行为矩阵](../../reference/reference_02/tests/BEHAVIOR_TEST_MATRIX.md) 与 [现有合规探针](../../audit/evidence/contract_probes.json)。
2. 在当前工作树运行 `.\.venv\Scripts\python.exe -m pytest ../../reference/reference_02/tests -q -p no:cacheprovider`，结果 **19 passed**；运行 `.\.venv-app\Scripts\python.exe -m pytest tests/smoke/test_startup.py -q -p no:cacheprovider`，结果 **3 passed**。
3. 当前 [服务入口](../../edge/app.py) 仅有 `/health`，没有正式业务路由、Pydantic 业务 DTO、事件库或 Outbox 实现。因此本报告将“规范/Schema 冲突”“规范尚待裁决”“实现尚未验证”分开表述。未开展硬件、MQTT Broker、IoTDA 或浏览器端到端验收。
4. `CONTRACT_COMPLIANCE.md` 中 CC01–CC05 已有具体探针。本报告复核这些证据，并新增跨模块和联合样例问题；不把已有探针重复计作新测试。

## 3. 阻塞发现

|ID / 等级|证据和问题|影响|联合裁决与验收条件|
|---|---|---|---|
|CC01 / P0 已证实|[M1 §5](../../reference/reference_02/modules/M1_感知采集.md) 定义 flow 的脉冲/流量及 water 的 `wet`；[SensorObservation.value](../../reference/reference_02/contracts/SensorObservation.schema.json) 只允许且强制 `present/moving/still`。现有探针拒绝合法 flow、water 载荷。|A 无法交付标准观测，B/C 无法从正式合同获得三源输入。|按 `sensor_type` 裁决判别载荷、心跳形式、数值单位及约束；三类正例和错配负例均需通过。|
|CC02 / P0 已证实|规范 §1–2 明确 `null`/缺失表示未知；[SensorObservation.value](../../reference/reference_02/contracts/SensorObservation.schema.json) 的三个布尔值必填且只能是 boolean，未知 presence 探针被拒。|可能被迫把失联/未知伪装成 `false`，违反 ADR-001。|裁决 `null`、字段缺失、心跳、`quality` 的组合语义；验证未知不被映射成正常。|
|CC03 / P0 已证实|规范 §3 的十二特征有明确缺失条件；[FeatureWindow.features](../../reference/reference_02/contracts/FeatureWindow.schema.json) 十二键全必填，数值和 `water_contact` 不允许 `null`；未知 water 探针被拒。|B 无法诚实表达无覆盖或 TTL 过期，C 可能用假零值推断。|裁决逐字段可空性、`missing_mask` 一致性、无覆盖时比率/计数语义；三路全缺失正例及“缺失却写 false/0”反例。|
|CC04 / P0 已证实|[M3 §5](../../reference/reference_02/modules/M3_时序对齐与质量治理.md) 要三源 `sensor_summary`，并称 `coverage/source_refs`；[AlignedWindow.sensor_summary](../../reference/reference_02/contracts/AlignedWindow.schema.json) 只允许 presence，实际引用字段为 `source_observation_ids`。flow 摘要探针被拒。|B 无法发布三源窗口；文档字段名与机器字段不一致。|裁决三源状态、年龄、覆盖率、TTL、沉默发布及字段别名；验证沉默传感器为 `unknown` 且窗口仍发布。|
|CC05 / P1 已证实|[ApiError.details](../../reference/reference_02/contracts/ApiError.schema.json) 对所有错误强制 `expected_version/actual_version`；规范 §4 同时定义 400/401/404/409/503。`NOT_FOUND` 加空对象探针被拒。|通用错误若遵约只能伪造版本或无法响应。|按错误码裁决 details 形状；409 返回客户端期望版本与当前版本，其他错误不暴露内部堆栈。|

## 4. 新增跨模块发现及设计待决

|ID / 等级|证据和判断|风险与建议验收|
|---|---|---|
|CC06 / P0 设计缺口|规范 §2 仅在 SensorObservation 定义 `source=hardware/simulation`；[SafetySignal](../../reference/reference_02/contracts/SafetySignal.schema.json)、[SafetyEvent](../../reference/reference_02/contracts/SafetyEvent.schema.json)、[CloudSyncRecord](../../reference/reference_02/contracts/CloudSyncRecord.schema.json) 没有来源字段；M6/M7/M8 §6 均要求模拟信号不能触发真实联系人通知。现有契约未说明通过引用链、存储列或受控 trial 上下文如何保持可信来源。|A/B/C 需共同确定端到端来源证明和外发授权点。验收：模拟源经过快速路径、滑窗路径、重启及 Outbox 重试后，真实联系人通道始终被阻断；硬件源按权限放行。不能仅依赖前端标识。|
|CC07 / P1 设计缺口|规范 §2 写“设备+事件类型+一次活动发作”仅一个 OPEN；[M6 §9](../../reference/reference_02/modules/M6_情境决策与事件状态机.md) 又要求避免不同水浸点被吞并。[SafetyEvent](../../reference/reference_02/contracts/SafetyEvent.schema.json) 只有 `device_id/event_type`，没有点位或 episode/group 标识。|C 与 A 应裁决事件分组键和复发边界，并映射数据库唯一约束。验收：同点快慢路径合并、不同点同时水浸不误合并、恢复后复发按明确规则新建或续用。|
|CC08 / P1 样例缺陷|[examples.json](../../reference/reference_02/contracts/examples.json) 唯一 `SensorObservation` 是 presence `obs-1`，但 `WATER_CONTACT` SafetySignal 的 `observation_refs` 指向 `obs-1`；同一组样例的 FeatureWindow 还有 flow/water 特征，却没有对应源观测。若作为联合黄金场景，证据链不成立。当前测试逐对象验证，发现不了此类问题。|提供一套相互引用的完整三源正例和至少一套缺源负例；测试引用存在、类型吻合、时间和设备一致。若样例本意互不关联，应拆成独立文件并避免复用同一 ID。|
|CC09 / P1 接口契约不完整|规范 §4 列七条 REST 路由，但 `LiveSnapshot`、`SyncStatus`、实验响应、ACK 请求/响应、分页封装无机器 Schema；[M8](../../reference/reference_02/modules/M8_用户产品与实验平台.md) 直接消费这些对象。当前 [服务入口](../../edge/app.py) 只有健康检查。|C 应给每条路由定义请求、响应、错误码、认证要求、分页稳定顺序和示例；生成并测试 OpenAPI。当前服务实现状态应标为未实现，不作为合同不一致。|
|CC10 / P1 验证层断档|规范 §1 明确 JSON Schema 只作外壳，跨字段由 Pydantic validator 补充；但当前无业务 DTO。已记录探针显示无时区时间、非法枚举、2.0 覆盖率、负重试次数、规则输出 0.99 分等可通过 Schema。|A/B/C 裁决 validator 归属并建立同一模型包。验收包含枚举、时间、数值边界、`time_basis/event_time`、`rules/model_score`、版本连续及引用约束的正反例。测试应证明实际 API/队列入口调用了验证，而不只直接测模型。|
|CC11 / P1 状态语义待决|[SafetySignal](../../reference/reference_02/contracts/SafetySignal.schema.json) 的 `value` 是 boolean、`quality` 是任意 string；M6 要把确认、物理恢复和生命周期分开。没有正式规则界定 `false` 是有效清除证据、无异常，还是可用于关闭事件；也未给出过期信号处理方式。|B/C 裁决仅在 `quality=VALID` 且经消抖/TTL 的条件下如何生成 ACTIVE/CLEARED/UNKNOWN；验收 ACK 后仍 wet、无新数据、有效 dry 三种独立路径。|
|CC12 / P2 扩展冲突|规范 §6 的 Outbox 草图对 `transition_id` 唯一，同时 [CloudSyncRecord](../../reference/reference_02/contracts/CloudSyncRecord.schema.json) 有 `destination`；ADR-004 将 C2/C3 分开验收，C3 非 MVP。若未来同一 transition 同时投往多个目的地，唯一键不允许。|A/C 应明确当前仅单目的地，或将候选唯一键改为 `(transition_id,destination)` 并定义每目的地独立回执/重试；在 C3 前完成裁决。|

## 5. 九份 DTO 逐项评估

|DTO|当前结构评价|开发前必须锁定的语义|
|---|---|---|
|SensorObservation|**阻塞**：三类载荷和未知布尔无法表达。|类型判别、心跳、时间可信性、幂等键、原始质量/来源。|
|AlignedWindow|**阻塞**：仅 presence 摘要。|三源状态、TTL、覆盖率、窗口边界、发布后迟到处理。|
|FeatureWindow|**阻塞**：缺失特征不可表示。|十二字段空值、mask、有效覆盖分母、状态恢复。|
|SituationAssessment|结构样例通过，语义层未实现。|枚举、rules 分数为空、ML 分数含义、降级/拒判。|
|SafetySignal|结构样例通过，证据链与状态规则未闭合。|可信观测引用、质量、`true/false` 与恢复语义。|
|SafetyEvent|结构样例通过，分组及状态机规则未闭合。|episode/点位、唯一 OPEN、版本、生命周期/确认/物理状态正交。|
|EventTransition|结构样例通过，跨对象规则未验证。|连续版本、actor 身份、去重、evidence_refs 可追溯。|
|CloudSyncRecord|结构样例通过，回执类型和目的地规则未定。|状态迁移、重试次数、回执层级、重启恢复、目的地基数。|
|ApiError|**阻塞通用错误**：details 仅适用于版本冲突。|错误码判别、HTTP 映射、安全可展示 details、request_id。|

## 6. 联合裁决表（A/B/C 各一名评审逐项记录）

|裁决包|主责/参与|必须形成的书面决定|退出证据|
|---|---|---|---|
|D1 三源观测与未知语义（CC01–02）|A 主责，B/C 复核|判别载荷、心跳、null/缺失/invalid、原始质量、单位|三源正例、未知正例、错配及伪 false 负例|
|D2 窗口与特征（CC03–04）|B 主责，A/C 复核|三源摘要、TTL、年龄基准、十二特征缺失及 mask、coverage|沉默发布、全缺失、边界、乱序黄金结果|
|D3 事件与来源（CC06–07、CC11）|C 主责，A/B 复核|来源贯穿与通知授权、点位/episode、物理清除和版本状态机|双路径合并、双点并发、模拟源禁外发、ACK 后仍 wet|
|D4 API 与 Outbox（CC05、CC09、CC12）|C/A 联合，B 复核|错误码及 details、七路由机器合同、目的地与回执基数|409 重放、401/404/503、分页、双目的地或单目的地限制|
|D5 版本与验证（CC08、CC10）|A/B/C 联合|正式版本号、兼容窗口、统一 DTO 包、联合 fixtures、验证责任|Schema/DTO/API/数据库各层正反例与完整追踪矩阵|

每项记录：决定、备选方案为何未选、影响的字段和消费者、兼容性、测试用例、A/B/C 评审人及日期。此表是评审材料，**当前没有三方签署**。

## 7. 先规划后开发：建议执行顺序

1. **冻结评审输入**：给主规范、9 份 Schema、样例和测试记录文件哈希与工作树提交号；确定本次评审的是当前工作树版本。`reference/` 的变更由联合评审批准后统一提交。
2. **完成 D1–D5 决议**：优先解决 CC01–04 与 CC06；逐条给出可运行的正反样例和兼容策略。已有 [CONTRACT_REVIEW_DRAFT.md](CONTRACT_REVIEW_DRAFT.md) 可作为 CC01–05 的起点，但其建议尚不是正式合同。
3. **一次性修订正式合同**：同步主规范、受影响 Schema、模块字段别名、联合样例、测试矩阵及版本说明。改变既有 `schema_version=1.0` 的字段约束时，需明确旧数据读取、迁移或拒绝策略；不能只改 Schema。
4. **建立分层测试**：结构测试、DTO 交叉字段测试、跨对象引用测试、API 请求响应测试、SQLite 状态机/事务测试、端到端 CT01–CT16。每一层标明执行命令与通过证据；Mock 结果不替代硬件/IoTDA Gate。
5. **再进入业务实现**：按 I-003→I-004→I-005→I-007、I-006/I-008→I-009 的依赖推进。I-010 云链路和 C3 的验收独立于 C1 本地告警。

## 8. 验收门槛与残留风险

- **Contract Gate**：无未裁决 P0；A/B/C 签署；九 DTO 与 API 的字段、枚举、单位、缺失和版本语义可机器验证；现有 19 项保持通过，新增正反例覆盖 CC01–CC12 中已选方案。
- **Behavior Gate**：[CT01–CT16](../../reference/reference_02/tests/BEHAVIOR_TEST_MATRIX.md) 对应真实实现测试和证据齐备，特别是未知不等于否定、快速/周期只建一事件、ACK 幂等、事务回滚和模拟源禁外发。
- **Integration Gate**：MQTT、设备时钟、SQLite 重启恢复和 IoTDA 回执分别验收；C1/C2/C3 分别报告状态。当前没有这些通过证据。
- **当前边界**：上述 19+3 测试通过，只说明现有单对象结构样例和服务启动正常。它们不能解除 CC01–CC05，也不能证明数据源、事件、通知或云端合同成立。
