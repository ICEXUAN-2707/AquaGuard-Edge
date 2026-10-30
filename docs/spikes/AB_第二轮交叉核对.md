# A/B 第二轮交叉核对

日期2026-10-30。同一执行代理复核，非独立Reviewer验收；未修改候选合同、B算法或硬件参数。

## 发现与修复

|问题|影响|修复与验证|
|---|---|---|
|统计只比较observation_id|同ID内容损坏可误判PASS|对比除边缘received_at外的内容，报告content_mismatches；新增回归|
|发送manifest同ID异内容未识别|错误预期被集合去重掩盖|报告manifest_conflicts并FAIL|
|未知分类可混入通过记录|统计遗漏异常类别|未知分类单列并FAIL|
|B align阶段冲突不在异常报告范围|同序列不同ID直接抛错，无结构化交接原因|对齐与特征均纳入逐实验BLOCKED范围，window为null时明确说明|
|CLI非法/重复DTO输入直接报堆栈|输出文件可能保留旧成功结果|捕获输入语义/格式错误，覆盖输出为FAIL并非零退出|

补测空输入不可PASS、多设备隔离、同时间多boot的实验命名空间、重叠flow拒绝；保留B对流量区间和fallback重启的原保护逻辑。

## 实际执行结果

执行：`.venv-app/Scripts/python.exe -m pytest spikes/SP-02/tests/unit spikes/SP-03/tests spikes/M4/tests spikes/M5/tests tests/contracts tests/smoke -q -p no:cacheprovider`。

结果：206 passed in 11.36s。

使用增强统计规则重新读取已有真实MQTT记录：

- baseline-20261030：唯一100/100，内容不匹配0、manifest冲突0、未知分类0，PASS。
- ab-paced-20261030：唯一6/6，上述异常均0，PASS。
- 重新运行handoff_b，输出spikes/SP-02/evidence/ab-round2-handoff.json，窗口和M4原型特征PASS。

本轮没有重新采集网络数据；以上为既有真实日志重算，不冒称新的Broker故障实验。第一轮100条突发flow区间重叠的限制继续成立，内容核对通过不代表可计算特征。

## 剩余边界

整体仍PARTIAL。有限实验按(device,boot)隔离，不支持把交错boot拼接成连续时间线；引用用(experiment_id,window_id)。M5本轮只有既有测试回归，不宣称MQTT到推断的端到端验收。同步时钟、真实标定及硬件仍待实物资料。独立Reviewer与A/B/C会签尚未完成，未commit/push。
