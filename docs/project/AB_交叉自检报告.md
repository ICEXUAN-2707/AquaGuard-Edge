# A/B 分支对接与交叉自检

后续复核见 [第二轮交叉核对](AB_第二轮交叉核对.md)：206项联合测试通过，补齐内容一致性及结构化失败报告。

日期2026-10-30。prototype_only；本次为同一执行代理交叉检查，不代替独立Reviewer或合同会签。

## 分支状态

执行git fetch origin后确认：当前分支spike/b-m3-m4-m5-validation，HEAD与origin同名分支ahead/behind为0/0。A工作尚在当前工作区，未commit/push；保留既有B/C和文档改动，未切换、重置或强行合并。

## 对齐结果与修复

1. 候选DTO 1.1与A的完整导出可进入B replay；异常/重复日志不是回放输入，必须先通过A持久去重并导出。
2. A仅支持RECEIVED_FALLBACK，B Stream禁止这类消息直接切换boot。保留B保护逻辑；新增A的handoff_b.py将每个device/boot明确作为独立有限实验交接，而非冒充连续重启时间线。
3. 相同窗尾不同boot可能产生相同B window_id；增加sidecar experiment_id划分实验作用域。消费者必须用(experiment_id,window_id)引用，不私改正式窗口DTO。
4. 真正交接A的100条MQTT日志发现：突发发布却声明每次flow区间1000ms，导致区间重叠。B正确拒绝，未删去检查或篡改原日志。该批仅为通信证据，不能作特征黄金值。
5. A CLI增加--interval发送间隔；新做6条三源真实MQTT节奏实验（每条0.5秒，同源流量间隔约1.5秒），收发集合一致，B窗口与M4特征计算PASS。间隔只是模拟实验参数，不是设备采样结论；更复杂抖动仍按B输入检查拒绝。
6. handoff输出显式PASS/PARTIAL和BLOCKED原因，特征不兼容时非零退出并保存窗口证据；不静默修正历史。

## 实际检查

- A单元、B SP-03/M4/M5、契约及启动测试：200 passed in 11.05s。
- spikes/SP-02/evidence/ab-handoff-20261030.json：历史100条，PARTIAL，flow区间重叠；此非零退出为预期，不算整体通过。
- spikes/SP-02/evidence/ab-paced-20261030/summary.json：6条收发PASS。
- spikes/SP-02/evidence/ab-paced-20261030/b-handoff.json：B窗口及M4特征PASS，source/origin保留simulation，质量保留RECEIVED_FALLBACK。

复现B交接：

```powershell
.\.venv-app\Scripts\python.exe spikes/SP-02/src/handoff_b.py spikes/SP-02/evidence/ab-paced-20261030/accepted.jsonl --output spikes/SP-02/evidence/review-b-handoff.json
```

M5本轮运行既有回归，未声称真实MQTT数据已完成M5端到端推断；M4输出仍为原型特征，不能冒充带检查点的正式FeatureWindow。硬件时钟、真实flow区间端点及跨boot连续流语义仍待手册/实测和A/B评审。

## 后续边界

交接已在当前B分支工作区落实，尚未提交远端；未把未经会签语义写入reference或生产合同。独立评审时重点复核fallback重启隔离、实验命名空间与flow区间语义，再决定正式流式适配方案。
