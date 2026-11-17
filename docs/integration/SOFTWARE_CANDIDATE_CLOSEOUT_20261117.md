# 软件候选收尾记录

基线 133ba00，本文件随 PR #13 收尾提交。main=5f5bc94；B PR #11 已合并，PR #12/#14/#15 尚待独立审查。当前收尾对象为 simulation_test 离线装配与 MQTT 验证软件候选；实际 MQTT、长时与真实云验收继续暂停，实物验收仍待证据。代码准备进入正式评审，不自动合并 main。

## 收尾范围与文件

|文件|最终补齐内容|
|---|---|
|scripts/mqtt_closeout_evidence.py|只读 checkpoint 引用/数量/字节盘点，缺失/越界引用及损坏 JSON 拒绝；未观察到引用不允许删除。离线生成运行锁，固定 Python/平台、已安装包、应用及前端锁文件 SHA、broker 文件 SHA 与预声明版本。按稳定 observation_id 汇总发布开始到消费游标提交的本机延迟，重复发布保留计数，缺失/失败/反向时钟/错误证据 scope 为 INCOMPLETE|
|scripts/mqtt_local_backend.py|实际执行前强制对比运行锁，启动前再次核对；broker 自身启动日志版本必须匹配。采样 checkpoint 数量与字节，退出检查盘点引用及延迟证据。发布器用自有 stop.request 在消息间退出；最终关闭前要求 ACK 证据、延迟记录和消费队列排空，之后确认进程退出、端口和数据库完整性|
|scripts/prepare_mqtt_protocol.py|新增 --runtime-lock，将锁内容随计划冻结；保留显式预算、固定 revision/TTL/阶段/boot。单纯 PREPARED 不启动任何服务，也不代表批准执行|
|spikes/SP-02/src/cli.py|可选发布时序日志与 --stop-file。publish_start 取自本机 perf_counter，PUBACK 成功/失败均保留记录；默认调用行为兼容，不伪造业务确认|
|spikes/C-business/mqtt_journal.py|新增可选 timing_sink/timing_clock；真实游标事务提交后写稳定 ID、attempt 编号、处置和时间。正常消费、旧 boot 隔离都记录。记录失败不会回滚已提交事务，错误仍传播；内存状态先更新，避免观测写入失败造成历史行遗漏|
|spikes/C-business/run.py、edge/runtime.py|仅显式 AQUAGUARD_MQTT_TIMING 路径启用消费时序 sidecar；默认不启用。未改公共 DTO、数据库 Schema 或 B 冻结算法|
|新增/更新测试|版本锁不符、缺失/越界 checkpoint、无效时延、PUBACK 失败、消息间停止、提交后证据写入失败、重启及正式入口兼容。网络/Popen 用替身；既有本地 HTTP/运行时短测继续执行，未启动 MQTT broker|

## 证据与环境失败

证据目录：docs/audit/offline-worker-closeout-20261117/。

|记录|结果与解释|
|---|---|
|targeted.xml|38 项中 13 失败；系统 C 盘空间不足导致临时 SQLite/文件写入失败，保留原始记录|
|targeted-workspace.xml|38 项 setup error；迁移测试临时目录时父目录未创建，测试尚未进入业务代码，保留记录|
|targeted-workspace-final.xml|改用 D 盘全新临时目录并仅在测试进程设置 TEMP/TMP 后，38/38 通过（54.17 秒）|
|final-regression.xml|最终组合离线回归 202/202 通过，0 失败/错误/跳过（68.55 秒）。包含新旧工具、真实业务消费、正式入口和本地 HTTP 短测；不是一小时实验|
|frozen-sources.json|39 个 REQUIRED_SOURCES 与本分支相对 main 的差异交集为空；只证明未改 B 冻结源，不冒充重新完成 B 效果评估|

不同范围不相加。未清理用户文件，未改系统持久环境变量。D 盘测试解决了本批临时目录问题；C 盘剩余空间仍是恢复实际实验前需检查的主机条件。

## 可复现的离线准备

在固定提交的干净工作区和匹配 requirements-app.lock.txt 的 Python 环境中，先创建全新输出目录，再执行以下准备步骤。它们不启动 broker、不连接 MQTT/云：

```powershell
python scripts/mqtt_closeout_evidence.py --broker <mosquitto.exe> --broker-version <明确数字版本> --output <新的runtime-lock.json>
python scripts/prepare_mqtt_protocol.py --output <新的计划目录> --revision <完整提交SHA> --ttl 10 --stop-seconds 18 --runtime-lock <runtime-lock.json> --thresholds <预声明预算.json>
```

预算字段与约束见 MQTT_OBSERVATION_BUDGETS_20261117.md；没有预填项目性能标准。broker 版本由准备者声明，未来实际启动时还要核对自身日志；本批没有执行 broker 来验证版本兼容。前端 package-lock 只作为清单指纹，不代替前端部署/浏览器验收。

## 验收边界与下一出口

1. 本批代码与限定离线回归已收尾，PR #13 可进入独立代码评审。PR #14/#15 为独立工具候选；PR #12 的 checkpoint 优化仍需解耦或版次化重建 B 工件，不能绕过冻结源检查。
2. 延迟只量到同一 Windows 主机的消费者游标提交（记录时间在事务返回后，包含观测开销），不是事件/窗口/UI/云端完成；旧 boot 隔离也会提交游标。需要实际输入才有真实延迟与容量数据。
3. checkpoint 盘点是显式引用与文件大小观察，不改保存算法、不做自动回收；长期增长是否可接受仍需预声明预算和实测。
4. 整体 acceptance_passed/long_run_acceptance 保持 false。恢复实验后先固定 SHA/锁/预算做本地 MQTT 短联调，再执行完整阶段与长时验证。默认连续阶段 3600 秒，故障等阶段另加 213 秒，不能混淆成总计一小时。
5. 最终作品仍需 D1 实物/标定/真实 trial、D3 真实 IoTDA 与云上应用、D4 真实评估及 CodeArts/材料/联合签署。完整清单见 docs/project/DELIVERY_GAPS_20261117.md。用户已确认的本地四页人工验收继续有效。
