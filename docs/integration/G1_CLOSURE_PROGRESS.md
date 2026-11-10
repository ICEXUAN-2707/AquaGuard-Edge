# G1 C 闭环增量记录

日期：2026-11-10。全部写入 `.c23-process`。

## 基线

当前分支从 5100d82 快进至已提交的 MQTT 基础 dd9d3d8，保留全部未提交
C23 文件。只读检查 `.delivery-closeout`，未修改其工作树。该增量不接入云端。

## 同轮 MQTT 与浏览器验收

`verify_workbench.py --browser` 在同一轮启动自有 Mosquitto、SP-02 消费者、
MQTT 发布者和公开 edge 服务，并行运行 Chromium 浏览器三页检查。使用
simulation 明确标记的输入，未使用内部自动生成观测作为替代。

```powershell
npm.cmd run build --prefix web
$env:AQUAGUARD_PLAYWRIGHT=(Resolve-Path audit/g1-browser-tools/node_modules/playwright).Path
$env:AQUAGUARD_CHROMIUM='C:/Program Files/Google/Chrome/Application/chrome.exe'
..\.venv-app\Scripts\python.exe spikes/SP-02/src/verify_workbench.py --directory audit/g1-mqtt-browser-01 --broker 'C:/Program Files/mosquitto/mosquitto.exe' --browser
```

目录必须是新的；复跑请换目录。Playwright 为独立测试工具，不增加生产依赖。
结果 PASS，8 项页面检查通过；API 复核 WATER_CONTACT 为 ACKNOWLEDGED，
Outbox pending_count=2，实验为 mqtt-trial 且存在检查点引用。浏览器无 pageerror。
桌面事件截图已人工查看，已确认与物理异常、生命周期分开显示。

证据：`audit/g1-mqtt-browser-01/result.json`、`events.json`、`manifest.jsonl`、
`journal.sqlite`、`business.sqlite`、日志及 `browser/` 内的结果与截图。
该脚本只停止本轮创建的进程。409 冲突与 503 页面反馈由浏览器注入，
不能作为真实网络故障证据。MQTT、分析、事件和成功 ACK 使用真实本地服务。

## 恢复边界

新增 G1 测试覆盖快慢水路径唯一事件、重启后重复输入、ACK 不清除物理异常、
连续 dry 恢复、再次 wet、原时间积压、停报 UNKNOWN、迟到拒绝、boot 切换及
退休 boot 拒绝后的事务完整性。

修复 JournalRuntime：迟到 water 不再因水状态水位已推进而卡住整个消费者；
不回退水位，记录 `BEHIND_WATER_WATERMARK` 后推进游标。过期积压记录
`STALE_BACKLOG`。记录和游标在同一个 SQLite 事务提交，原始输入仍在 journal。
water 快路径与游标仍通过稳定 observation_id 支持崩溃重放，不宣称跨库原子提交。
这不是恢复迟到 wet 的历史告警，而是明确丢弃其即时控制作用并保留理由。

增量前完整回归 277 passed / 148.48s。修复后相关测试 9 passed / 7.94s：
`audit/g1-boundaries-final.xml`。计数范围重叠，不相加。

最终代码完整回归：278 passed / 143.02s，退出 0；XML 为
`audit/g1-regression-final.xml`。执行范围为 `spikes/C-business/tests`、
`spikes/SP-06/tests`、`tests/contracts`、`tests/smoke`，使用当前工作树父目录
已有 `.venv-app`。`git diff --check` 通过。没有提交或推送本次增量。

## 尚未放行

- MQTT runtime 仍采用一个 boot 对应一个 trial 库的策略，boot 变化失败关闭；
  WaterService 底层 boot 切换测试不能冒充 MQTT 持续跨 boot 已完成。
- 事件尚无关闭操作；恢复后仍 OPEN，再次 wet 保留相同 ID 与已确认状态。
  这是现状测试，不满足最终关闭后再次发生需新告警的完整生命周期要求。
- 浏览器组合验收先于最后迟到输入修复执行；修复后完整回归通过，尚未再次运行浏览器组合。
- 未完成真实停报的浏览器恢复、长跑/容量/磁盘异常、云回执及最终材料。

因此 G1 仍为 PARTIAL；不得用这次浏览器通过宣称全部 C 工作完成。
