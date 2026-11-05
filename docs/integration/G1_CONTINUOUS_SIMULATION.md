# G1 持续模拟纵向集成第一批

状态：实现中；原型闭环增量，不是 G1 正式验收。分支 feat/g1-continuous-simulation。

## 本批实现

`spikes/C-business/online.py` 持续生成明确标记 simulation 的三源 DTO，复用 M3 对齐、M4 可复算检查点、M5 gate/classify、C 查询投影；water 原始观测独立进入已有 WaterService，事件/transition/Outbox 原子落库。所有数据只在本机，不连接真实云、不发送通知。

固定 demo01，120 秒循环：前 40 秒有人流水，随后人员未检出；70–100 秒探头湿。正常 30 秒窗口、5 秒发布间隔、2 秒迟到等待。首次投影约 32 秒后出现。真实调度落后时不补造历史样本；按实际接收时间保留缺口。内存观测保留 180 秒，磁盘检查点和 SQLite 尚未做长期保留治理，仅限短时受控演示。

## 启动

推荐正式入口：先构建 web，再在仓库根目录 PowerShell 执行以下配置。服务仅绑定本机；环境变量须显式设置，不自动读取 .env 文件。

```powershell
$env:AQUAGUARD_RUNTIME = 'simulation'
$env:AQUAGUARD_DEVICE_ID = 'demo01'
$env:AQUAGUARD_PORT = '8010'
$env:AQUAGUARD_DB = 'audit/g1-demo.sqlite'
$env:AQUAGUARD_C_TOKEN = [guid]::NewGuid().ToString('N')
$env:AQUAGUARD_C_CURSOR_KEY = ([guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N'))
.\.venv-app\Scripts\python.exe -m edge
```

edge/runtime.py 是迁移适配层，当前仍复用 spikes/C-business 与 B 引擎源码；整个仓库一起部署，不可只复制 edge 目录。默认 baseline 模式保留原行为。配置错误在创建数据库之前拒绝。实验页输入 demo-trial，可查询运行中的模拟 trial 及最新可复算检查点引用；尚无 C0–C3 指标，不能当作 G3 实验报告。

旧原型入口仍支持：先在 web 下执行 `npm.cmd run build`。仓库根目录 PowerShell 执行：

```powershell
$env:AQUAGUARD_C_TOKEN = [guid]::NewGuid().ToString('N')
$env:AQUAGUARD_C_CURSOR_KEY = ([guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N'))
.\.venv-app\Scripts\python.exe spikes/C-business/run.py serve --db audit/g1-demo.sqlite --simulate --port 8010
```

访问 http://127.0.0.1:8010/c.html，填入本终端生成的 token，设备 demo01。不需要 seed，首次创建空库后持续输入。使用全新独立数据库，避免与旧 seed/历史时钟证据混用。环境凭据不写入源码或文档。关闭进程停止输入；重新启动创建新模拟 boot，数据缺口保持显式。

## 验证与剩余项

自动化 `test_online.py` 用注入时间持续跑 90 秒，验证 ATTENDED_FLOW、POSSIBLE_UNATTENDED_FLOW、唯一湿事件、Outbox 和模拟来源。该测试不等于浏览器或真实墙钟时延验收。

2026-11-05 实跑：`.venv-app/Scripts/python.exe -m pytest spikes/C-business/tests tests/contracts tests/smoke -q -p no:cacheprovider --basetemp=audit/g1-regression-01`，115 passed，退出码 0。测试临时输出保留在 audit/g1-*，不属于交付源码。

第二批已接入周期风险事件：`context_events.py` 重新核验 B 检查点后，把 POSSIBLE_UNATTENDED_FLOW 写入 M6/transition/Outbox，同事务持久化最后窗口和 assessment ID，重复窗口不新增 transition，旧窗口或同时间冲突拒绝。有效有人用水/空闲转为物理 CLEARED，未知或证据过期转 UNKNOWN，均不自动关闭事件或清除 ACK。再次异常复用当前 OPEN；完整关闭/复发策略仍待后续实现。

assessment 现展示窗尾前且尚新鲜的独立 water 安全信号。信号采用原始观测身份和时间；2 秒迟到等待计入新鲜度预算。湿信号再次经过 Store.open_water 验证，与原始快路共享唯一 WATER_CONTACT OPEN 事件；历史 dry 不反向修改快路物理状态。POSSIBLE_UNATTENDED_FLOW 是另一事件类型，不能与水接触事件互相吞并。

下一批：拆除正式入口对 spikes 的迁移依赖；浏览器持续更新/ACK/409/过期/窄屏验收；完整关闭/复发与长期容量治理。Mock worker 独立运行，不表示真实云同步。

G0 三方会签、Reviewer/Owner、官方规则和资源核验仍待项目组完成。未改已锁定公共 DTO 或 wire schema；原型以软件基线准备集成，正式放行另行评审。

回滚：撤销 online.py、context_events.py、test_online.py，恢复 b_bridge.py 的可选信号参数和 run.py 中 simulate 开关/情境定时处理即可回到原行为；事件表格式未变，新增 context_state 表可保留，不自动删除历史数据。
