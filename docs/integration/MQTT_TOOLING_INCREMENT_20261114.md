# MQTT 采集工具第二批

基线为 PR #13 的 30054af。本批继续只做代码与离线短测，不启动 broker、worker、发布器、计划任务或真实云连接。

## 文件与行为

- scripts/mqtt_capacity_snapshot.py：显式关闭只读连接；新增 file_bytes，分别观察 Journal/业务库的 main、wal、shm 大小。保留 journal_bytes/business_bytes 的旧语义（仅主文件）。缺失 sidecar 为 0，权限等错误不伪装成 0；主文件缺失仍失败。不执行 checkpoint，不读取/删除 sidecar 内容。
- scripts/observe_mqtt_capacity.py：记录每次采集耗时、采样间隔、相对初始计划的迟到、墙钟与单调钟差。超过一个间隔的迟到或大于 1.5 倍间隔的采样缺口标记 GAPS；单次采样为 UNKNOWN。恢复后不突发补齐历史样本。墙钟差不能单独证明主机暂停，estimated_suspend_seconds 保持 null。
- tests/delivery/test_mqtt_capacity_snapshot.py、test_mqtt_capacity_collector.py：覆盖 sidecar 库存、虚拟主机时间缺口、无突发补采、未知暂停状态、非法间隔拒绝及不产生虚假验收结论。

COMPLETED 仅表示要求的采样次数写入完成，即使覆盖为 GAPS 也不会转换成验收 PASS；long_run_acceptance 始终 false。计数、文件大小和两个数据库之间均非原子快照。迟到阈值只用于观测记录，并非项目的最终可用性门槛。

## 尚待实现的完整编排

受控进程归属/退出、broker 与 subscriber READY、预声明连续/停报/重复/重启/新 boot 阶段、独立持久提交与 ACK 时序、进程 RSS/优先级、OS 暂停证据、checkpoint 引用和退出完整性汇总仍需要后续批次。当前工具不会执行这些阶段，也没有将它们标为通过。只有用户明确恢复后才执行长时测试。

只读分析工具已另从 main=5f5bc94 建立 feat/read-only-runtime-tools-20261114 分支，避免 PR #12 的 checkpoint 与 B 冻结源冲突；本批不依赖该工具分支合并。
