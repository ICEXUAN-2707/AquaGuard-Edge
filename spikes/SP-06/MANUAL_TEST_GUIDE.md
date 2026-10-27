# SP-06 人工测试操作指南

本指南用于人工逐步检查 SQLite + Mock Outbox 原型。所有数据均为合成数据，`source=simulation` 和 `trial=prototype_only`；没有网络请求，不需要 IoTDA 账号。

## 准备

在仓库根目录打开 PowerShell。使用一条全新数据库路径；数据库文件会被 `.gitignore` 忽略。不要复用包含重要数据的 SQLite 文件。

```powershell
$python = '.\.venv-app\Scripts\python.exe'
$runner = 'spikes/SP-06/tests/manual_runner.py'
$db = 'spikes/SP-06/manual_walkthrough.sqlite'
```

如果该文件已经存在且想保留上次结果，把 `$db` 改为另一个文件名。`init` 只创建缺失的表，不会清空已有行。

## 测试一：原子写入、重复请求和版本更新

1. 初始化并写入第一个事件：

   ```powershell
   & $python $runner init --db $db
   & $python $runner submit --db $db --case open
   & $python $runner inspect --db $db
   ```

   预期：Event 版本为 1；有一条 Transition 和一条 `PENDING` Outbox；消息 ID 为 `manual-message-1`。

2. 重放相同幂等键和 payload：

   ```powershell
   & $python $runner submit --db $db --case replay_open
   & $python $runner inspect --db $db
   ```

   预期：输出 `replayed: true`，返回原 Transition/消息 ID；三张表的行数不增加。

3. 检查两种冲突。下面两条命令预期打印 `ERROR` 并返回非零退出码；这是测试通过表现：

   ```powershell
   & $python $runner submit --db $db --case same_key_different_payload
   & $python $runner submit --db $db --case same_key_different_state
   & $python $runner submit --db $db --case stale_version
   & $python $runner inspect --db $db
   ```

   预期：前两条分别是同键不同 payload、同键不同目标状态冲突；第三条是旧版本冲突。数据库仍只有最初的一组记录。

4. 提交第二个版本：

   ```powershell
   & $python $runner submit --db $db --case update
   & $python $runner inspect --db $db
   ```

   预期：同一 Event 当前版本为 2；Transitions 的版本依次为 1、2；Outbox 有两条待发送记录。

## 测试二：Outbox 重试与回执分层

继续使用测试一的数据库，按顺序执行：

```powershell
& $python $runner worker --db $db --outcome accepted
& $python $runner worker --db $db --outcome retry
& $python $runner inspect --db $db
& $python $runner worker --db $db --outcome accepted
& $python $runner inspect --db $db
```

预期：第一条消息被 Mock 接受；第二条先进入 `RETRY_WAIT`，再次发送后成为 `ACCEPTED`。同一条重试消息的 `message_id` 不变、attempts 增加。仅有传输回执时 `business_receipt` 应为 `null`。

另用一个新数据库路径测试业务回执分开写入。先将 `$db` 改成新路径，再运行：

```powershell
& $python $runner init --db $db
& $python $runner submit --db $db --case retry_event
& $python $runner worker --db $db --outcome accepted --business-receipt
& $python $runner inspect --db $db
```

预期：`transport_receipt` 与 `business_receipt` 分别有自己的 provider 和 receipt ID。

永久失败也使用新数据库：初始化后提交 `failed_event`，执行 `worker --outcome failed` 并检查，预期 Outbox 可见 `FAILED` 和错误摘要。

## 测试三：模拟 worker 重启恢复

使用新数据库路径：初始化、提交 `restart_event`，然后模拟 worker 已领取消息但还没保存发送结果：

```powershell
& $python $runner claim --db $db
& $python $runner inspect --db $db
```

预期状态为 `SENDING`，attempts 为 1。现在执行恢复，相当于关闭旧 worker 并用新实例继续：

```powershell
& $python $runner recover --db $db
& $python $runner inspect --db $db
& $python $runner worker --db $db --outcome accepted
& $python $runner inspect --db $db
```

预期：记录先变为 `RETRY_WAIT`，随后可被重新发送；`message_id` 保持 `manual-message-restart`，attempts 变为 2。此步骤测试数据库重开/worker 重建逻辑，不模拟断电或文件系统损坏。

## 测试四：故障注入与整体回滚

新建一份数据库并初始化，然后在新事件写入的 Outbox 步骤注入失败：

```powershell
& $python $runner init --db $db
& $python $runner submit --db $db --case rollback_new_event
& $python $runner inspect --db $db
```

`submit` 预期报 `injected failure`。检查结果应为三张表均无行。

再验证已存在 Event 的更新失败回滚：

```powershell
& $python $runner submit --db $db --case open
& $python $runner submit --db $db --case rollback_existing_event
& $python $runner inspect --db $db
```

第二条提交预期失败。Event 应仍为版本 1，Transition 和 Outbox 也仍各只有一条；没有留下部分更新。

## 执行全套自动用例

人工步骤完成后，可运行完整可重复测试：

```powershell
& $python -m pytest spikes/SP-06/tests -q -p no:cacheprovider
```

记录实际执行命令、输出、数据库检查结果和任何差异到 `REPORT.md`。不要把 Mock 结果记为真实云端通过；不要把 `ERROR` 预期用例当成产品故障。测试结束后，确认 `$db` 指向本 Spike 的临时文件，再按需删除该文件。
