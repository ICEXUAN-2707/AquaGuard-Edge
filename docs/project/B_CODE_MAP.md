# B部分代码地图｜从零按数据流阅读

日期：2026-11-03。范围：当前离线模拟原型。目录SP-03对应M3，SP-03-features对应M4，SP-04对应M5；SP是实验任务编号，M是架构模块编号。本文不代表新增算法验收。

## 0. 先懂三个词
观测：传感器一次上报。窗口：取一段时间里的有效证据。特征：把证据压缩成数字/状态。规则：依据这些证据输出情境。null/unknown表示不知道，0/false表示有证据的零或否，不能混用。

## 1. 先跑再读
仓库根目录执行：
```powershell
.\.venv-app\Scripts\python.exe spikes/SP-03-features/demo.py
.\.venv-app\Scripts\python.exe spikes/SP-04/demo.py
.\.venv-app\Scripts\python.exe spikes/SP-04/evaluate.py
```
先看SP-03-features/evidence/r07_feature_windows.json的十二特征，再看SP-04/evidence/r03_assessments.json的情境/原因，最后看SP-04/evidence/r05/comparison.json逐场景差异。第一条会生成本机快照引用，因此换机器先重跑它。

## 2. 总调用地图
```text
原始观测 + 到达时序 + 实验配置
    → alignment.align（M3窗口）
    → engine.compute（重建核验并组合十二特征）
        → basic_flow.calculate
        → state_features.state_features → transitions.count_transitions
        → continuous.continuous_features
    → checkpoint.save（真实快照 + FeatureWindow）
    → rules.classify
        → gates.gate → checkpoint.restore → 重算验证
        → 情境分支 + 原因码 + 稳定身份 → SituationAssessment
```
stream.Stream是M3的流式时钟/缓存适配层；replay是入门回放工具，不是上图每一步都必须调用的前置阶段。

## 3. 第一站：统一输入输出
文件edge/contracts/models.py。先找SensorObservation、validate_raw_observation、AlignedWindow、Features、FeatureWindow、SituationAssessment。
它们是“允许什么数据进出”的候选契约，不是分类算法。检查类型、单位/枚举、时区、未知、来源和跨字段约束。schema_version是载荷版本，feature_version是特征语义版本，不能混为一谈。对应JSON结构在reference/reference_02/contracts/。

## 4. 第二站：SP-03 时间治理
|顺序/文件|主要入口|输入→输出与功能|
|---|---|---|
|1 src/replay.py|replay、main|观测列表→按received_at和ID排序的回放；保留事件时间null，记录降级；命令行读JSONL|
|2 src/alignment.py|align|观测+窗尾+配置→候选窗口和审计；这是M3核心|
|3 src/stream.py|Stream、push、advance|按接收时间输入/推进时钟→分批窗口；管理缓存、boot、追赶和失败原子性|
|4 data/build_three_source.py|脚本|生成21条三源观测及独立手写双窗预期|
|5 data/build_case.py|脚本|早期小样例构造，仍依赖测试帮助代码，不是生产工具|
|6 evidence/stage_review_reproduce.py|历史脚本|保留修复前问题的复现思路，不是当前必须成功的验收命令|

### align的算法顺序
校验观测→去重/身份冲突→逐窗截止筛选→三源排序→构造有效区间→裁剪并合并→计算coverage与窗尾状态→推导来源→DTO校验。

重点算法：
- 双时间：event_time决定测量归属，received_at决定是否赶上发布；无可信事件时间时回退但保留降级。
- 固定截止滑窗：(t-W,t]，默认W30/S5/L2；超过某窗截止不回改它，仍可进入后续窗。
- TTL状态保持：water/presence保持到下一观测或TTL，明确未知会中断；到期相等即unknown。
- flow区间：暂假设event_time为统计间隔终点，使用(t-interval,t]，不无限外推。
- 区间并集：排序合并重叠区间，coverage=并集有效秒数/W；窗尾状态与历史覆盖分别算。
- 来源追溯：保留未知中断引用，全模拟/全硬件/混合/无可核验证据分别推导origin。

Stream注意：同接收时刻先push完再advance；push在副本上尝试推进/清理/容量检查，成功才提交。advance有单次窗口数上限，next_end是追赶游标。boot隔离为保守清缓存，不是精确跨启动时间重建。

## 5. 第三站：SP-03-features 十二特征
先读engine.py掌握组合，再逐个读子算法，最后checkpoint.py。
|文件|入口|职责|
|---|---|---|
|src/engine.py|compute|核对设备、按配置重建M3窗口并精确匹配引用/来源，调用三个子计算，合并十二字段，输出missing_mask；此时还是内部结果|
|src/basic_flow.py|calculate|解析窗口引用，校验区间，计算均值、峰值、活动占比及内部覆盖诊断；重叠流量区间拒绝|
|src/state_features.py|state_features|核对配置摘要/宽度，算水接触和人员状态、比例、转换及固定等权总覆盖|
|src/transitions.py|count_transitions|相接已知区间之间计变化；支持有前驱证据的人员窗尾点；无比较证据返回null|
|src/continuous.py|continuous_features|完整历史按截止筛选，从窗尾反向找连续链，求流水与未检出人员区间交集|
|src/checkpoint.py|canonical、save、restore、emit|规范化JSON、内容摘要、临时文件/fsync/替换；恢复时校验并重算；emit产生完整候选FeatureWindow|
|demo.py|脚本|读取三源夹具、生成窗口与特征、保存和恢复两份实际工件|

### 十二特征从哪里来
|字段|算法/含义|主要文件|
|---|---|---|
|flow_mean_lpm|Σ(流量×有效时长)/有效时长|basic_flow.py|
|flow_max_lpm|有效区间最大流量|basic_flow.py|
|flow_active_ratio|超过阈值的有效时长/流量有效时长|basic_flow.py|
|flow_streak_sec|截至窗尾连续活动区间链|continuous.py|
|flow_change_count|连续区间active/inactive变化次数|state_features.py + transitions.py|
|water_contact|窗尾有效湿/干/未知|state_features.py|
|water_contact_sec|截至窗尾连续湿链|continuous.py|
|presence_state|窗尾检出/未检出/未知|state_features.py|
|presence_occupied_ratio|检出人员有效时长/人员总有效时长|state_features.py|
|presence_transition_count|连续已知在场状态变化，包含合资格窗尾点|state_features.py + transitions.py|
|absence_after_flow_sec|活动流水与未检出人员有效交集的窗尾连续链|continuous.py|
|data_coverage_ratio|三源coverage固定等权平均，缺源不重分配|state_features.py|

例：10秒6 L/min、20秒0，均值2；只有10秒6、其余未知，均值6且覆盖1/3。未知不能补0。
连续时长每个窗尾从历史重算，不相加重叠窗口；可大于W。历史截断时只返回已有证据支持的时长，不证明真实起点。当前保存完整历史，尚非有界实时检查点。

## 6. 第四站：SP-04 情境规则
|文件|入口|职责|
|---|---|---|
|src/gates.py|gate|检查规则配置、候选特征版本、受控目录、快照重算一致性、评估时间、flow/presence终态和覆盖；从原始flow区间派生IDLE连续证据|
|src/rules.py|classify|消费门控；输出四情境、原因码、质量、规则版本/配置摘要与assessment_id，候选DTO校验|
|src/scenarios.py|observations|用标准库生成合成操作观测，不依赖测试框架|
|demo.py|脚本|消费M4实际工件，输出情境演示|
|evaluate.py|evaluate、metrics|八个合成trial比较B0/B1/B2与5/10/15秒，单列拒判并计入全样本正例召回|

门控先于分类：非法输入拒绝；合法但不足输出UNKNOWN。READY只是内部“可继续”，不是第五种情境。
规则优先级：flow未知或覆盖不足→UNKNOWN；有效inactive且连续无流>=5秒→IDLE；有效active且人员present→ATTENDED_FLOW；active且absent的连续交集>=10秒→POSSIBLE_UNATTENDED_FLOW；其余UNKNOWN。
门槛默认flow/presence覆盖0.8，窗口年龄超过10秒过旧。IDLE不强制presence，但其他源失效仍降级。规则分数null；水接触wet不取消安全信号，也不改用水情境。
身份算法：规范化证据、规则语义版本与配置→SHA256。新鲜固定窗口重复评估保持一致；过旧拒判纳入时刻使用不同身份，避免覆盖历史有效判断。摘要不是数字签名。

## 7. 第五站：按能力阅读测试
|模块/文件|主要证明什么|
|---|---|
|SP-03/tests/test_replay.py|排序、未知保留、坏输入及重复拒绝|
|test_alignment.py|窗口、TTL、迟到、区间裁剪和引用|
|test_golden_r04.py|独立手写边界预期与来源|
|test_stream.py|流式/批处理、boot、容量原子性、追赶及审计|
|test_three_source.py|21条三源双窗黄金|
|SP-03-features/tests/test_definitions.py|字典字段与四组算术|
|test_basic_flow.py|手算、100组独立逐秒参考、区间拆分不变性|
|test_state_features.py|人员/水接触、随机逐秒参考、配置与来源|
|test_continuous.py|跨窗时长、历史截断、TTL/unknown中断|
|test_transitions.py|flow变化、窗尾点及独立布尔参考|
|test_engine.py|十二字段完整黄金、反序、缺失和错配|
|test_checkpoint.py|真实保存恢复、继续输入、损坏/版本及保存失败|
|SP-04/tests/test_r01_definitions.py|人工规则表与阈值前提|
|test_gates.py|可信入口、过旧、IDLE证据及2304组合互斥|
|test_rules.py|实际管线9.9/10/10.1秒及稳定身份|
|test_matrix.py|缺失情境/质量/原因精确对照、water独立和配置拒绝|
|test_evaluation.py|基线计数守恒、手算指标与不可区分反例|
|test_recovery.py|新进程、重复评估、继续输入及快照故障拒绝|

单独运行某文件理解一个能力；随后跑完整回归。测试夹具之间有导入依赖，属于原型组织方式，工程化应提取公共夹具。

## 8. 目前实现了哪些算法，没实现哪些
已实现：确定性时间回放、固定截止滑窗、TTL治理、区间裁剪/并集/交集、时间加权统计、连续链回溯、状态转换计数、质量拒判、阈值决策树式规则、内容寻址快照、重算恢复、稳定身份与基线统计。
未实现：学习型决策树/随机森林训练、真实家庭概率预测、有界实时持久状态、真实设备时钟映射、正式M6事件/告警或云通知。规则的if/else不是已经训练了机器学习决策树。

## 9. 最推荐的源码阅读顺序
models.py（只看六个关键类型）→alignment.align→basic_flow.calculate→engine.compute→state_features→transitions→continuous→checkpoint.save/restore→gates.gate→rules.classify→evaluate.metrics→stream.Stream。
第一遍不深究路径导入/哈希细节，先画输入输出；第二遍拿一个测试逐行追踪。每读完一个文件，回答“输入是什么、遇到未知怎么处理、输出给谁、测试在哪里”。

## 10. 回归与边界
```powershell
.\.venv-app\Scripts\python.exe -m pytest spikes/SP-04/tests spikes/SP-03-features/tests spikes/SP-03/tests tests/contracts tests/smoke -q -p no:cacheprovider
```
最近记录为171通过，含已有契约/启动；本文仅代码地图，没有重跑。真实性能、硬件/boot/flow端点、独立评审仍待完成。阅读总文档地图：B_PROJECT_MAP_AND_NEXT_STEPS.md；逐轮成果分别见三个目录README。
