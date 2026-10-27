# Contracts V1.2 修订候选｜联合会签前

状态：**候选规范，2026-10-27 完成技术修订，A/B/C 尚未会签**。本文件是 `00_Contracts_V1.1_深化规范.md` 的增量修订；两者无冲突处沿用 V1.1。当前 `contracts/*.schema.json`、`examples.json`、`scenario_s01.json` 和 `edge/contracts/` 按本候选版编写。V1.1 DOCX 和历史审计证据仍反映旧版，不可据此声称候选版已获批准。

## 1. 版本与兼容边界

- 文档版本 V1.2 与 DTO `schema_version="1.1"` 是不同编号。8 个业务 DTO 同步升至 `1.1`；`ApiError` 不含 `schema_version`。旧 `1.0` 载荷仅用于历史回放，不得被新消费者静默当作 `1.1` 处理。
- 当前仓库未部署业务生产消费者；仍需在 I-002 会签时确认是否保留 `1.0` 读取适配及保留期。任何兼容层必须显式标记输入版本，并用迁移 fixture 验证；不能替换原始历史记录。
- JSON Schema 验证结构与可表达范围，`edge/contracts` 的 Pydantic 模型验证单对象交叉字段；引用链、唯一性、状态迁移和事务由后续集成测试验证。设备、网络和云端 Gate 单独验收。

## 2. D1｜三源观测与未知值（CC01–02）

`SensorObservation.value` 由 `sensor_type` 判别：

|sensor_type|value 必填字段|语义|
|---|---|---|
|flow|`pulse_count:int>=0`、`interval_ms:int>0`、`estimated_lpm:number>=0`、`calibration_id:非空字符串`|一个有效统计间隔。单位依次为脉冲、ms、L/min。|
|water|`wet:boolean|null`|`null` 表示设备明确报告未知；`false` 只表示有效干态。|
|presence|`present/moving/still:boolean|null`|`null` 表示对应子测量未知；`moving=true` 或 `still=true` 与 `present=false` 不得并存，`moving` 与 `still` 不得同时为 true。|

三种载荷不能互换，完整标准 DTO 不允许省略某个 `value` 子字段。无法产出观测值的状态心跳走 MQTT `status` 通道，不伪造成 flow 数值 0。`quality=valid` 时 water.wet 和 presence.present 必须已知；原始接入只接受 `valid/invalid/unknown`，`stale/duplicate/late` 是后处理标签。未知不能补成 `false`。`received_at`、非空 `event_time` 必须是带时区 ISO8601；`RECEIVED_FALLBACK` 对应 `event_time=null`，另两种时间基准必须有非空时间。可信设备时钟还需在接入层验证同步证据，字段存在本身不足以证明可信。

## 3. D2｜窗口、缺失和特征（CC03–04）

- `AlignedWindow.sensor_summary` 强制包含 flow/water/presence。各项为 `{state,age_sec,coverage_ratio}`；状态分别为 `active/inactive/unknown`、`wet/dry/unknown`、`present/absent/unknown`。`age_sec` 按 `window_end` 到最后一条仍有效观测计算；终态 `unknown` 时为 `null`。覆盖率在 0..1，按该源在窗口中有效覆盖时长计算；即使终态未知，窗口前段有效覆盖仍可非零。心跳不计入有效覆盖。过 TTL 不输出 dry/absent/inactive。
- 窗口采用 `(t-W,t]`，满足 `window_start < window_end <= published_at`。沉默源不阻塞其他源的窗口发布；迟到观测进入旁路审计，不静默修改已发布窗口。机器字段统一为 `source_observation_ids`；M3 文档旧称 `source_refs` 仅是历史别名，不进入 DTO。
- `FeatureWindow` 保留十二特征键。无法计算的数值与 `water_contact` 写 `null`；`presence_state=unknown`。`missing_mask` 表示该源在本窗口无可用证据：对应源特征必须为 `null`，presence 的状态必须为 unknown。flow 或 presence 缺失时 `absence_after_flow_sec=null`。三源全缺失时 `data_coverage_ratio=0`；其余覆盖度权重需随 `feature_version` 固定。没有连续证据时转换计数为 `null`，有明确连续证据且无转换才是 0。
- `FeatureWindow.origin` 由窗口来源导出；检查点必须保留 `feature_version` 和其输入窗口身份。S01 样例中的特征数值仅展示字段，不是计算黄金值；I-005 应另给逐采样黄金结果。

## 4. D3｜来源、事件与清除（CC06–07、CC11）

- 原始 `source` 仅有 hardware/simulation。下游 `origin` 有 hardware/simulation/mixed/unknown：全为硬件且引用完整才是 hardware；全为模拟才是 simulation；两种同时出现是 mixed；引用缺失或无法核验是 unknown。来源由受信后端按不可变观测引用推导，客户端传入值不能单独授权外发。AlignedWindow→FeatureWindow→SituationAssessment/SafetySignal→SafetyEvent→EventTransition→CloudSyncRecord 必须保留或可核验来源。
- 真实联系人外发只允许经过后端授权的 hardware 事件；simulation、mixed、unknown 均默认拒绝。C3 仍非 MVP 承诺；测试环境 IoTDA 与真实目的地必须分离。重试和进程重启不得丢失来源或绕开授权。
- 当前版本限定**每个 device_id 对应一个受控水浸点/供水支路**。唯一活动事件键为 `(device_id,event_type)`；同点快慢路径合并到同一 OPEN 事件。多水浸点必须分配不同 device_id；未来若一设备多点，先增加点位合同与数据库唯一键，不得靠 event_type 文本拼接偷偷扩展。
- `SafetySignal.value=true` 是异常存在候选；`false` 仅在 `quality=VALID`、未过 TTL 且经过必要消抖时，作为物理清除候选。INVALID/UNKNOWN/STALE 或信号缺席只能导向物理 UNKNOWN，不能清除。ACK 只更新确认状态，不代表清除、关闭或同步成功。关闭/复发策略在 I-008 状态机表中固化并测试。

## 5. D4｜API 错误、请求响应与 Outbox（CC05、CC09、CC12）

`ApiError.code` 仅允许 `BAD_REQUEST/UNAUTHORIZED/NOT_FOUND/SERVICE_UNAVAILABLE/VERSION_CONFLICT/IDEMPOTENCY_CONFLICT`。`VERSION_CONFLICT.details` 必含 `expected_version`（请求值）和 `actual_version`（当前事件值）；其余错误的 details 为 `{}`，不得返回内部堆栈、密钥或 SQL。所有错误有非空 `request_id`。

七条路由的候选机器模型位于 `edge/contracts/api_models.py`。业务服务尚未实现这些路由；I-009 必须让实际 OpenAPI、请求/响应序列化和下表一致。

|方法与路径|请求/查询|200 响应模型|错误与特别约束|
|---|---|---|---|
|GET `/api/devices/{device_id}/live`|非空 device_id|`LiveSnapshot`|404；三源 age、coverage、origin 与 cloud_status 分离。|
|GET `/api/devices/{device_id}/assessment`|非空 device_id|`AssessmentResponse`|404/503；assessment 与安全信号分别呈现。|
|GET `/api/events`|`device_id?`、`lifecycle?`、`cursor?`、`limit=1..100`|`EventListResponse`|400；按 `(created_at,event_id)` 降序，opaque cursor 不因同时间戳丢项。|
|GET `/api/events/{event_id}`|非空 event_id|`EventDetailResponse`|404；完整连续的 transition 版本链。|
|POST `/api/events/{event_id}/ack`|`AckRequest`：`schema_version=1.1`、`expected_version>=1`、非空 `idempotency_key`、`ack_type=ACKNOWLEDGE`|`AckResponse`|400/401/404/409；同 `(event_id,key,payload)` 重放返回同一结果，键相同但载荷不同为 IDEMPOTENCY_CONFLICT；过期版本为 VERSION_CONFLICT。|
|GET `/api/sync/status`|`device_id?`|`SyncStatus`|503；TRANSPORT/BUSINESS/NONE 分层，不把传输确认宣称业务送达。|
|GET `/api/experiments/{trial_id}`|受控 trial_id|`ExperimentResult`|401/404；仅受控实验源，公开演示入口不能执行回放或真实通知。|

ACK 的幂等结果需持久化到与事件关联的操作记录；同键同载荷先返回原操作结果，即使客户端携带旧版本，也不得新增 transition。权限校验发生在变更前。`event.version` 与 transition 的 `event_version` 从 1 连续递增，事件、transition、Outbox 在一个 SQLite 事务提交或全部回滚。

当前 Outbox 唯一目的地为 `huawei_iotda`，一条 transition 最多一条该目的地消息；SQL `transition_id UNIQUE` 与此相符。增加 C3 或第二目的地前必须迁移为 `(transition_id,destination)` 唯一并分开回执和重试。`ACCEPTED` 必须有可核验 transport_receipt；`business_receipt` 独立，字段存在不代表用户/联系人收到。具体 IoTDA 回执映射仍待 Gate3 实测。

## 6. D5｜验收和会签

1. **静态契约门槛**：9 份 Schema、单对象样例、三源联合样例、结构正反测试、DTO 语义正反测试均通过；旧 `1.0` 必须被新模型拒绝；命令见仓库根目录 `CONTRACT_ACCEPTANCE.md`。
2. **模块门槛**：I-003–I-009 的入口必须调用正式 DTO 验证；CT01–CT16 每条有运行的行为/集成测试、输入、断言和输出证据。空测试、skip 或只测 Mock 不算对应真实 Gate 通过。
3. **事务与通知门槛**：并发 ACK、幂等重放、事务故障注入、重启恢复、模拟来源禁外发、断 WAN 本地告警均有可重现测试。IoTDA 和实物硬件单独 Gate，不能被结构测试替代。
4. **会签记录**：A（采集/通信/云）____，B（对齐/特征/推断）____，C（事件/产品）____；日期____；接受的 Schema/样例/测试哈希____；保留意见与负责人____。三方签署前本文件保持“候选”。
