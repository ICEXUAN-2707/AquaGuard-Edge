# 水知安 V0.6｜合同与实施说明

**来源与优先级**：以《业务基线与冻结决议 V0.5》《PRD V0.5》《Architecture & Contracts V1》《模块Spec V0.5》和最近五项阻塞修订为基线；V0.6 在此上将语义细化到可测试级别。与早期 V0.4 冲突时，采用 ADR-001～005。**文档设计冻结 ≠ 代码、设备、模型与云端实测通过**。

## 已冻结原则
- ADR-001 用水情境、安全信号、数据健康分离；UNKNOWN 不能等同 false。
- ADR-002 模型真值由独立 trial 操作记录得到；按 trial_id 分组切分；AI 不保证胜过规则。
- ADR-003 快速安全信号路径和滑窗路径合入唯一 M6；默认 W30/S5/L2 仅为待验证配置。
- ADR-004 本地告警 C1、IoTDA C2、远程联系人 C3 独立验收；C3 不是 MVP 承诺。
- ADR-005 生命周期、确认、物理恢复、同步进度分别保存；业务变更与 Outbox 同一事务。

## 设计与验证状态
- **规范冻结**：字段含义、质量语义、事件幂等、状态约束、接口错误行为、契约测试。
- **待 Gate0**：源仓库许可/可运行/复用路径、MQTT Topic和固件、设备电平。
- **待 Gate1**：采样率、TTL、时钟精度、水位线参数及实际延迟。
- **待 Gate2**：情境分类性能、告警阈值和实验可区分性。
- **待 Gate3**：IoTDA SDK/属性模型、ACK层级和云端回执。

# Contracts V1.1｜实现级契约（设计冻结）

## 1. DTO 传递规则
接收顺序不等于事件顺序。所有对象需携带 schema_version（API错误除外）；所有时间为带时区 ISO8601，设备无法证明UTC/当地时钟准确时不得填可信 event_time；received_at由边缘接入写入。observed value=false仅表示合法否定观测，null或missing表示未知。DTO JSON Schema见 contracts/*.schema.json；Schema 是第一轮验证外壳，更严格的枚举/时间/跨字段条件由 Pydantic 自定义 validator 负责。

## 2. 枚举与交叉字段规则
| 类型 | 合法值或约束 |
|---|---|
| sensor_type | flow / water / presence |
| source | hardware / simulation |
| time_basis | DEVICE_SYNCED / EDGE_MAPPED / RECEIVED_FALLBACK |
| quality | valid / invalid / stale / duplicate / late / unknown（跨处理阶段标签，接入层原始quality只收valid/invalid/unknown） |
| data_quality | VALID / DEGRADED / UNAVAILABLE |
| situation | IDLE / ATTENDED_FLOW / POSSIBLE_UNATTENDED_FLOW / UNKNOWN |
| inference_mode | rules / ml / fallback |
| lifecycle | OPEN / RESOLVED / CLOSED |
| ack_status | UNACKNOWLEDGED / ACKNOWLEDGED |
| physical_status | ACTIVE / CLEARED / UNKNOWN |
| escalation_level | L0 / L1 / L2 / L3 |
| sync_status | PENDING / SENDING / RETRY_WAIT / ACCEPTED / FAILED |

- `time_basis=DEVICE_SYNCED` 必须存在可信 event_time；fallback 可为空；uptime_ms 仅在同一boot内可比较。
- `(device_id,boot_id,sensor_type,seq)` 幂等唯一；不同boot允许序号重置。
- `observation_id`、`window_id`、`assessment_id`、`event_id`、`transition_id` 全局稳定不随重试改变。
- `model_score=null`用于规则输出；ML分数须声明分数语义，未校准不得作为事故概率。
- 缺失布尔量不得写成 false；sensor_summary 的状态超过 TTL 时只能是 unknown。
- water/contact 安全信号可与 ATTENDED_FLOW 同时存在；M6不能由模型输出覆盖已校验的安全信号。
- 一个设备+一种事件类型+一次活动发作只能有一个 OPEN事件；二次通道更新同一事件。
- `EventTransition.event_version` 应严格连续递增，同一 transition_id 不重复入库。
- 事件变更写入 SafetyEvent、EventTransition 和 OutboxMessage 必须单个SQLite事务提交或全回滚。
- ACCEPTED 仅表示已验证的传输确认，不等于业务持久化与联系人收到。

## 3. 特征字典与计算语义
|字段|单位|定义|缺失条件|
|---|---|---|---|
|flow_mean_lpm|L/min|有效观测区间时间加权均值|无有效水流区间|
|flow_max_lpm|L/min|窗口有效水流观测最大值|无有效水流区间|
|flow_active_ratio|0..1|有效观测覆盖时长中的流水时长比率|有效时长为0|
|flow_streak_sec|s|有有效证据支持的当前连续流水时长，跨窗口维护|跨越未知间隔且不可推定|
|flow_change_count|次|有效观测支持的0↔有流状态切换数|缺少足够连续证据|
|water_contact|true/false/null|窗口末端最近且未过期水接触状态|过期、断线|
|water_contact_sec|s|窗口内有有效水接触的累计时长|缺少有效状态覆盖|
|presence_state|present/absent/unknown|窗口末端最近且未过期存在状态|过期、断线|
|presence_occupied_ratio|0..1|有效覆盖时段中的目标存在占比|无有效覆盖|
|presence_transition_count|次|有效状态区间存在/不存在切换次数|未满足可连续比较条件|
|absence_after_flow_sec|s|存在持续水流时可证据支持的连续未检测到目标时间|任一关键状态未知|
|data_coverage_ratio|0..1|按传感器权重聚合的关键观测覆盖度；权重须版本化|无有效观测|

> 注意：固定窗口默认W30s/S5s/L2s只是参数。采用 (t-W,t] 边界；事件时间水位线与处理时限联合关闭窗口，绝不因某一路永久沉默而卡死。发布后迟到数据入旁路日志，不静默回溯业务事件。

## 4. REST API V1（建议路径，可在 Gate0 后适配原仓库）
|方法 / URL|请求字段|响应|错误|
|---|---|---|---|
|GET /api/devices/{device_id}/live|设备ID|liveSnapshot:各信号+age+quality+cloud_status|404|
|GET /api/devices/{device_id}/assessment|设备ID|SituationAssessment+安全摘要|404/503|
|GET /api/events?device_id=&lifecycle=|过滤/分页|SafetyEvent[]、next_cursor|400|
|GET /api/events/{event_id}|事件ID|SafetyEvent+EventTransition[]|404|
|POST /api/events/{event_id}/ack|`expected_version`、`idempotency_key`、`ack_type`|更新的SafetyEvent+transition_id|400/401/404/409|
|GET /api/sync/status|设备ID可选|待同步数、错误数、上次确认层级|503|
|GET /api/experiments/{trial_id}|受控实验ID|trial元数据、指标和资产引用|401/404|

ACK幂等键与event_id组合唯一；同键同负载重放返回同一操作结果，不重复记录；同键不同负载返回409。expected_version不匹配返回409并返回可读新版本；不能让前端直接修改SQLite。实验/真实来源隔离，公开演示入口不能调用真实联系人通知。

## 5. MQTT Adapter
Topic沿原仓库已验证约定实施（预期格式 home/+/+/sensor、status），不得未验证即替换为生产合同。支持合包/分包输入并转换成每个传感器一条 SensorObservation；字段映射要保留观测时间来源，若合包时间不可精确到子测量，必须把time_basis降级。错误消息存到dead-letter隔离日志，不回写“正常”。

## 6. SQLite事务与Outbox
`safety_events(event_id PK, device_id,event_type,lifecycle,ack_status,physical_status,escalation_level,version,...)`；`event_transitions(transition_id PK,event_id,event_version UNIQUE per event,...)`；`outbox_messages(message_id PK,transition_id UNIQUE,destination,sync_status,attempts,next_retry_at,last_error,...)`。事件更新、transition插入、outbox插入原子执行。同步worker只变更outbox送达状态，不改写事件业务事实。待测：IoTDA回执与幂等保障范围。

## 7. 变更控制与跨团队协作
契约为三条工作线共同使用的唯一接口依据；任何字段改名、枚举修改、单位变化、窗口边界变化、事件版本规则调整，均需更新本文件、fixtures和契约测试，经A/B/C各一名评审确认；重大变更新增ADR，不由Codex自行决定。

## 8. 自动化测试执行顺序
在具备Python/pytest/jsonschema环境后：`python -m pytest tests -q`。初版包含Schema正反样例；后续逐Issue新增行为测试，不能以Schema验证替代跨字段/数据库/网络集成验收。
