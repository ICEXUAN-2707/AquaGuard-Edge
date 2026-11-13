# 暂停长时实验后的离线装配

基线main=5f5bc94，已包含B PR #11。新分支feat/offline-worker-closeout-20261113不修改B冻结输入、规则或模型工件。

新增spikes/C-business/offline_cloud_worker.py：显式加载既有测试配置、仅接受simulation_test绑定及已有隔离数据库，使用IoTDAAdapter执行真实消息映射，但只装配OfflineTransport。该传输没有网络客户端或socket构造，仅支持retry/permanent，不提供accept模式、不写假云回执。CLI steps为1..100，不持续调度，不开启真实云。

DeliveryService新增可选finish_clock；本入口以发送结束时刻finish，从完成时刻计算重试，旧Mock调用仍使用原now语义。保持现有mock-r05-v1持久策略和simulation-only来源限制，不做旧库迁移或硬件授权放行。

运行模板：在完整仓库根目录、已设置AQUAGUARD_IOTDA_*测试配置后，应用Python执行spikes/C-business/offline_cloud_worker.py --db <隔离业务数据库> --mode retry --steps 1。配置仍校验测试绑定/CA，但不会连接endpoint。不得使用正在演示或保留证据的数据库。

新增scripts/mqtt_capacity_snapshot.py：只读查询Journal记录数、业务消费游标、尚未消费的有效attempt数量；拒绝Journal绑定不符及缺失数据库。两库不是原子快照，统计仅观察，文件大小不含WAL/SHM，不据此签收性能或长时容量。

调用：python scripts/mqtt_capacity_snapshot.py --journal <journal.sqlite> --db <business.sqlite>。不启动broker、发布器或实验。

短程离线验证：装配/交付/IoTDA适配18项通过，快照与装配5项通过（范围重叠）。包括完成时刻重试、硬件绑定拒绝、无伪造回执、关闭传输、旧Mock兼容、只读不创建缺失库、积压计数排除重复attempt。未执行长时/压力/真实云测试。

后续：对finish-time租约过期、持久策略迁移及进程隔离工厂另批评审；先完成本机故障测试再考虑显式真实网络入口。MQTT长时场景待用户恢复实验后执行，记录ACK延迟、消费lag、Journal/WAL/检查点及各进程资源；暂停期间仅准备工具与协议。

第二批短程验证：交付/Outbox/离线装配/快照34项通过。发送完成恰达租约边界返回STALE，之后仅由claim恢复过期租约；再次发送保持原message_id，并按第二次完成时间计算退避。完成时间倒退保留可恢复SENDING，非法finish_clock在claim前拒绝。非默认旧持久策略明确要求评审迁移，不自动改写。MQTT消费cursor超过Journal库存时拒绝，不报告假零积压。

长时协议候选见MQTT_LONG_RUN_PROTOCOL_20261113.md，列明准备、连续输入、停报、重复、重启、新boot和退出阶段及采集缺口；本批没有执行该协议。
