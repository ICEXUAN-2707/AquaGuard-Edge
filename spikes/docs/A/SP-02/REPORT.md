# SP-02 阶段报告

**当前结论：本轮软件阶段已收尾，可交评审；整体SP-02为PARTIAL。** 统一证据与未完成门槛见 [软件阶段收尾报告](../A_软件阶段收尾报告.md)。下文为历史增量，不作为当前完成状态清单。

最新：订阅端已实现SQLite提交后手动MQTT确认及非法消息持久隔离。20项单元测试通过；真实提交后确认前崩溃重投PASS，证据evidence/crash-ack-python-20261030。两次接收new/duplicate，唯一观测1。需稳定客户端ID和持久会话，Broker保持运行；不保证Broker同时故障无损。详见软件验证进度。

当前汇总以 [软件验证进度](../A_软件验证进度.md) 为准。新增发送端持久化队列，16项单元测试通过。真实离线补发实验evidence/offline-queue-20261030：无Broker发送失败后保留100条，新进程在Broker恢复后补发，接收唯一100，队列清零。整体仍PARTIAL。

## 2026-10-30 增量

完整故障场景回归：evidence/fault-suite-20261030/summary.json，五组全部PASS。新增同身份异内容判conflict、额外非法字段判invalid，随后合法消息仍判new；自动重连复测约1.031秒。非法载荷隔离后客户端最终非零退出符合本场景预期，编排器核对了分类而非将退出异常忽略。

持续运行的订阅端自动重连实测PASS：evidence/live-reconnect-20261030/summary.json。停止/恢复本轮Broker后，订阅进程未重启，约1.016秒重新完成订阅并接受一条新观测；时间来自同一订阅进程的单调时钟。仅为本机单次测量，不是网络恢复性能保证。CLI增加连接时间线与1–4秒重连退避配置。单元回归14 passed in 0.50s。

新增verify_mqtt.py，在独立回环端口18884真实执行三组场景，全部PASS：重复/乱序；发布与订阅进程重新启动后持久化去重及新boot接收；停止并重新启动Broker后重新建立客户端连接，继续去重和处理。证据：evidence/restarts-20261030/summary.json及各客户端/Broker日志。本轮没有验证客户端持续运行时的自动重连，也没有验证断线期间离线积压或崩溃确认窗口；不据此声明无损补发。

新增analyzer集合核对，单元测试14 passed in 2.14s。通过winget获取Mosquitto 2.1.2，安装包哈希验证成功。本机回环Broker实际运行100条三源模拟消息：发送唯一100、收到100、接受100，missing/unexpected均为空；证据在evidence/baseline-20261030/。已导出accepted.jsonl。

本次仅基线场景PASS，整体仍PARTIAL；重启、断连与故障编排尚待执行。下文未安装Broker的描述为此前历史状态。

日期：2026-10-29。prototype_only。状态：PARTIAL，未独立验收。

已完成三源模拟生成、标准化、DTO校验、稳定身份、重复/冲突/乱序分类、SQLite身份持久化及导出；提供基础本机MQTT CLI与回环Broker配置。

实际运行：`.venv-app/Scripts/python.exe -m pytest spikes/SP-02/tests/unit -q -p no:cacheprovider`，结果12 passed in 0.98s。覆盖三源、未知、非法输入、数据库重开去重、冲突、乱序和新boot；仅为纯逻辑证据。

环境：Paho 2.1.0、pytest 9.1.1；PATH及C:/Program Files/mosquitto/mosquitto.exe均未找到Broker。真实通信未执行。

待完成：真实100条收发、集合自动统计、故障编排、会话/retain对照、持久化后手动确认及队列/磁盘故障。当前CLI不承诺崩溃零丢失；乱序检查全表扫描需后续优化。

SP-01尚缺匹配实物手册，未实施驱动或确定电气参数。Reviewer待组内指定。
