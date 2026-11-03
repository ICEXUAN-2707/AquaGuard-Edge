# A 技术验证软件阶段收尾报告

日期：2026-10-30。prototype_only。结论：本轮软件实现与执行证据已整理，可交独立Reviewer复核；SP-02整体仍PARTIAL，SP-01硬件验证未开展。本报告优先于历史增量中的旧待办描述。

## 本轮完成范围

三源模拟消息 → 本机Mosquitto → 严格标准化 → SQLite身份/审计 → 唯一DTO导出。包括重复、冲突、乱序、进程重启、Broker重启、持续运行订阅器自动重连、电脑发送端持久队列补发、订阅端持久化后手动确认。

非法观测单独持久化隔离；存储错误不确认并断开。无可信设备时钟时event_time=null，RECEIVED_FALLBACK；未知不转成false。

## 证据索引

最终统一入口已真实执行通过：`spikes/SP-02/evidence/software-closeout-20261030/summary.json`，三个门槛退出码均为0；gate-0.log保存57项检查输出，mqtt/与crash/分别保存真实Broker回归和崩溃重投证据。补发实验仍以独立证据目录为准。

|检查|执行证据|结果与限制|
|---|---|---|
|单元、契约、启动回归|收尾执行57 passed in 6.39s；最终复现日志另存|含只读SQLite真实错误，不等于真实磁盘满/掉电|
|真实100条收发|spikes/SP-02/evidence/baseline-20261030/summary.json|唯一集合一致|
|五组MQTT故障回归|spikes/SP-02/evidence/manual-ack-regression-20261030/summary.json|持续连接恢复、进程重新连接分别验证|
|发送持久化恢复|spikes/SP-02/evidence/offline-queue-20261030/summary.json|无Broker失败后100条保留，新进程补发后唯一100；未覆盖发送中断电|
|提交后确认前崩溃|spikes/SP-02/evidence/crash-ack-python-20261030/summary.json|退出73、重投判duplicate、唯一1；Broker保持运行|

首轮PowerShell崩溃编排失败记录commit-before-ack-20261030不计验收通过。

## 复现入口

在仓库根目录执行，证据目录必须不存在，Broker端口18884/18886须空闲：

```powershell
.\.venv-app\Scripts\python.exe spikes/SP-02/src/verify_release.py --broker 'C:\Program Files\mosquitto\mosquitto.exe' --directory spikes/SP-02/evidence/review-new-run
```

脚本执行软件/契约/启动检查、五组真实Broker场景和崩溃重投，输出逐门槛日志与summary.json；只操作自行创建的本机进程。补发场景证据独立列出，不伪称纳入此脚本。运行方法另见SP-02/README.md。

## 交给B的内容

- baseline-20261030/accepted.jsonl：完整三源唯一DTO样例；来源均simulation。
- fault-suite-20261030中的manifest和received记录：重复/乱序/启动/非法案例，异常日志不能直接当唯一DTO回放文件。
- SP-02/TIME_ASSUMPTIONS.md：时间、seq作用域及补发限制。
- 不能把补发时的received_at当作原始测量时刻；不据此重建真实历史窗口。B联合验收尚未执行，不宣称已完成。

## 后续门槛与非承诺

1. 指定独立Reviewer，复核本报告、脚本、证据与失败退出行为；Owner不能自验收。
2. Broker同时崩溃、持久化会话组合、真实磁盘满/损坏、队列容量与压力测试继续作为后续可靠性任务，不承诺生产可靠性或exactly-once。
3. 当前无报文大小/队列容量限制，仅用于受控小规模实验；不得直接部署公网或生产。
4. SP-01必须拿到匹配实物的手册、完成参数追踪和接线复核后再开发驱动；不包含ESP32持久队列、真实采样、校准或时钟精度结论。
5. 机器合同仍为候选，本轮不替代A/B/C会签，不修改生产API或业务库。

本轮软件工作收尾不等于全部SP-02及A部分最终验收通过。后续按以上门槛进入评审与软硬件联调。
