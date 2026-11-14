# MQTT长时验收协议候选（执行暂停）

2026-11-14 工具增量：`scripts/observe_mqtt_capacity.py` 可定时调用只读库存快照，输出独立目录内的 `samples.jsonl`（UTC/单调耗时）和 `result.json`。默认仅采一次；计划超过 60 秒须显式 `--allow-long-run`，当前暂停期间不执行该选项。错误或中断记录 INCOMPLETE，COMPLETED 也始终为 `long_run_acceptance=false`。单次使用：`python scripts/observe_mqtt_capacity.py --journal <journal.sqlite> --db <business.sqlite> --output <新的输出目录>`。它不启动 broker/发布器/worker，不测 ACK、资源、WAL/SHM，不替代下述完整编排与验收。

用户暂停实验期间，只准备代码与协议；本文没有产生长时PASS，也不自动注册或启动任务。

## 恢复执行前

固定提交与依赖，使用新目录、新业务库、新Journal、新boot及空闲loopback端口。broker/subscriber/publisher/edge均须为本次创建，分别记录PID及创建时间；只清理这些自有进程。来源simulation，设备demo01；不改字段伪装硬件，不接真实云。正式长时工具还需实现以下采集和故障阶段，不能仅凭已有短程verify_workbench改seconds就声称完成。

保持用户登录、明确唤醒条件，运行环境不做大批训练/复制；记录普通优先级及主机双时钟。observer和service都需有监督/阶段/退出记录。机器暂停或采样覆盖不足保留为证据条件失败。

## 预先标记的阶段

|阶段|输入/故障|断言与留证|
|---|---|---|
|启动|初始化Journal、订阅READY、启动公开运行时；预留首窗建立时间|无数据时404/UNKNOWN合法，不把startup计为正常连续输入|
|连续输入|三源约每秒各一条、实际墙钟发送；identity唯一、received_at由接收端记录|持续有效观测与分析窗口；不补造历史时间，不把重叠窗当独立trial|
|停报|停止本次发布器超过TTL，并单独标记故障区间|live过期拒绝/未知，UI不延续正常；503在该标记阶段是保护结果，仍保留样本|
|恢复/重发|恢复原boot，受控重复QoS输入|Journal标识duplicate，不重复业务副作用；ACK仍在持久提交后|
|edge重启|保留原库/Journal重启自有edge|消费游标继续、旧事实不倒退、事件身份保持、确认状态不被恢复伪造|
|新boot|发布新boot，再注入少量退休boot|新分析窗重新建立，旧boot隔离；快速水信号与慢窗口边界分别验证|
|退出|停止自有输入及进程，读库检查|DB完整性、唯一OPEN约束、进程退出和端口关闭；日志、结果、失败样本完整保留|

正常连续输入与故障期指标分开，阶段边界必须在运行前定义，不在失败后移出分母。分段通过不能外推所有组合故障通过。

## 必须采集

- 每次采样UTC/单调时间、采样延迟、主机睡眠差、各进程RSS/优先级。
- Journal observations/attempts/rejected、new/duplicate/out_of_order分类、业务消费cursor及未消费有效attempt数。
- 端到端接收/消费延迟与持久ACK延迟（需要独立时间记录；不能将发布端PUBACK当作业务持久ACK）。
- business/Journal含WAL/SHM大小、检查点总量与增长、Outbox状态、事件生命周期及引用完整性。
- API状态/快照年龄、step/tick/SQL锁/检查点阶段墙钟与CPU，慢周期线程堆栈。

已有mqtt_capacity_snapshot.py只覆盖两库只读库存与未消费有效attempt计数。Journal绑定不符、cursor越界拒绝；两库非原子快照且文件大小不含WAL/SHM。它不是完整长时采集器，后续需增加上述其他量测。

## 退出标准

所有阶段符合预设行为；正常连续期无无解释不可用；采样覆盖达到预先门槛；无DB损坏、重复OPEN或无主进程；容量与延迟给出实际量测和支持边界。没有实测数据前不承诺吞吐、磁盘预算或长期有界。不删除工件来让增长指标变好。

若失败，先区分主机暂停/低优先级、Journal逐条全表扫描、数据库锁、文件I/O及业务计算，做最小修复。保留历史FAIL，用户明确恢复实验后才执行长时阶段。
