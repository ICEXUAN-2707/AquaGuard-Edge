# G1 本地模拟集成阶段报告

日期：2026-11-05；分支 feat/g1-continuous-simulation。范围：持续模拟、本地业务入口及 HTTP 验证。G1 状态 PARTIAL，尚未正式验收。

## 已实现

- 正式命令 `python -m edge` 支持显式 simulation 模式，凭据/设备/数据库配置预校验，保持本机绑定和原 baseline 默认行为。
- 三源持续输入、M3 对齐、M4 可复算检查点、M5 情境、独立 water 快路、M6/SQLite/Outbox 与七路由查询串联。
- 周期情境风险事件、持久窗口去重、过期 UNKNOWN；ACK 与物理状态分离；快慢水接触去重；模拟来源贯穿。
- 实验页 demo-trial 返回当前模拟运行与真实生成的检查点引用；不是虚构指标或 C0–C3 实验报告。
- 真实定时器窗尾选择实际 flow 区间端点，避免毫秒抖动引起 FLOW_UNKNOWN；采集间隙保持真实，不补造数据。

## 验证范围

自动化覆盖持续模拟、两类事件、ACK、重启复用、Outbox 原子回滚、重放去重、API 投影与来源。新增真实子进程测试通过公开入口启动，等待两个不同 captured_at 的窗口，验证情境、独立安全信号、trial、sync、events 和构建后的首页资源。

前端构建在前批通过，本批未修改前端源码。浏览器验收尝试通过 computer-use 的 node_repl 和备用 CUA 通道初始化，两者均返回 `failed to write kernel assets: 磁盘空间不足 (os error 112)`，未进行浏览器点击或窄屏检查。不得将 HTTP 测试表述为浏览器 E2E 通过。

最终联合命令 `.venv-app/Scripts/python.exe -m pytest spikes/C-business/tests tests/contracts tests/smoke -q -p no:cacheprovider --basetemp=audit/g1-final-regression-01`：**118 passed in 79.60s，退出码 0**。随后新增毫秒抖动专项单独运行 **1 passed，退出码 0**；不把不同阶段的历史数量相加。`git diff --check` 通过。完整终端输出在本轮会话，报告是结果摘要。

## 未通过项与下一步

|事项|当前结论|完成条件|
|---|---|---|
|浏览器 E2E/窄屏|环境阻断|工具可启动后实际验证三页、持续更新、ACK/409、过期与窄屏，并保存证据|
|正式模块迁移|入口就绪，模块仍依赖 spikes|分批提取 B/C 模块到 edge，保持回归与回滚路径；不能只部署 edge 文件夹|
|A MQTT 纳入同一 runtime|当前持续输入为进程内 simulation DTO|把既有 A 标准导出接到同一输入端，做 broker 中断/重连的全链验证；现状不证明 MQTT 全系统闭环|
|完整生命周期|OPEN/物理状态/ACK 已运行|补正式关闭/复发/升级规则及评审，当前不自动 CLOSED|
|长期运行|短时受控演示|检查点/SQLite 保留、容量、调度监督与故障恢复验收|
|独立放行|未完成|G0 联合签署、实际 Owner/Reviewer、G1 Reviewer 复核|

G2 真实三源台架/IoTDA/华为云应用、G3 真实 trial/轻量 ML、G4 视频/PPT/干净环境复现均未因本批软件实现而升级。不能据此宣称最终作品完成。

启动与回滚见 G1_CONTINUOUS_SIMULATION.md。所有新功能显式 simulation；未创建云资源或发送真实通知。测试输出目录 audit/g1-* 与原有未跟踪文件不属于交付提交范围。
