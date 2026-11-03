# A 组员任务单

最新阅读入口见 [A文档导航](A_文档导航.md)；硬件已购入后的执行规划见 [零基础实验手册](A_零基础实验与数据采集手册.md)。参数未核验前不执行实物接线。

采购清单、资料入口、开发阶段与验收矩阵见 [A 双线开发计划](A_双线开发计划.md)。该计划为待执行路线，实验状态以实际证据为准。

## 你负责什么

你负责 SP-01 和 SP-02，回答两个问题：三种传感器的数据能不能稳定采到；消息经过 MQTT、进程重启和乱序后，能不能判断数据来自哪个设备、何时产生、是否重复。

**SP-02 可以现在开始；SP-01 在实物和安全参数确认后开始。** 如果组内有足够时间，两项可以并行。SP-02 不需要实物硬件，可以先用模拟消息熟悉流程。SP-01 只有在确认板卡和传感器型号、供电与电平后才能接线实测。

## 开始前先做

1. 请组长给你分配 SP-01 和 SP-02 的 Issue、分支及 Reviewer。Owner 不能自己验收自己的结果。
2. 查看 [Spike Issue 模板](templates/SPIKE_ISSUE_TEMPLATE.md) 和 [Spike 报告模板](templates/SPIKE_REPORT_TEMPLATE.md)，每项工作都单独建目录：`spikes/SP-01/`、`spikes/SP-02/`。
3. 如果 Python 环境尚未准备好，在仓库根目录执行：

   ```powershell
   python -m venv .venv-app
   .\.venv-app\Scripts\python.exe -m pip install -r requirements-app.lock.txt
   ```

4. 在 README 里写清你的操作系统、Python 版本、Mosquitto 版本、固件工具版本；每条命令和运行结果都复制到 `evidence/`。Broker 地址或安装方式不清楚时先问组长，不要把 Broker 暴露到公网。
5. 当前参考基线是 [V1.2 候选规范](../../reference/reference_02/00_Contracts_V1.2_修订候选.md)，但 A/B/C 尚未完成 C0 会签。可据此检查字段映射，不改 `reference/`、`edge/contracts/`、生产 API 或业务数据库。
6. 把实验标记 `prototype_only` 写在文件名、README、报告或 sidecar 中，不要把该字段塞进正式 DTO JSON 对象，否则会因额外字段校验失败。

## 先记住这些词

- `device_id`：哪台设备发来的数据。
- `boot_id`：设备每次重启后的一轮启动编号，用来区分“重启后序号从头开始”和“旧消息重复”。
- `seq`：同一轮启动里递增的消息序号。
- `uptime_ms`：设备本轮开机后经过的毫秒数，不是日历时间。
- `event_time` 是设备认为测量发生的时间；`received_at` 是电脑或边缘程序收到消息的时间。两者不能混成一个字段。
- 重复消息：同一设备、同一轮启动、同一传感器的同一个序号又收到一次。

## SP-02：先验证 MQTT、时间和重启

### 目标

不用传感器，先验证最小消息管道：发布一条 JSON，订阅端能收到；重复、乱序、断连和重启后日志能说明发生了什么。

### 按步骤完成

1. 安装或启动一个本机 Mosquitto Broker；记录版本和启动命令。若组内已有 Broker，先找组长要连接地址，不能把账号密码写进 Git。
2. 先看 [V1.2 候选规范 D1](../../reference/reference_02/00_Contracts_V1.2_修订候选.md)。如果用候选 DTO 外形，公共字段包括 `schema_version=1.1`、`observation_id`、`device_id`、`sensor_type`、`boot_id`、`seq`、`uptime_ms`、`event_time`、`received_at`、`time_basis`、`value`、`quality`、`source`。时间写带时区的 ISO 格式；模拟数据用 `source=simulation`，没有可信设备时钟时用 `time_basis=RECEIVED_FALLBACK` 且 `event_time=null`。
3. `value` 按传感器类型填写：flow 用 `pulse_count`、`interval_ms`、`estimated_lpm`、`calibration_id`；water 用 `wet`；presence 用 `present`、`moving`、`still`。未知用 `null`，不能猜成 false。实验文件或 README 标 `prototype_only`；不要把标记字段加进 DTO 对象。
4. 先连续发送 100 条消息，订阅端保存一份原始 JSONL 日志；统计发出数、收到数、重复数和时间差。
5. 再分别注入重复 seq、乱序 seq、Broker 暂停/恢复，以及发布程序重启。重启后更换 `boot_id` 并重置 seq，验证日志能区分“新一轮启动”和“同一轮重复消息”。
6. 写测试或检查脚本，对上述日志自动统计；不能只凭终端“看起来正常”写 PASS。

### 完成交付

- `README.md`：一条一条写清安装、启动 Broker、启动订阅者、发布消息、停止的方法。
- `src/`、`tests/`：最小发布/订阅程序和可重复检查。
- `data/`：模拟输入；`evidence/`：100 条原始记录、断连和重启日志。
- `REPORT.md`：各场景发出/收到/重复统计、失败现象、结论和遗留问题。

建议本地验收命令：`python -m pytest spikes/SP-02/tests -q`。若测试尚未编写或命令不能运行，报告应写 PARTIAL/FAIL，不能写 PASS。

### A 交给 B 的结果

另写一段 `TIME_ASSUMPTIONS.md`：说明设备时间、接收时间、uptime、boot_id 和 seq 哪些可靠，哪些只是模拟。给 B 2–3 份完整消息例子，至少包含乱序、重复和重启。B 在窗口实验中可以使用这些文件，但不能把模拟时钟说成真实硬件精度。

## SP-01：硬件采集与校准（有实物后）

### 目标

验证 YF-S201 水流、FC-37 水接触、LD2410C 人体存在的原始读数和掉线表现，并记录 ESP32/固件方案是否支持所需字段。

### 按步骤完成

1. 先拍摄并记录板卡、传感器的准确型号/版本；查数据手册中的供电、电平、引脚和接线要求。让有经验的人复核后再上电。
2. 只做低压、隔离的桌面台架测试；不要接真实管网、不要改家用电源、不要短接未知引脚。型号或电平无法确认就先标记 BLOCKED。
3. 水流传感器用量杯/已知体积重复测量至少 5 次，保存脉冲数、测量时长、估计流量和计算系数。
4. 水浸传感器做干/湿切换至少 10 次，记录原始值、触发时间、恢复时间和抖动。
5. 人体传感器分别测试有人静止、有人移动、无人和拔线。特别记录静止目标能否检测；拔线不能被记成“无人”。
6. 重启设备，确认新 `boot_id`、seq 行为和时间字段；所有数据带时间和设备型号。

### 完成交付

- `hardware_notes.md`：型号、接线图/照片、供电与电平来源、工具链版本、危险项和复核人。
- `data/calibration.csv`：至少 5 次水流标定及重复干湿/人体场景读数。
- `evidence/`：原始串口日志和测试过程照片；隐去 Wi-Fi 密码、设备密钥和个人信息。
- `REPORT.md`：固件路线比较、可用字段、检测失效和证据限制。

若没拿到硬件，仍可完成 SP-02；SP-01 如实标记 BLOCKED，并列出需要的板卡/传感器型号与数量。不要用网上视频或模拟数据代替实物 PASS。

## 每天给组长的三句话

1. 今天新增了哪份可检查的日志/文件？
2. 当前卡在什么具体步骤？
3. 需要谁提供哪一项设备、地址、说明或评审？
