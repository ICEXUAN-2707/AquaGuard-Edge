# PR #12 / #13 复审与集成边界

复审日期：2026-11-14。远端同步后基线 main=5f5bc94，PR #12=abe27a7，PR #13 原基线=7fa4005；本文件随本轮修复提交。没有合并 main，没有启动长时实验或真实云连接。

## PR #13：离线交付候选

本轮补充拒绝谓词被缩窄的 unique_open 索引，避免仅凭名称及部分 SQL 匹配放行业务库；装配失败显式关闭新建传输。缺失文件、空文件、空 SQLite、Journal、无关库、缺列/策略/索引、错误策略和缩窄索引均在 Worker 构造前拒绝。负向测试比较完整文件字节与 sqlite_master，确认拒绝后不变。

短时回归 47/47 通过（0 失败/错误/跳过），JUnit：docs/audit/offline-worker-20261114/offline-review-20261114.xml。覆盖离线装配、旧 DeliveryService/Mock 兼容、Outbox 持久重试、租约过期、完成时钟倒退、只读库存和采集工具。此前 B 交付兼容验证为 67 文件检查/38 测试；本轮未改动 B 冻结源。本轮未发现其他阻塞这批离线代码交付的问题，但不构成联网或长期可靠性验收。

可交付：simulation_test 专用、已初始化兼容策略业务库的显式装配，真实 IoTDA 消息映射配无网络失败传输；只读库存与有界采集器。调用者仍须保证数据库为专用副本且不被并发替换。等价但非标准格式的索引 SQL 也可能保守拒绝；不自动迁移旧库。

## PR #12：按依赖拆分，不整体批准

以下是集成范围整理，独立项仍须在 main 基线上拆出提交并运行对应短测后才能合并；不能将历史分支测试结果当成拆分后验证。

|范围/文件|建议|交付条件与限制|
|---|---|---|
|scripts/analyze_runtime_observation.py、audit_runtime_storage.py；tests/delivery/test_runtime_analysis.py、test_runtime_storage_audit.py|优先拆出只读分析工具|核对输入兼容和只读行为，运行对应短测；库存没有引用不等于允许删除|
|scripts/supervise_endurance.py、start_endurance_task.ps1；tests/delivery/test_endurance_supervisor.py|作为独立调度工具批次评审|保留 Job Object、退出收据和自身进程归属边界；短测后交付代码，不注册/启动任务|
|scripts/runtime_endurance.py、benchmark_journal.py；tests/delivery/test_runtime_endurance.py|保留为显式执行工具候选|核对 CLI、日志和运行时接口依赖后再拆分；准备完成不代表允许执行一小时或压力实验|
|spikes/C-business/{api,context_events,online,projections,run,runtime_diagnostics,store,water}.py；test_pause_recovery.py、test_runtime_diagnostics.py|耦合运行时批次，暂不直接挑文件合并|online.py 已导入 checkpoint.verification_scope，必须连同依赖评审，或先拆掉缓存优化相关改动再验证诊断部分|
|spikes/SP-03-features/src/checkpoint.py 及 tests/test_checkpoint.py|当前集成阻塞项|它在 scripts/b_frozen_sources.py 的 REQUIRED_SOURCES 中；改变它会使已冻结 B 工件的源哈希校验失效。须选定新版本、重建并复验 B 工件，或从诊断批次分离该优化，不能关闭校验或覆盖历史证据|
|历史 docs/audit、诊断记录和失败样本|保留来源与失败状态|只作历史证据，不能作为当前提交的 PASS；按实际代码范围重写 PR 标题/正文，避免混入无关批次|

因此 PR #12 当前仍为 Draft，不能宣称整体可合并。近期优先顺序：只读分析工具独立批次 → 调度工具独立批次 → 诊断与 checkpoint 优化解耦/版本化 B 重建 → 运行时整体短测。PR #13 无需等待 PR #12 的性能优化即可单独评审交付。

## 仍暂停的验收

- 一小时连续可靠性、MQTT 长时/压力、故障注入全阶段验收；历史主机暂停和中断样本没有转为 PASS。
- 真实 IoTDA 网络、证书/权限、真实云接受回执、硬件来源及实物端到端验收。
- 延迟/吞吐/长期容量承诺；B 实物效果与 ML 增益结论。

## 下一轮明确出口

1. 按上表从 PR #12 拆出可独立验证的代码并提交短测证据；冻结源冲突处理前不合并耦合优化。
2. MQTT 库存采集已具备默认单次、长时显式开关、独立输出及 INCOMPLETE 留痕；仍需实现 broker/publisher/edge 归属编排、阶段控制、ACK 时间证据、主机暂停/采样覆盖、进程资源、WAL/SHM 与退出一致性汇总。该采集器不是完整长时验收器。
3. 工具补齐并短测后，等待用户明确恢复实验；届时固定提交、依赖、隔离数据库和阶段门槛再运行。失败必须保留，不因中断改写分母。
