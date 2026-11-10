# C 本地闭环收尾与交付索引

日期：2026-11-10。工作目录 `.c23-process`，基础提交 df8184d。
范围为本地 simulation 软件闭环；真实硬件、云和竞赛最终材料不是本记录的完成项。

## 可复现入口

使用工作树父目录已有 `.venv-app`，在本工作树执行。需本机 Mosquitto、Chrome、
独立 Playwright 模块，配置路径见 G1_CLOSURE_PROGRESS。每次使用全新输出目录。

```powershell
npm.cmd ci --prefix web
npm.cmd run build --prefix web
$env:AQUAGUARD_PLAYWRIGHT=(Resolve-Path audit/g1-browser-tools/node_modules/playwright).Path
$env:AQUAGUARD_CHROMIUM='C:/Program Files/Google/Chrome/Application/chrome.exe'
..\.venv-app\Scripts\python.exe spikes/SP-02/src/verify_workbench.py --directory audit/new-lifecycle-run --broker 'C:/Program Files/mosquitto/mosquitto.exe' --lifecycle
..\.venv-app\Scripts\python.exe spikes/SP-02/src/verify_workbench.py --directory audit/new-recovery-run --broker 'C:/Program Files/mosquitto/mosquitto.exe' --recovery
..\.venv-app\Scripts\python.exe spikes/C-business/export_evidence.py --directory audit/new-recovery-run --output audit/new-recovery-evidence.zip
```

若工具目录尚不存在：`npm.cmd install --prefix audit/g1-browser-tools playwright`。
上述两个场景各自启动并停止自有进程，端口占用直接失败，不杀其他服务。
这是有界验收入口；长期人工演示启动仍按 MQTT_WORKBENCH_RUNTIME 的独立进程命令。
依赖入口当前仍包含 spikes，交付时必须保留完整仓库，不能只复制 edge。

## 证据索引

| 项目 | 证据与报告 |
|---|---|
| MQTT→分析→三页→ACK | G1_CLOSURE_PROGRESS；audit/g1-mqtt-browser-01 |
| 物理恢复→显式关闭→复发新事件 | G1_LIFECYCLE_PROGRESS；audit/g1-lifecycle-browser-01 |
| 真实停报→UNKNOWN→重启与新 boot→同页恢复 | G1_REAL_RECOVERY_PROGRESS；audit/g1-recovery-browser-final |
| 退出确认、版本配置、输入哈希 | 上一目录 run.json、cleanup.json、result.json |
| 进程隔离/TLS 阻塞原型 | C23_01 至 C23_03 报告；不是已集成生产云连接器 |
| 本批隔离、SQLite 满与回滚 | audit/g1-closeout-targeted.xml，7 passed / 5.60s |
| 最终完整回归 | audit/c-local-closeout-final.xml |
| 本地可交付证据包 | audit/c-local-delivery-evidence-final.zip；19 文件 SHA256 校验通过 |

证据包包含输入、SQLite 备份、检查点、截图及校验清单；不含凭据、工具和服务原始日志。
只接受 cleanup.json 确认全部自有进程退出的运行；输出已存在则拒绝覆盖。
SQLite 备份已执行 integrity_check；不是正在运行系统的跨库原子快照。
检查点引用保留原绝对路径，跨机器重放需要路径映射；包不是一键可移植应用。
首次导出因未显式关闭 SQLite 连接而失败，修复后重新导出并全量校验通过。

## 本批收尾行为

退休 boot 记录到 mqtt_quarantine，与游标同事务提交；原记录保留在 journal。
它不回退当前 boot、不写入分析历史、不改变事件状态，后续合法输入继续消费。
重启仍仅加载当前 boot。未授权 source/设备仍失败关闭，不自动信任未知来源。

SQLite 满测试使用真实页数配额及大 BLOB 触发 SQLITE_FULL，没有填满用户磁盘。
失败后事件、转换、Outbox、观测及状态全部回滚；解除配额/触发器后原输入可成功重试。
这是 SQLite 引擎满错误，不是操作系统掉电、损坏或整个磁盘物理耗尽测试。

持续运行新增六分钟仿真时间检查：三源历史最多 543 条、窗口连续推进、
Outbox 与转换数量一致、OPEN 唯一性、检查点可复算及数据库完整性与重开。
仿真时间与实际墙钟时长分开，不据此声称数小时或数天无人值守稳定。

## 剩余边界

- 检查点、业务历史、journal 和日志目前保留证据、不自动删除，磁盘占用随运行增长。
  自动清理必须保护事件 evidence_refs 和待发快照；本批未引入可能破坏证据的清理策略。
- 长时墙钟 soak、检查点/日志保留策略和容量上线限额仍为 P1，不能发布为无人值守服务。
- B 的统一指标、独立标签/trial、模型卡交接尚需对应工件，不以当前运行页替代。
- IoTDA 真实回执、断网补传、云应用、CodeArts、报告/视频/PPT 仍需后续独立验收。
  simulation 可用于真实云试验，但不得生成假的云回执代替接入。
- 这些证据均为开发者自检，独立评审与 G0 会签不由测试结果代替。

本记录完成本地软件增量与可复现证据的整理，不宣称全部 C 项目或竞赛最终交付完成。

最终验证：完整 C-business/SP-06/contracts/smoke 回归 **285 passed / 218.67s**，
退出 0（audit/c-local-closeout-final.xml）；随后新增的导出保护测试单独执行
**2 passed / 0.38s**（audit/c-export-final.xml）。两次范围不同，保留原始计数，
不把它们写成同一次全量 287 项。导出工具成功复验且证据包 19 个 SHA256 全部通过。
`git diff --check` 通过。证据包仅本地保留，不推送 SQLite/截图归档和工具目录。
