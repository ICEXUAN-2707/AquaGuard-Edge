# MQTT 本地执行后端首版

本批始于 2026-11-15，收口于 2026-11-17；基线 b2cdb69，属于 PR #13。没有启动实际 MQTT 服务、计划任务、一小时实验或真实云连接。测试目录保留开始日期 offline-worker-20261115，XML 内记录实际测试时间，不改写历史时间戳。

## 文件说明

|文件|代码职责|限制|
|---|---|---|
|scripts/mqtt_protocol_runner.py|校验固定提交、loopback simulation 来源、阶段顺序/连续边界、TTL 与 boot 恢复约束；默认拒绝执行，超过 60 秒另需显式开关。写 ENTERED/READY/FINISHED/FAILED 收据、阶段采样和最终结果；阶段操作超时、服务提前退出、清理或 DB 检查失败均保留失败|执行完成仅是 execution_status=COMPLETED；故障断言仍为 NOT_EVALUATED，acceptance_passed 与 long_run_acceptance 始终 false|
|scripts/mqtt_local_backend.py：启动与隔离|Windows 专用。校验 main 工作树对应的实际分支 HEAD 与计划一致且 tracked 源干净，TTL 与 online.py 的 AST 常量匹配，端口有效且不同；新目录内生成 broker 配置、数据库、manifest 和日志，edge checkpoint 由业务库所在目录隔离。固定 127.0.0.1/demo01/simulation；配置、令牌仅用于本轮本地服务|“main 工作树”指传入脚本所在仓库根，不要求 Git 分支名为 main。未调用真实云 worker。不复用现有 DB。依赖与 broker 的完整版本锁仍需后续收口|
|同上：归属与 READY|Windows Job Object 绑定本次 runner 和之后的后代进程，异常退出由 OS 回收；保留句柄至 runner 进程退出。记录所创建 PID 与时间，清理只操作保留的 Popen 对象。broker 需自身 Mosquitto 启动日志及 loopback 可达；subscriber 需 READY，edge 需 health，首批消费游标需初始化；edge 重启也需 READY|必须从独立 CLI 进程运行，不能在长期宿主内调用真实 backend.start。Mosquitto 日志门槛保守匹配，尚未做实际 broker 版本兼容验证。资源总量与 OS 暂停指标尚未接线|
|同上：阶段输入|按墙钟约 3 条/秒的 manifest 发布，源为现有 SP-02 sample；停报后回放原来清单开头样本以测试重复，重启沿用 boot，新 boot 后注入一个具有新身份的旧 boot 批次以触发隔离路径|不能用未发送的清单末尾冒充“重复”；旧 boot 注入不能仅重复已有 ID，否则只测到 Journal 去重。输入实现尚未经过真实 MQTT 联调，不能据此断言重复/隔离效果通过|
|同上：退出检查|全部自有进程退出确认后，才以只读方式做业务库/Journal quick_check、重复 OPEN 分组检查、游标/积压库存及 loopback 端口关闭观察。端口仍可达时失败，不查杀占用者|积压被报告，不代表已经证明无消息丢失；退出文件与两库不是原子快照。进程退出未知时跳过 DB 验收，并明确 FAILED|
|tests/delivery/test_mqtt_protocol_runner.py|虚拟时钟与替身服务验证默认关闭、长时关闭、显式 READY、阶段状态、503 留存、启动/中途/清理/完整性失败|不启动 broker 或等待真实阶段时长|
|tests/delivery/test_mqtt_local_backend.py|验证回放清单、旧 boot 新身份、自有进程清理、只读 DB 不变、重复 OPEN 拒绝、broker 日志门槛与退出端口观察|网络/Popen 使用替身，SQLite 使用临时库|

## 验证证据

- 接入、计划、采集、执行控制器与离线 worker 的组合回归：127/127 通过，22.09 秒；docs/audit/offline-worker-20261115/backend-regression.xml。
- 随后补充退出端口检查，最终后端专项：20/20 通过，5.42 秒；docs/audit/offline-worker-20261115/backend-final.xml。与前一组有重叠，不应相加为独立测试总数。
- 初轮后端 13 项证据 backend-tests.xml 保留为历史，不覆盖最终证据。

## 执行开关与仍暂停内容

真实运行入口为 scripts/mqtt_protocol_runner.py，需要 --plan、--output、--broker；未显式 --execute 会在任何后端操作前拒绝，超过 60 秒另需 --allow-long-run。这些参数仅说明接口；暂停期间不运行执行命令。

当前代码可以进入独立审查，尚未证明端到端可运行。下一批：逐阶段业务断言（TTL 未知、重复副作用、重启身份、新旧 boot 隔离）、采样覆盖/主机暂停、各直属子进程资源与 ACK 证据汇总、checkpoint 引用与最终阈值。待用户明确恢复后，再做实际本地 MQTT 短联调和长时验证。PR #14/#15 仍为独立工具批次；本后端没有引入其待合并代码依赖，也未改 B 冻结源。没有合并 main。
