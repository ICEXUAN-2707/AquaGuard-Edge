# SP-03｜第 0—1 轮：口径与回放基础

状态：PARTIAL。2026-10-29。synthetic / prototype_only。
本轮回放基础验证 PASS；完整 SP-03 尚未完成，Reviewer 待指定。

## 为什么先做回放
传感器型号尚未确定。先使用候选 SensorObservation DTO 和模拟数据固定软件入口，后续硬件只通过适配层替换输入。回放根据 received_at 推进虚拟时间，不依赖真实等待，不连接 MQTT、云服务或硬件。

## 运行
在仓库根目录执行，使用已有应用环境（审计环境 .venv 不含 Pydantic）：

```powershell
.\.venv-app\Scripts\python.exe -m pytest spikes/SP-03/tests -q -p no:cacheprovider
.\.venv-app\Scripts\python.exe spikes/SP-03/src/replay.py spikes/SP-03/data/synthetic.jsonl --output spikes/SP-03/evidence/replay.jsonl
```

数据说明和人工预期在 data/；实际结果和测试日志在 evidence/。
所有模拟标记放在本说明中，未向正式 DTO 塞入额外字段。

## 本轮口径
- 候选 DTO schema_version=1.1；不表示契约已经三方会签。
- 先统一验证全部输入，再按 received_at、observation_id 排序；相同时间按 ID 字典序处理。
- virtual_time 为接收时间；effective_time 为非空事件时间，否则为接收时间，并标记 degraded_time。包装字段属于原型输出，不是新业务 DTO。
- 原始 event_time=null 和 presence.present=null 保持不变。
- 本轮重复 observation_id 明确报错；下一轮设计幂等去重和冲突审计。
- DEVICE_SYNCED 仅是合成输入声明，本程序不证明设备时钟可信。
- 本轮为有限文件离线回放，一次性加载和排序；不是持续运行服务，没有生产缓存上限保证。

## 下一轮需补齐的设计
1. 窗口 (t-W,t]，W30/S5/L2 仅为实验配置；明确锚点和截止时刻消息优先级。
2. 固定截止关闭窗口；沉默仍发布；晚到按目标窗口判断，已发布窗口不可静默回改。
3. 按源配置 TTL；未知不补零；过期不续计；保留窗前仍有效状态。
4. 确认 flow 时间戳对应 interval_ms 的哪个端点；序号是设备级还是源级。
5. boot 变化、时间映射、异常未来时间、身份冲突和有界缓存。
6. M4 通过何种内部接口读取不可变观测或有效时间段；不擅自增加正式 DTO 字段。

## 暂定分轮路线
R02 时间对齐与质量治理 → R03 十二特征 → R04 跨窗记忆与恢复 → R05 规则拒判及本地联调 → R06 实物适配和参数验证 → R07 独立 trial 与 ML 对比。
每轮保存代码、人工预期、真实输出、REPORT；上一轮退出条件通过后再推进。原型参数调整需记录配置版本。正式集成遵循现有契约会签要求。

## 第 2 轮新增入口
[第 2 轮报告与自查记录](REPORT_R02.md)。实现有限文件对齐原型；完整 SP-03 仍为 PARTIAL，下一小轮先补重启隔离、分源 TTL 和流式有界缓存。

## 第 3 轮入口
[第三轮开发报告](REPORT_R03.md)。Stream 使用显式 advance 推进时钟；同时间戳先输入全部消息再推进。重启采用清空旧读数的保守策略。完整限制、测试及后续工作见报告。

## 第 4 轮入口
[第四轮报告](REPORT_R04.md)；人工黄金预期 data/r04_golden.json；回归证据 evidence/r04_tests.txt。

## 第 5 轮修复
[整改简报](REPORT_R05.md)。advance 每次默认最多 100 个窗口；next_end 为继续追赶位置。若 push 报 catch-up，先重复 advance(消息接收时间, inclusive=False) 到 next_end+lateness 不再严格早于接收时间，再重试 push。处理同时间戳全部消息后才能 inclusive=True 发布。

## 第 6 轮
三源综合输入 data/r06_three_source.json，实际输出 evidence/r06_windows.json；详见 REPORT_R06.md 与 DECISION_TABLE.md。
