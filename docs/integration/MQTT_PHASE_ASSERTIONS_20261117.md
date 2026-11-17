# MQTT 业务阶段断言与 ACK 证据汇总

本批基线 d7bda41，属于 PR #13，仍为离线代码候选。PR 还包括既有 simulation_test 离线云 worker（只读验证已有业务库/完整唯一 OPEN 索引/兼容策略后装配）、持久完成时钟、容量采集、ACK 调用计时与本地执行后端。没有放开 hardware 来源、旧库迁移或真实云传输。

|文件|本轮改动|实际可证明范围|
|---|---|---|
|scripts/mqtt_phase_evidence.py|以业务库只读事务截取 OPEN 水事件、转换总数、boot/cursor、隔离计数；另读 Journal 重复计数。evaluate 返回 SATISFIED/VIOLATED/INCOMPLETE 和具名断言|业务库与 Journal 非原子快照；验证本次受控水接触路径，不声称覆盖所有情境或全部 Outbox 消息的副作用|
|scripts/mqtt_local_backend.py|阶段操作前/后取证，接入断言；全部进程退出后汇总 subscriber-timings.jsonl。日志缺失/非法/未完成会让退出检查失败|未实际运行 MQTT；断言实现通过离线样例验证，不代表业务真实链路已通过|
|scripts/mqtt_protocol_runner.py|写 ASSERTED 收据及 phase_assertions；断言不满足/证据不足会中止后续阶段、保留 FAILED 并清理；采样间隔至少 1 秒|局部断言满足仍不升级为整体或长时验收；acceptance_passed、long_run_acceptance 始终 false|
|scripts/mqtt_ack_summary.py|逐行保留总记录、完成/未完成/非法数；完成且有效的记录计算 nearest-rank p50/p95/max；拒绝负数、NaN/inf、时延组成不一致及 broker 确认伪声明|只度量 subscriber 本地 Journal 返回与 ACK 调用；不是 broker 确认、publisher→业务端到端、IoTDA 接收或人工确认。失败/非法行留在分母，分位数明确只对应有效完成记录|
|tests/delivery/test_mqtt_phase_evidence.py、test_mqtt_ack_summary.py|正向、违反不变量、缺证据、只读不改库、缺库不创建、非法时延和回执声明测试|临时 SQLite/合成快照，未启动服务|
|tests/delivery/test_mqtt_protocol_runner.py、test_mqtt_local_backend.py|补充断言失败/证据不足中止与清理，并适配退出证据契约|虚拟时钟/替身进程，无 broker 连接|
|docs/project/PROJECT_STATUS.md、DELIVERY_GAPS_20261117.md|更新已合并/待评审状态，按最终 D1–D4 列出差距与完成出口|不以测试数累加或工具完成率替代整体验收|

阶段检查包括：唯一 OPEN 水事件与 simulation 来源；TTL 后 UNKNOWN、同一事件；恢复后 ACTIVE、ACK 不变、重复计数增长且仅出现预期恢复转换；edge 重启保持事件身份/ACK/cursor；new boot 生效并观察到旧 boot 三源隔离；正常连续期采样均可用。缺少任何需要的字段为 INCOMPLETE。

验证：专项 46/46 通过；最终组合离线回归 155/155 通过（37.54 秒）。证据 docs/audit/offline-worker-20261117/phase-evidence-tests.xml、phase-evidence-regression.xml，范围有重叠，不相加。

剩余：资源/OS 暂停和覆盖率接线、checkpoint 与端到端延迟证据、版本锁/阈值、独立评审与集成；实际 MQTT 短联调和长时、真实硬件与 IoTDA/云应用验收仍暂停或待证据。完整差距见 docs/project/DELIVERY_GAPS_20261117.md。原工作台人工验收继续有效，没有合并 main。
