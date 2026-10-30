# SP-02 · MQTT / 时间 / 重启 最小管道验证

> Owner：A ｜ 状态：**PARTIAL**（技术验证 5/5 通过；Broker 未使用 Mosquitto，见下）
> 依据：`docs/spikes/A_任务单.md` 的 SP-02 部分、`reference/reference_02/00_Contracts_V1.2_修订候选.md` 的 D1

---

## 一句话结论

**用模拟观测（`source=simulation` / `time_basis=RECEIVED_FALLBACK`）跑通了 100 条消息的发布-订阅链路，
并且用可重复的脚本把"重复、乱序、断连、发布端重启"四种情况都进了日志、都能被自动统计出来。**

**唯一没满足的是 Broker 型号**：任务单要求 Mosquitto，本机用 **aedes（Node）** 代替，
原因是这台机器**没有管理员权限**，装不了 Mosquitto 官方安装包。详见"限制"一节。

---

## 环境（证据：`evidence/env_versions.txt`）

| 项 | 值 |
|---|---|
| 系统 | Microsoft Windows 11 家庭版 中文版 |
| Python | 3.15.2 |
| paho-mqtt | 2.1.0 |
| Node.js | 见 `evidence/env_versions.txt` |
| **Broker** | **aedes 0.51.3（通过 `node broker.js` 启动，端口 18830）—— 不是 Mosquitto** |
| 主题 | `aquaguard/<device_id>/observation`、`aquaguard/<device_id>/status`（假设 A-01，待确认） |

---

## 目录

```
spikes/SP-02/
├─ README.md                  ← 本文件
├─ REPORT.md                  ← 结果与统计（含 PASS/PARTIAL 判定）
├─ TIME_ASSUMPTIONS.md        ← 给 B：哪些时间可信、哪些是模拟
├─ data/simulation_plan.json  ← 5 个场景的定义与预期
├─ src/
│   ├─ observation.py         ← V1.2 观测构造 + D1 校验（严格，多一个字段就报错）
│   ├─ publisher.py           ← 发布端（4 种故障注入）
│   ├─ subscriber.py          ← 订阅端（原样落 JSONL 当证据）
│   └─ stats.py               ← 统计（缺失/重复/乱序/延迟/boot 分段）
├─ tests/                     ← pytest，18 项
├─ tools/run_all.ps1          ← 一键跑完 5 个场景并出统计
└─ evidence/                  ← 原始日志、统计 JSON、环境版本
```

---

## 怎么跑

### 0) 装依赖

```powershell
cd <仓库根目录>
python -m venv .venv-app
.\.venv-app\Scripts\python.exe -m pip install -r requirements-app.lock.txt
# 若锁文件里没有 paho-mqtt / pytest，单独补：
.\.venv-app\Scripts\python.exe -m pip install paho-mqtt pytest
```

### 1) 起 Broker（二选一）

**A. 本机 aedes（本项目实际使用的方案，无需管理员）**
```powershell
cd <仓库根目录>\..\工具\broker     # 或任意含 broker.js 的目录
$env:MQTT_PORT=18830
node broker.js
```

**B. Mosquitto（任务单期望的方案，需要管理员权限）**
```powershell
# 安装后：
mosquitto -p 18830 -v
# 记下：mosquitto -h 输出的版本号，填进 evidence/env_versions.txt
```

### 2) 订阅端（另开窗口）

```powershell
cd spikes\SP-02\src
.\.venv-app\Scripts\python.exe subscriber.py --port 18830 --out ..\evidence\raw_manual.jsonl --duration 20
```

### 3) 发布端（再开一个窗口）

```powershell
cd spikes\SP-02\src
# 基线 100 条
.\.venv-app\Scripts\python.exe publisher.py --port 18830 --count 100 --rate 20 --out ..\evidence\sent_manual.jsonl
# 重复注入
.\.venv-app\Scripts\python.exe publisher.py --port 18830 --count 100 --rate 20 --fault dup --out ..\evidence\sent_manual_dup.jsonl
# 乱序注入
.\.venv-app\Scripts\python.exe publisher.py --port 18830 --count 100 --rate 20 --fault shuffle --out ..\evidence\sent_manual_shuffle.jsonl
# 发布端重启注入（换 boot_id、seq 归零）
.\.venv-app\Scripts\python.exe publisher.py --port 18830 --count 100 --rate 20 --fault restart --out ..\evidence\sent_manual_restart.jsonl
```

### 4) 统计

```powershell
cd spikes\SP-02\src
.\.venv-app\Scripts\python.exe stats.py --sent ..\evidence\sent_manual.jsonl --received ..\evidence\raw_manual.jsonl --json-out ..\evidence\stats_manual.json
```

### 5) 一键全跑（含 Broker 暂停/恢复场景）

```powershell
cd spikes\SP-02
powershell -ExecutionPolicy Bypass -File tools\run_all.ps1
# 若你已把 Mosquitto 起在 18830：
powershell -ExecutionPolicy Bypass -File tools\run_all.ps1 -ExternalBroker
```

### 6) 自测

```powershell
.\.venv-app\Scripts\python.exe -m pytest spikes/SP-02/tests -q
```

> 本次实测：**18 passed**。

### 怎么停

- 订阅端/发布端：`Ctrl+C`
- Broker：`Ctrl+C`（aedes）或 `Ctrl+C`（mosquitto）
- 一键脚本会自己在 `finally` 里停掉 Broker

---

## 5 个场景与注入方式

| # | 场景 | 命令要点 | 期望 |
|---|---|---|---|
| 1 | 基线 | `--fault none --count 100` | 发=收、无重复、无乱序 |
| 2 | 重复 | `--fault dup`（末尾原样重发 5 条） | 能数出 5 条重复，且不误判为新数据 |
| 3 | 乱序 | `--fault shuffle --shuffle-window 10` | 统计能数出乱序次数 |
| 4 | 重启 | `--fault restart`（发一半断开、换 boot_id、seq 归零） | 出现两段 boot，第二段 seq 从 1 开始 |
| 5 | Broker 暂停/恢复 | 脚本中途 kill 掉 Broker 3 秒再拉起 | 发布端不崩，缓冲后补发，最终零丢失 |

---

## 关键假设（需要组长/契约线确认）

| ID | 假设 | 影响 |
|---|---|---|
| A-01 | 主题为 `aquaguard/<device_id>/observation`，状态走 `.../status` | 换前缀只改 `--topic-prefix` 和订阅通配符 |
| A-02 | 同一 `boot_id` 内，三个传感器**共用**一条递增 `seq` | 若要每 sensor_type 独立 seq，需改 publisher 计数 |
| A-03 | `time_basis` 只用 `RECEIVED_FALLBACK`（`event_time=null`） | 另两个时间基准枚举名待确认，确认后才能用真实设备时钟 |

---

## 限制（必须在报告里如实写，不许含糊）

1. **Broker 不是 Mosquitto**：aedes 0.51.3。原因：本机无管理员权限。→ 这一项判 **PARTIAL**。
2. `source` 全部为 `simulation`，**不能声称代表真实硬件精度**。
3. 时钟未做 NTP 同步实验；`event_time=null`，全部走 `RECEIVED_FALLBACK`。
4. 场景 4 的"重启"是**发布进程重启**，不是 ESP32 断电重启；硬件复位行为要等 SP-01。
5. 未测 TLS / 认证 / 公网 Broker（任务单明确要求不要把 Broker 暴露公网）。
