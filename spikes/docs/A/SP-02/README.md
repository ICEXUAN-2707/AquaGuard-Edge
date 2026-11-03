# SP-02 prototype_only

A/B分支对接、真实数据交叉检查与修复见 [交叉自检报告](../../../../docs/project/AB_交叉自检报告.md)。`handoff_b.py`接受唯一完整DTO JSONL，按设备/boot分成独立实验，不代表连续重启流。突发通信基线的1000ms流量区间重叠，不可直接当特征输入；模拟特征实验可使用`publish --interval 0.5`三源轮发并检查实际区间，不能据此推断硬件参数。

本轮收尾入口见 [软件阶段收尾报告](../A_软件阶段收尾报告.md)，含统一复现命令、证据与B交接材料。整体仍待独立评审及软硬件联调，不是生产部署版本。

订阅端现使用manual_ack：合法观测或非法报文隔离记录提交SQLite后才确认。存储失败不确认并断开连接。需要跨订阅进程重投时使用`--persistent-session`（稳定client_id），并保持Broker会话；默认clean_session模式不能保证此行为。

确认前崩溃验证（新目录）：

```powershell
.\.venv-app\Scripts\python.exe spikes/SP-02/src/verify_crash.py --broker 'C:\Program Files\mosquitto\mosquitto.exe' --directory spikes/SP-02/evidence/new-crash-run
```

`--crash-after-commit`为实验故障注入，会直接以73退出，仅用于隔离验证。当前Broker persistence=false，Broker进程同时崩溃会丢失内存会话；本测试不证明此情形无损。SQLite为处理事实依据，received.jsonl为辅助日志，崩溃可导致JSONL缺少首次处理记录。

最新能力与待办见 [A软件验证进度](../A_软件验证进度.md)。

持久化发送队列（先generate准备manifest；接收端READY后flush）：

```powershell
.\.venv-app\Scripts\python.exe spikes/SP-02/src/send_queue.py enqueue --directory spikes/SP-02/data/run01
.\.venv-app\Scripts\python.exe spikes/SP-02/src/send_queue.py status --directory spikes/SP-02/data/run01
.\.venv-app\Scripts\python.exe spikes/SP-02/src/send_queue.py flush --directory spikes/SP-02/data/run01
```

flush连接失败会非零退出并保留待发项，可新进程重试。confirmed仅代表Broker传输确认；Broker无持久化或订阅器离线时，不能据此保证下游收到。确认后、本地标记前崩溃可能重发，依赖订阅端稳定身份去重。该工具是电脑实验实现，非ESP32固件缓存。

真实Broker重复、乱序及重启验证（目录必须尚不存在）：

```powershell
.\.venv-app\Scripts\python.exe spikes/SP-02/src/verify_mqtt.py --broker 'C:\Program Files\mosquitto\mosquitto.exe' --directory spikes/SP-02/evidence/new-restart-run
```

该命令只启动和停止自己创建的Broker/客户端，使用独立回环端口18884；验证重复/乱序、冲突/非法输入隔离、客户端进程重启、Broker重启后重新连接、持续运行订阅器自动重连。不会验证离线补发。

CLI在subscribe-connections.jsonl记录UTC和单调时钟连接时间线，重连后重新订阅。非法输入进入received.jsonl审计、不中断后续接收，但本轮订阅进程最终返回非零状态，避免将异常实验当作普通基线通过。

部署及硬件联调流程见 [软硬件结合开发手册](../A_软硬件结合开发手册.md)。2026-10-30已完成真实本机Broker的100条基线，详情见REPORT.md。

当前实现：三源模拟消息、严格标准化、持久化身份分类、基础本机MQTT CLI。
硬件驱动未启用，所有消息source=simulation。

从仓库根目录运行：

```powershell
.\.venv-app\Scripts\python.exe -m pytest spikes/SP-02/tests/unit -q
.\.venv-app\Scripts\python.exe spikes/SP-02/src/cli.py generate --directory spikes/SP-02/data/run01
```

真实通信需要本机Mosquitto。启动Broker后，两个终端分别运行；订阅端打印READY后再发布：

```powershell
.\.venv-app\Scripts\python.exe spikes/SP-02/src/cli.py subscribe --directory spikes/SP-02/data/run01 --seconds 30
.\.venv-app\Scripts\python.exe spikes/SP-02/src/cli.py publish --directory spikes/SP-02/data/run01
```

订阅结束后用export子命令输出accepted.jsonl供B读取。每次实验使用新目录。
Ctrl+C停止客户端；Broker只停止本次自行启动的进程。
本轮CLI为clean_session=true，不承诺离线补发；未实现持久化后手动MQTT确认，不能宣称崩溃零丢失。
Broker重启、队列/磁盘故障及自动集合统计仍待实现。不能仅以publish确认判断验收成功。
