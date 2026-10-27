# SP-06 技术验证报告

- Owner：C
- Reviewer：待指定
- 状态：IN_PROGRESS
- 范围：`prototype_only`

## 假设

本地 Event、Transition 与 Outbox 可以在一个 SQLite 事务中提交；Mock Cloud 失败不影响本地提交；数据库重开后待发记录和稳定 `message_id` 可恢复。

## 环境与命令

- Python：3.12.10
- SQLite：3.49.1
- 执行命令：`python -m pytest spikes/SP-06/tests -q -p no:cacheprovider`

## 当前证据

首轮原型已实现：三张 SQLite 表、原子写入函数、覆盖目标状态与 payload 的幂等指纹、版本冲突、单进程 Mock Outbox Worker、重开数据库后的 `SENDING` 恢复，以及供人工操作的 CLI 和 JSON 数据集。

扩展后 Spike 测试结果：**14 passed，0 failed**。覆盖版本递增、创建/更新失败回滚、重复请求和同键不同目标冲突、两个 SQLite 连接竞争、Mock 临时/永久失败及发送异常、稳定 `message_id`、回执分层和重开数据库恢复。

人工操作 CLI 已按指南抽查：初始化、创建/更新 Event、Mock 接受/暂时失败、数据库状态检查、`SENDING` 领取与恢复均可运行。

## 限制与后续

- Mock 结果不能代替真实 IoTDA 验收。
- 重启用例通过关闭并重开数据库/worker 实例模拟，不覆盖断电或文件系统损坏。
- 当前按至少一次投递设计，不声称 exactly-once。
- Reviewer 尚未指定；SQLite 方案和测试矩阵仍待独立评审。
