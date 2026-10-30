# SP-02 报告 · MQTT / 时间 / 重启 最小管道

> 判定：**PARTIAL**
> 说明：**5 个技术场景全部 PASS**；但任务单要求"本机 Mosquitto Broker"，本次实际使用 **aedes 0.51.3**（本机无管理员权限装不了 Mosquitto），故整体不能判 PASS。
> 所有数字均来自 `evidence/stats_*.json` 与 `evidence/*.jsonl`，可用 `tools/run_all.ps1` 一键复现。

---

## 一、判定总表

| # | 验证项 | 判定 | 依据（证据文件） |
|---|---|---|---|
| 1 | 基线：100 条发布/订阅、无重复无乱序 | ✅ PASS | `evidence/stats_baseline.json` |
| 2 | 重复注入：能识别重复且不误判 | ✅ PASS | `evidence/stats_dup.json` |
| 3 | 乱序注入：能数出乱序 | ✅ PASS | `evidence/stats_shuffle.json` |
| 4 | 发布端重启：boot_id 变化、seq 归零、不被误判 | ✅ PASS | `evidence/stats_restart.json` |
| 5 | Broker 暂停/恢复：不崩、缓冲、零丢失 | ✅ PASS | `evidence/stats_broker_pause.json` |
| 6 | Broker 为 **Mosquitto** | ⚠️ **PARTIAL** | `evidence/env_versions.txt`：aedes 0.51.3 |
| 7 | 时间同步（NTP）与 `event_time` 可信性 | ⏸ BLOCKED | 模拟数据无法验证，等 SP-01 硬件 |

**整体：PARTIAL**（技术验证过关，Broker 型号不满足任务单）

---

## 二、统计总表（真实运行结果）

| 场景 | 发出 | 收到 | 缺失 | 重复(observation_id) | 重复(D1 键) | 乱序次数 | 延迟 中位/最大 | boot 段 |
|---|---|---|---|---|---|---|---|---|
| baseline | 100 | 100 | 0 | 0 | 0 | 0 | 1.0 / 1.0 ms | 1 段（seq 1–100） |
| dup | 105（100+5 注入） | 105 | 0 | **5** | **5** | 1 | 0.0 / 5059.0 ms | 1 段 |
| shuffle | 100 | 100 | 0 | 0 | 0 | **42** | 4.0 / 8.0 ms | 1 段（首条 seq=7） |
| restart | 100 | 100 | 0 | 0 | 0 | 0 | 0.0 / 1.0 ms | **2 段，各 50 条，seq 都从 1 开始** |
| broker_pause | 60（其中 **25 条缓冲**） | 60 | 0 | 0 | 0 | 0 | 1.0 / 19.0 ms | 1 段 |

所有场景 `parse_errors = 0`、`non_observation_messages = 0`。

---

## 三、逐场景分析

### 场景 1 · 基线（PASS）
- **命令**：`publisher.py --count 100 --rate 20`，订阅端 `--duration 12`
- **结果**：发 100 / 收 100，缺失 0，重复 0，乱序 0，延迟 0–1 ms，单一 boot 段 `a509`（seq 1–100）
- **结论**：最小管道成立，主题、QoS 1、JSON 序列化都没有问题。

### 场景 2 · 重复注入（PASS）
- **注入方式**：100 条发完后，把前 5 条**原样重发**（`observation_id`、`seq`、`boot_id` 全同）
- **结果**：发 105 / 收 105；`duplicate_by_observation_id = 5`，`duplicate_excess_messages = 5`，`duplicate_by_d1_key = 5`
- **证据**：重复对示例（`evidence/raw_dup.jsonl`）
  - `observation_id = bf701b33-8e56-44d0-811a-a096975039af`，`seq = 4`，`sensor_type = flow`
  - 第 1 次收到：`12:38:41.022`
  - 第 2 次收到：`12:38:46.080`
- **结论**：`observation_id` 与 D1 三元组（device_id + boot_id + sensor_type + seq）都能把重复识别出来。
- **观察**：这批重复消息里最大延迟 5059 ms —— 原因是注入发生在发布端断开前，QoS 1 重传导致；**不是链路抖动**，已在统计里单独体现。

### 场景 3 · 乱序注入（PASS）
- **注入方式**：每 10 条一个窗口，窗口内打乱顺序再发
- **结果**：发 100 / 收 100；`order_inversions = 42`；**收到的第一条是 seq=7**（正常应为 1）
- **结论**：日志能忠实反映"到达顺序 ≠ 产生顺序"，B 的窗口对齐可以据此判断迟到数据。

### 场景 4 · 发布端重启（PASS，最关键的一项）
- **注入方式**：发到第 50 条时断开、换新 `boot_id`、`seq` 归零，继续发 50 条
- **结果**：收 100 条，分成 **两个 boot 段**：
  - `8fd2`：50 条，seq 1–50
  - `9c31`：50 条，seq 1–50
- **同时**：`duplicate_by_d1_key = 0` —— **重启后 seq 归零没有被误判成"同一轮的重复消息"**
- **结论**：`boot_id` 的设计目的被验证：它能把"新一轮启动"和"旧消息重复"区分开。这是任务单要求 A 交给 B 的核心结论之一。

### 场景 5 · Broker 暂停/恢复（PASS）
- **注入方式**：发布中（5 条/秒）杀掉 Broker 3 秒，再拉起
- **结果**：发 60（其中 **25 条走本地缓冲** `buffered=true`）/ 收 60 / **缺失 0**；延迟 0–19 ms
- **结论**：发布端在断连时不死、消息进缓冲、重连后补发成功，没有丢消息。
- **注意**：本次 Broker 是**内存态 aedes**，进程被杀后订阅关系与保留消息都重置；生产上若用持久化配置，行为需重测。

---

## 四、失败现象与坑（如实记录）

| 现象 | 原因 | 处理 |
|---|---|---|
| 第一版跑出 `sent=200` | publisher 的 `batch` 在非乱序模式下没清空，每条发了两遍 | 改成分支内清空，重跑后 100/100 |
| 第一版统计报 `KeyError: observation_id` | 订阅通配符 `aquaguard/+/#` 把 `status` 心跳也收进来了 | 订阅默认改成 `aquaguard/+/observation`；stats 增加防御性过滤 |
| 第一版 Broker 日志只有"上线"没有消息 | paho `connect()` 后没调 `loop_start()`，publish 只进队列不发 | 加 `loop_start()` |

> 这三条都是**真实踩过的**，写进来是为了后面的人不再踩；不是"设计如此"。

---

## 五、限制（不能拿模拟冒充真实）

1. `source` 全为 `simulation`；`time_basis` 全为 `RECEIVED_FALLBACK`、`event_time = null`。
2. **没有验证设备时钟精度**：NTP 同步、时钟漂移、`event_time` 与 `received_at` 的差值分布，都要等 SP-01 的真实硬件。
3. 场景 4 是**进程重启**，不是 ESP32 断电/看门狗复位；硬件复位后 `boot_id` 与 `seq` 的真实行为要 SP-01 验证。
4. Broker 非 Mosquitto（PARTIAL 的直接原因）；未验证 Mosquitto 的持久化会话、`retain` 重启行为。
5. 未做认证/TLS/公网暴露测试（任务单明确禁止把 Broker 暴露公网）。

---

## 六、遗留问题（交给谁）

| # | 问题 | 交给 |
|---|---|---|
| 1 | 主题命名 `aquaguard/<device_id>/observation` 是否正式采用？ | 组长 / 契约线（假设 A-01） |
| 2 | `seq` 是全局递增还是每个 sensor_type 独立递增？ | 契约线（假设 A-02） |
| 3 | `time_basis` 另两个枚举值叫什么？ | 契约线（假设 A-03） |
| 4 | status 通道的 payload 是否也需要 schema？（本次未定义） | 契约线 |
| 5 | Mosquitto 环境搭建（需要管理员或组长提供已部署 Broker 地址） | 组长 |

---

## 七、下一步

1. 把本目录提交到 `spike/sp-02-mqtt-time` 分支，走 PR 并指定 Reviewer（Owner 不能自验）。
2. 拿到 Mosquitto（或组长给的 Broker 地址）后**只需重跑 `run_all.ps1 -ExternalBroker`**，把 Broker 一栏从 PARTIAL 转 PASS。
3. 硬件到货后进入 SP-01，把 `source` 换成 `hardware`、补真实 `event_time`，并复用本目录的 `stats.py` 做校准数据统计。
