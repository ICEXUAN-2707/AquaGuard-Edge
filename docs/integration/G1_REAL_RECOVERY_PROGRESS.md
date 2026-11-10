# G1 真实停报、重启和 boot 恢复验收

日期：2026-11-10。基于 d93cbe9，全部工作位于 `.c23-process`。

新增 `verify_workbench.py --recovery` 与独立浏览器恢复脚本，复用原有
Mosquitto、SP-02 journal、SQLite、分析引擎与三页面，不增加第二套运行平台。

场景：首轮真实 MQTT simulation 输入 45 个三源采样周期，暂停输入 18 秒，
通过真实 TTL/页面轮询观察过期，然后停止并重启自有 edge 进程，继续使用
原 business.sqlite、journal.sqlite 和访问凭据。第二轮使用全新 boot，
再发布 45 个三源周期。浏览器保持同一页面，不刷新、不拦截 HTTP、不注入响应。

首轮 `audit/g1-recovery-browser-01` PASS：

- 页面先显示 MQTT 数据；停报后显示过期且不保留传感卡片。
- API 中原水事件变为 UNKNOWN；新 boot 输入后恢复 ACTIVE，event_id 不变。
- 同一浏览器自动恢复三源与情境显示，无 pageerror。
- 未关闭事件恢复不产生第二个告警。Outbox 保留三次转换，pending_count=3。

已人工检查过期与恢复截图，来源明确为 simulation，云状态仍 UNKNOWN。
此处验证的是业务 journal 消费进程重启，不是 MQTT subscriber 或 broker 崩溃。
历史 A ingress 的重投证据不能替代本场景，也不把模拟观测称为真实硬件。

## 复现最终版本

先按前一记录安装独立 Playwright 工具、构建 web，设置
`AQUAGUARD_PLAYWRIGHT`、`AQUAGUARD_CHROMIUM`，然后运行：

```powershell
..\.venv-app\Scripts\python.exe spikes/SP-02/src/verify_workbench.py --directory audit/g1-recovery-browser-final --broker 'C:/Program Files/mosquitto/mosquitto.exe' --recovery
```

目录须全新；默认端口 18886/8021，脚本先检查占用，不终止别人的进程。
结束仅清理本轮创建的进程。最终脚本在所有正常/异常路径导出 cleanup.json，
记录 PID、退出码、是否确认退出；terminate 超时再 kill，仍未确认则验收失败。
这是对响应正常的本机 OS 的退出观察，不是任意阻塞系统调用的硬时限保证。

最终版本还导出 run.json（Git SHA、是否有已跟踪修改、Python/OS、端口和模式）
与 result.json 的输入清单 SHA256/耗时，不导出访问凭据。运行过程中使用的
临时 token/key 仅通过子进程环境传递。完整本地目录含输入、SQLite、检查点、
日志与截图；提交仅保留精简 JSON/XML 及代码报告，数据库和工具不推送。

最终复跑 `audit/g1-recovery-browser-final` PASS，耗时 118.26 秒。
浏览器 3 项真实恢复检查通过，无 pageerror；cleanup.json 记录的 7 个自有进程
全部确认退出。主动 terminate 的服务在 Windows 下退出码为 1，不冒充优雅退出。
相关回归 18 passed / 53.66s，XML 为 `audit/g1-recovery-regression.xml`，
范围为 MQTT journal、生命周期、C runtime、公开 simulation runtime smoke。
仅验收脚本变化，没有重新运行全部 283 项；历史计数不相加。
`node --check web/tests/browser-recovery.cjs` 和 `git diff --check` 通过。

## 仍未放行

该场景是一次有限时长的受控本地验证，不是容量、磁盘不足、长期稳定性验收。
退休 boot 的隔离/继续消费策略、检查点和日志保留、B 指标/模型卡展示仍需推进。
真实 IoTDA、断网补传、云应用、CodeArts 及最终材料仍未由本记录验收。
