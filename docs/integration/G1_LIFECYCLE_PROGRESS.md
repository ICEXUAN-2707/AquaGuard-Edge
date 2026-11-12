# G1 生命周期与 boot 恢复

日期：2026-11-10。基于已推送的 3c96242，工作树 `.c23-process`。
本记录更新 G1_CLOSURE_PROGRESS 中尚无关闭和 boot 切换的历史限制。

## 产品行为

- 本地原型新增 `POST /api/events/{event_id}/close`，使用 Bearer 授权，参数为
  schema_version、expected_version、idempotency_key。不改变共享 A/B DTO。
- 仅已确认、物理 CLEARED、生命周期 OPEN 且恢复证据仍新鲜时允许关闭。
  water 使用持久化策略 TTL；context 使用现有 10 秒窗口新鲜度。
- 关闭转换、版本、Outbox 及幂等操作记录同事务写入。关闭与 ACK 使用同一
  幂等键空间，但区分操作内容；同键异操作冲突，旧操作重放不改变历史。
- 确认或干燥本身不自动关闭。关闭后再次发生生成新的未确认事件。
  快慢路径重复使用已归属关闭事件的 evidence_refs 时不重开旧告警。
- 页面提供关闭按钮，并显示条件不满足、版本冲突及不确定网络结果；
  不确定结果重试原关闭请求，避免自动生成新操作键。
- MQTT 接受从未见过的新 boot：清空分析内存历史、重新积累 30 秒窗口，
  持久化 boot 记录。重启只加载当前 boot 历史；dry 链由 WaterService
  的既有 boot 边界重置。退休 boot 仍失败关闭，不默默回退至旧启动状态。

## 同轮真实本地 MQTT + 浏览器

构建页面后，在已有 Playwright/Chromium 环境中执行：

```powershell
..\.venv-app\Scripts\python.exe spikes/SP-02/src/verify_workbench.py --directory audit/g1-lifecycle-browser-01 --broker 'C:/Program Files/mosquitto/mosquitto.exe' --lifecycle
```

该目录须全新，复跑须换名称。Playwright/Chromium 环境变量配置沿用上一记录。
本轮受控 simulation 数据经本地真实 broker 输入，依次 wet、dry、再次 wet。
Chromium 10 项检查 PASS，页面关闭成功并出现第二个水事件；API 复核同时存在
已关闭事件及新的 OPEN/UNACKNOWLEDGED 水事件，Outbox pending_count=6。
无 pageerror。证据位于该目录的 result.json、events.json、browser/ 和数据库。
409/503 UI 检查为显式注入；不是云回执、实物采集或真实断网证据。

初次完整回归 282 passed / 1 failed：旧测试固定 API 总数为 7，不允许新增
本地关闭路由。已改为核对原七条候选路径完整存在，并检查新增关闭路由。
未删除任何原路由。另补关闭后旧证据重放检查。

最终完整回归 **283 passed / 146.60s**，退出 0；证据：
`audit/g1-lifecycle-final.xml`。范围为 C-business、SP-06、contracts、smoke。
`npm.cmd run build --prefix web`、`node --check web/tests/browser-acceptance.cjs`
及 `git diff --check` 通过。已查看关闭后事件页面截图，确认旧事件历史与新事件
同时展示。浏览器先于最后的低层历史证据去重保护运行，该保护由最终回归验证。

## 仍需推进

退休 boot 目前会阻止继续消费，需操作员核查 journal；尚无隔离坏记录的入口。
跨 boot 的端到端浏览器故障恢复、真实停报后的 UI 恢复仍需专门演示证据。
检查点/日志保留、容量/磁盘故障、长跑、云及最终竞赛材料不由本增量放行。
因此不宣称整个 G1 或全部 C 部分验收通过。
