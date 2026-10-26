# 水知安能力差距分析

判定口径沿用 REPO_AUDIT 的 VERIFIED / INFERRED / UNVERIFIED。审计对象为当前资料仓库，设计存在不计为模块已实现。统一资产证据：`audit/evidence/reference_manifest.json`；运行证据：`audit/evidence/pytest.log`。

## M1 至 M8

|模块|已实现|部分实现|未实现|需验证|结论与证据|
|---|---|---|---|---|---|
|M1 采集|无业务实现|设计已写明三传感器输入|固件、标定、自检、消抖、boot/seq、校准资产|供电电平、低流量、静止存在、实际采样率与时钟|VERIFIED 为实现缺失；UNVERIFIED 为硬件；`modules/M1_感知采集.md` §3、5–9，manifest|
|M2 标准化|无 Adapter|SensorObservation presence 示例与结构测试|MQTT 订阅、三类载荷、坏包隔离、去重、重连|上游 Topic/合包格式及时间精度|VERIFIED；`M2_消息通信与标准化.md` §3、5–9；Schema `.properties.value`；需验证项 UNVERIFIED|
|M3 对齐|无算法|AlignedWindow 单例及结构测试|事件时间缓冲、水位线、超时、TTL、晚到旁路|W/S/L、采样率差异、时钟降级、缓存上限|VERIFIED；`M3_时序对齐与质量治理.md` §3、5–9；Schema `sensor_summary`；参数 UNVERIFIED|
|M4 特征|无计算器|十二特征字典与完整数值示例|时间加权、缺失传播、跨窗持续状态、检查点恢复|在线/离线一致与窗口边界|VERIFIED；V1.1 §3；`M4_特征融合与状态记忆.md` §3、7–9；行为 UNVERIFIED|
|M5 情境|无规则和模型|SituationAssessment 示例与结构测试|C0–C3 推理、fallback、独立标注、trial 分组、模型卡|区分能力、误报/召回、ML 实际收益|VERIFIED；`M5_轻量AI情境识别.md` §3、5–9；性能 UNVERIFIED|
|M6 决策|无状态机|SafetySignal/Event/Transition 示例与结构测试|快速路径、唯一 OPEN、版本、ACK 幂等、恢复/关闭与升级|重复路径竞争、震荡、用户确认后仍湿|VERIFIED；`M6_情境决策与事件状态机.md` §3、5–9；行为 UNVERIFIED|
|M7 存储与云|无存储或连接|CloudSyncRecord 示例与事务设计|三表、迁移、事务、worker、重启恢复、SDK 适配|账号、实例、产品模型、密钥、TLS、回执|VERIFIED；V1.1 §6；`M7_事件持久化与华为云协同.md` §3、5–9；云 UNVERIFIED|
|M8 产品与实验|无页面/API|三页面流程和 REST 文字设计|路由、授权、实时状态、ACK、回放/导出、浏览器测试|401/404/409/503、仿真隔离、过期状态展示|VERIFIED；V1.1 §4；`M8_用户产品与实验平台.md` §3、5–9；行为 UNVERIFIED|

INFERRED：不能用模块完成百分比衡量这些文档资产。业务实现覆盖目前为零，契约支撑仅部分具备且存在阻塞。依据上表和 CONTRACT_COMPLIANCE 的实测反例。

## Gate 与最小纵向交付

|关卡|当前等级|缺口与退出证据|后续 Issue|
|---|---|---|---|
|G0 源仓库/路线/通信|UNVERIFIED；D0 资料审计已完成|确定上游 URL+commit+许可或记录采用自建；固件路线二选一；模拟 MQTT 日志|I-001、I-002、I-003、I-013|
|G1 时间与特征|UNVERIFIED|乱序、单路沉默、TTL、边界、重启、固定输入黄金特征与 CT16|I-004、I-005|
|G2 决策与本地演示|UNVERIFIED|有人流水+湿同时成立；双路径单事件；确认不恢复；三页本地演示|I-006、I-007、I-008、I-009|
|G3 持久化与云|UNVERIFIED|SQLite 故障回滚、断 WAN/重启补传、SDK 属性+消息与云侧回执|I-008、I-010、I-012|

依据：`audit/evidence/04_Spec_模块工程规格与Issue_V0.5.txt` 第68–83段。INFERRED：G0 可拆成不依赖实物的模拟准入与硬件准入；模拟准入不等于 G0 全通过。先交付模拟闭环，再替换硬件与云，避免硬件到货和账户阻塞所有开发。

## 实验资产缺口

|试验|缺失资产和方法|等级与依据|
|---|---|---|
|E1 单传感器|已知体积多次重复、干湿/静止/离开操作记录、设备批次、校准系数与误差、触发恢复延迟|VERIFIED 缺资产；业务基线提取第135–137段；方法 INFERRED|
|E2 时序治理|保留 event_time/received_at、乱序/丢包/单路沉默注入、到达序基线与事件时间结果对照|VERIFIED 缺资产；业务基线第138–140段，CT03/04/13|
|E3 规则和 ML|Raw/Features/Labels、独立 trial 操作记录、split_manifest、C0–C3 指标、拒判比例|VERIFIED 缺资产；业务基线第130–143段，CT12/16；无性能结果|
|E4 可靠性|事务故障注入、WAN 中断保 LAN、进程重启、重复 transition 的日志与回执对应表|VERIFIED 缺资产；业务基线第144–146段，CT09–11|
|E5 校园迁移|配置差异、复用模块清单、修改量和耗时|VERIFIED 缺资产；业务基线第147–149段；INFERRED 排在 P2，不能抢占本地闭环|

INFERRED：每个 trial 固定 scenario_id、trial_id、来源、设备/配置/特征版本、操作时间线与数据引用；分组后再生成窗口数据集，禁止相邻重叠窗跨集合。延迟报告区分采集→边缘接收、接收→M6、M6→页面/云确认，并报告样本数和分位数，门槛经 Gate 实测后确定。依据 ADR-002/003、PRD 提取第110–117段；这是实验计划，不是新增已冻结 DTO。

## 场景覆盖

UNVERIFIED：S01–S12 当前均无端到端可执行验收。定义见业务基线提取第21–60段。INFERRED：固定仿真至少覆盖空闲、正常/静止有人流水、离开后流水、自动进水拒判、单独湿、有人且湿、流水且湿、presence 过期、flow 失联、WAN 中断及恢复；每次保留输入、版本、输出与状态时间线。对应 I-002/I-012，不把自动进水直接标成事故真值。
