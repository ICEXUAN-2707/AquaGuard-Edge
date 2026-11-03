# 水知安 IoTDA 最小集成计划

2026-11-03产品边界补充：IoTDA接入、本地用户三页、后续远程业务后台和联系人通知分别管理，职责、依赖及验收见[C业务、终端与云协同路线](../../spikes/docs/C/C_PRODUCT_ROADMAP.md)。本计划描述云适配，不替代用户应用交付；下文保留初版评估和当时未验证结论。

本轮只评估，不连接华为云、不创建计费资源。VERIFIED 指规范/官方资料可核实；INFERRED 为候选实现；UNVERIFIED 为真实连接、性能和回执能力。项目依据：V1.1 §2/6、ADR-004/005、M7 §3–9。

## 最小路线

INFERRED：ESP32仍只连接局域网Mosquitto，边缘Python M7作为一个云端逻辑设备，通过**设备侧 IoT Device Python SDK**向IoTDA上报；设备属性表达最新状态，设备消息承载稳定ID的事件变更。无需先部署云端计算/消息数据库/联系人服务。这是减少依赖的候选方案，逻辑设备到真实传感节点的映射须Gate3确认。

VERIFIED 为官方资料：设备侧SDK支持属性和消息上报；官方快速接入有产品模型、注册设备、配置接入地址与密钥、TLS证书和上报示例。[华为云设备侧 Python SDK 快速接入](https://support.huaweicloud.com/intl/zh-cn/sdkreference-iothub/iot_02_00942.html)。它验证SDK具备这些接口，不验证本项目已接入。

INFERRED：应用侧IoTDA OpenAPI/SDK只在需要云端查询、管理设备或额外回执验证时加入，不把服务端AK/SK当设备鉴权，不让M6直接等待云返回。消息与属性分别验收，不把设备事件、属性上报、普通消息三个不同协议混为同一接口。

## 集成边界与状态

INFERRED：业务事务一次写入SafetyEvent、EventTransition和Outbox；worker读取持久化消息→映射云载荷→发送→按已验证回调更新sync_status。Mock与Huawei实现使用相同内部适配接口；候选操作为connect/report_properties/report_transition/close，最终签名随固定SDK版本审核，不是新增公共DTO。

|同步状态|候选动作 INFERRED|必须证明的行为|
|---|---|---|
|PENDING|本地事务产生消息|本地事件成立不依赖云|
|SENDING|worker认领并保存attempt信息|进程崩溃后能超时重新认领，稳定message_id|
|RETRY_WAIT|临时网络/平台错误，退避+jitter|不阻塞采集和M6，next_retry_at持久化|
|ACCEPTED|只在验证过的传输确认后写入|记录SDK/协议确认层级和原始关联ID，不推导联系人已收到|
|FAILED|不可恢复错误或达到明确策略边界|本地可见错误，修正配置后可受控重试，不删除历史|

以上枚举 VERIFIED 来源 V1.1 §2；状态迁移具体策略尚 UNVERIFIED，需I-010实现。SDK内存缓存不替代Outbox，不能仅以connect成功或API调用返回即声明送达。

## 云端依赖清单

|依赖|目前等级|Gate3所需证据|
|---|---|---|
|账户、可用IoTDA实例、区域与额度|UNVERIFIED|账号管理员确认实例、访问范围、资源空间与配额，记录脱敏实例元数据|
|产品与物模型|UNVERIFIED|MQTT/JSON产品、service_id及属性名/类型与映射版本；三路未知值表示方案经评审|
|逻辑设备身份与密钥|UNVERIFIED|device_id/node_id映射；后端环境注入凭据，仓库只放无秘密示例|
|接入地址、DNS、TLS与CA|UNVERIFIED|控制台给出的实际主机和端口、CA验证、证书/时间错误日志；不得关闭TLS校验凑通过|
|SDK固定版本、许可、依赖锁|UNVERIFIED 为选型/安装|固定tag/SHA，LICENSE/NOTICE和依赖审查，Python/MQTT兼容测试|
|云侧消息跟踪与属性查看权限|UNVERIFIED|属性显示截图/导出、事件message_id与transition_id关联记录|
|可选业务接收端与数据转发|UNVERIFIED且非最小路径必需|只有要求业务持久化确认时再设计接收端幂等及业务回执|

VERIFIED：官方属性上报要求内容匹配产品模型。[设备属性上报说明](https://support.huaweicloud.com/usermanual-Iothub/iot_01_0326.html)。具体产品字段、区域、设备、权限和密钥资料在本工作区没有提供；本轮未访问用户华为账户。

## 云载荷映射提案

|数据|INFERRED 映射|约束/证据|
|---|---|---|
|实时状态|独立版本化云属性映射，选择流量、湿/存在状态、data_quality、age、边缘状态|未知使用云模型支持的明确状态或独立有效性标识，不自动null→false；V1.1 §1–3|
|事件变更|消息内容保留schema_version、message_id、transition_id、event_id、event_version以及必要状态与证据引用|稳定ID跨重试，事件事实仍以本地SQLite为权威；V1.1 §2/6|
|云回执|CloudSyncRecord的transport_receipt记录已验证确认；business_receipt仅收到真实业务接收回执时填写|禁止将MQTT确认等价于业务持久化或联系人收到；V1.1 §2|
|模拟实验|单独演示设备或资源空间、来源追踪、禁止真实联系人外发|DTO下游未自带source/trial需I-002评审元数据关联，不私改合同；CT15|

INFERRED：IoTDA设备ID和本地device_id分别配置映射；不得云端重命名反向污染本地DTO。云物模型应作为adapter配置版本控制，不直接替换冻结业务Schema。

## SDK 审查注意事项

VERIFIED：2026-10-26查阅[官方Python SDK仓库](https://github.com/huaweicloud/huaweicloud-iot-device-sdk-python)发现README声明与仓库许可证标识不一致，且准备环境与本次Python3.12环境不同；详细证据与版本在DEPENDENCY_RISKS。UNVERIFIED：本项目所需SDK具体SHA、Python3.12兼容性、回调对QoS/确认的真实语义、重复消息去重范围。I-010必须通过固定版本spike给出答案，不能宣称业务exactly-once。

## 验收步骤

以下全部 INFERRED 未执行，所列测试文件是待实现提案。

1. 无云环境跑Mock：`python -m pytest tests/cloud -q`，覆盖成功、超时、断网、重复回调、重启认领和永久鉴权失败。
2. 固定SDK环境及证书，连接测试设备；分别记录连接成功、单次属性和单次事件消息，再在云侧核对。命令提案`python -m pytest tests/integration/test_iotda.py -q`；无凭据时应明确未验收，不把skip算完成。
3. 断开WAN保留LAN，触发水浸和确认；本地页面/事务持续，Outbox积压；重启边缘后恢复WAN，核对稳定message_id和transition版本、重试次数及确认层级。
4. 注入鉴权/TLS错误与平台暂时错误，验证脱敏日志、退避、可见FAILED及恢复；云worker只能改投递事实。
5. 归档`iotda_receipt_log`、SDK SHA/锁、云映射版本、脱敏截图/跟踪记录和本地对应事件时间线。只有本地行为可演示记C1，真实IoTDA验收后记C2；本期不以C3联系人送达为完成条件。

UNVERIFIED：上述步骤当前均无硬件/云执行证据。缺账户/产品/设备时可以继续本地与Mock开发，但真实C2验收必须等待外部条件。依据ADR-004、M7 §7–9和行为CT10/11。
