# MQTT ACK 时序与阶段计划准备

本批只做短时离线测试，没有连接 MQTT broker、真实云或启动计划任务。

验证：SP-02 接入单测 50/50 通过；接入、阶段计划、容量采集与离线装配/Delivery/Outbox 的组合回归 109/109 通过（21.37 秒）。最终证据 docs/audit/offline-worker-20261114/mqtt-ack-plan-regression.xml。调度工具在独立 main 基线分支 feat/owned-supervisor-tools-20261114 验证 8/8，通过的只是代码与数秒子进程检查，不是原一小时实验。

## 文件与边界

- spikes/SP-02/src/ingress.py：process_message 新增可选 timing/clock。保留原提交后 ACK 顺序；记录入口、存储开始、Journal 返回、ACK 调用和返回的单调时钟与 observation_id/boot/seq。存储失败不 ACK；提交后中断或 ACK 调用失败不标记 ack_submitted。未开启计时的旧调用不调用新时钟。
- spikes/SP-02/src/cli.py：显式 --timing-evidence 才写 subscriber-timings.jsonl，flush/fsync 后保留。日志失败会标记错误并断开，不以缺失证据声称通过。指标是客户端 c.ack() 成功返回，即 ACK 提交给客户端，broker_ack_confirmed 始终为 null；不是 broker 收到 ACK 的确认、云接受或业务事件人工确认。after_commit 强制 os._exit 注入会跳过 finally，缺失记录必须算证据不足，不能补造。
- scripts/prepare_mqtt_protocol.py：纯计划入口，无执行选项。要求固定完整提交 SHA 和显式 TTL；停报时长必须大于 TTL。一次性创建 plan.json，预先划分启动、连续、停报、原 boot 恢复/重复、edge 重启、新 boot 和退出；保留 boot 恢复身份。PREPARED 不等于执行成功。阶段偏移是计划，不是实测时间。
- spikes/SP-02/tests/unit/test_ingress.py、tests/delivery/test_mqtt_protocol_plan.py：测试独立连接可见的持久提交、故障边界、不开启计时的兼容、无效计划零输出、已有计划不覆盖及 boot 连续性。

计划命令（不启动实验）：

```powershell
python scripts/prepare_mqtt_protocol.py --output <全新计划目录> --revision <完整40位提交SHA> --ttl 10 --stop-seconds 18
```

TTL 示例对应当前在线窗口配置，但工具不读取运行时；正式执行前必须对固定版本核对。连续阶段默认 3600 秒，仅写入计划，不等待一小时。不应在暂停期间运行 subscribe/publish 命令。

下一批仍需受控 broker/subscriber/publisher/edge 的执行后端、READY 门槛、实际阶段收据、每个子进程资源、OS 暂停证据、消费延迟与退出 DB 不变量汇总；最终覆盖率/延迟阈值必须在恢复执行前确定。本批没有完成完整 MQTT 长时验收器，没有性能或可靠性 PASS。
