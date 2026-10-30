# TIME_ASSUMPTIONS · 给 B 的时间语义说明

> 出自 SP-02（A 角色）。目的：告诉你**哪些时间可信、哪些只是模拟**，以及你处理窗口/迟到数据时该信什么。
> ⚠️ 全文前提：本次数据 `source = simulation`、`time_basis = RECEIVED_FALLBACK`、`event_time = null`。
> **不能拿这份数据声称"真实硬件时钟精度"。**

---

## 一、一句话结论

**目前唯一可信的时间是 `received_at`（边缘/订阅端收到消息的时刻）；`event_time` 一律为 `null`，`uptime_ms` 只是发布进程内部的相对时间。**

---

## 二、字段可信度表

| 字段 | 本次可信吗 | 说明 |
|---|---|---|
| `received_at` | ✅ 可信 | 订阅端本机时钟（+08:00），毫秒精度；它是"电脑收到的时刻"，不是"传感器测到的时刻" |
| `event_time` | ❌ 全为 `null` | 模拟数据没有可信设备时钟，按 D1 必须置 null；**不要据此判断采样时刻** |
| `time_basis` | ✅ 可信 | 全部 `RECEIVED_FALLBACK`，即"没有可信设备时钟，只能用接收时间兜底" |
| `uptime_ms` | ⚠️ 相对可信 | 发布进程启动后的毫秒数；进程重启就会归零，跨重启不可比 |
| `boot_id` | ✅ 可信 | 每次"启动"换一个新值；本次场景 4 里 `8fd2 → 9c31` |
| `seq` | ✅ 可信（有前提） | 同一 `boot_id` 内递增；**当前按假设 A-02 是全局递增，三个 sensor_type 共用一条序列** |
| `observation_id` | ✅ 可信 | 每条唯一，重复投递时不变 |
| `quality` / `value` | ✅ 可信（模拟值） | 字段语义正确，但**数值是造的**，不代表真实传感器 |

---

## 三、三条判据（你写对齐算法时直接用）

### 1) 判重
D1 定义：**同一 device_id + 同一 boot_id + 同一 sensor_type + 同一 seq** 再次收到 = 重复。
实测：注入 5 条重复，统计准确识别 `duplicate_by_d1_key = 5`，且不产生"多余的新数据"。

### 2) 判先后
用 `(boot_id, seq)` 判先后，**不要用 `received_at` 判先后**（网络乱序会让接收时间颠倒）。
实测乱序：收到的前 12 条到达顺序是 `7, 1, 3, 8, 5, 6, 2, 9, 10, 4, 12, 20` —— 完全不是产生顺序。
如果你按 `received_at` 排序，窗口就会错。

### 3) 判"重启"还是"重复"
`seq` 从 1 重新开始 **不等于** 重复。先看 `boot_id`：
- `boot_id` 变了 → 新一轮启动，seq 归零是正常的
- `boot_id` 相同且 seq 相同 → 才是重复

实测场景 4：两个 boot 段各 50 条、seq 都是 1–50，但 `duplicate_by_d1_key = 0`，证明这条判据成立。

---

## 四、真实报文样例（原样取自 `evidence/`）

### 样例 1 · 正常一条（flow）

```json
{"schema_version":"1.1","observation_id":"ed69d0eb-8620-4438-93e2-bb7a1e0dd3b7","device_id":"A001","sensor_type":"flow","boot_id":"a509","seq":1,"uptime_ms":1,"event_time":null,"received_at":"2026-10-30T12:38:27.838+08:00","time_basis":"RECEIVED_FALLBACK","value":{"pulse_count":12,"interval_ms":1000,"estimated_lpm":1.2,"calibration_id":"SIM-CAL-0"},"quality":"valid","source":"simulation"}
```

### 样例 2 · 乱序（同一窗口内的到达顺序 ≠ 产生顺序）

到达顺序（`raw_shuffle.jsonl` 前 10 条）：

```
12:38:54.594  seq=7  flow
12:38:54.595  seq=1  flow
12:38:54.596  seq=3  presence
12:38:54.597  seq=8  water
12:38:54.597  seq=5  water
12:38:54.598  seq=6  presence
12:38:54.599  seq=2  water
12:38:54.599  seq=9  presence
12:38:54.600  seq=10 flow
12:38:54.601  seq=4  flow
```

→ 若你的窗口依赖"按到达顺序累积"，前 10 条会得到 `7,1,3,8,5,6,2,9,10,4` 这种序列。
→ 正确做法：先按 `(boot_id, seq)` 归位，再按窗口切分。

### 样例 3 · 重复（同一 `observation_id` 收到两次）

```
observation_id = bf701b33-8e56-44d0-811a-a096975039af
seq = 4 , sensor_type = flow , boot_id = f981
第 1 次收到 12:38:41.022
第 2 次收到 12:38:46.080      ← 同一 observation_id、同一 seq
```

### 样例 4 · 重启（两个 boot 段，seq 各自从 1 开始）

```
boot_id = 8fd2  →  {"seq":1,...,"sensor_type":"flow",...}     received_at 12:39:07.144
boot_id = 9c31  →  {"seq":1,...,"sensor_type":"presence",...} received_at 12:39:11.744
```

注意第二条是 `presence` 而第一条是 `flow` —— 这正说明 **seq 是全局递增的**（假设 A-02），
**不是每个传感器各自一条序列**。若契约线最终要求每 sensor_type 独立 seq，我会重跑并通知你。

---

## 五、给 B 的 4 条建议

1. **窗口对齐**：以 `received_at` 做窗口边界（现在是唯一可用时间），以 `(boot_id, seq)` 做窗口内容的归位与去重。
2. **迟到数据**：`seq` 小于窗口内已发布最大 `seq` 的，视为迟到；建议进旁路审计，**不要静默改写已发布窗口**（D2 也是这么要求的）。
3. **缺失判定**：先看有没有心跳/status，再谈"沉默"。本次没定义 status payload，属于遗留问题（见 REPORT 第六节）。
4. **别把 `uptime_ms` 当绝对时间**：它只在单个 `boot_id` 内有意义。

---

## 六、一句话提醒

这份数据能证明**传输链路和判重/乱序/重启的语义是通的**；
但它**不能证明设备时钟精度**。真实 `event_time` 的可信度，要等 SP-01 硬件测出来再造数给你。
