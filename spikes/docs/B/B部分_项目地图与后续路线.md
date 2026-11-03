# B部分项目地图与下一阶段实施路线

整理日期：2026-11-02。适合组长、零基础成员和后续开发者。当前交付边界以各模块最新报告为准，早期报告只记录当时状态；本文是路线与索引，不代表新增验收已执行。

## 1. 我们现在在哪里
已经跑通离线模拟观测→M3时间对齐→M4十二特征与快照→M5四情境规则。最近已记录回归171项通过，包含既有契约/启动检查，不是项目完成比例。正式模块、实物和全系统验收仍未完成；10秒为批准的实验阈值，不是实测最优值。

技术验证结束后的工作是“确认语义→工程化→联合闭环→实物标定→独立实验→验收交付”。不要直接将spikes文件复制到正式目录后宣布上线。

## 2. 下一阶段按什么顺序做
|批次|做什么与怎么做|产物|退出条件|
|---|---|---|---|
|P0 评审与基线|A/B/C共同看M3决策表、M4/M5收尾限制，确认flow区间端点、TTL、boot、拒判、来源和10秒策略；记录配置/代码/数据版本|决议、待办责任人、合同哈希和回滚说明|关键口径有明确决定；正式冻结依C0，不代签|
|P1 模拟在线工程化|从真实输入接口接入统一DTO；提取原型逻辑到正式alignment/features/inference模块；统一时钟/配置注册、受控证据存储、日志、错误与生命周期|正式模块、小规模流式服务、迁移说明|同输入、到达顺序和时钟与黄金回放一致；容量/背压和恢复有证据|
|P2 本地联合闭环|A输入→B情境→C唯一事件/SQLite/API/页面；水接触快速信号直接到M6，不等滑窗；页面显示来源、覆盖、年龄、原因和UNKNOWN|联合场景、事件链、演示与日志|正常/水浸/沉默/重复/ACK仍湿等断言通过，本地无需云可运行|
|P3 实物适配和标定|型号确定后先单源读数，再三源；记录供电、电平、采样/抖动/网络延迟、流量标定、静止人员反例、拔线和重启|硬件资料、原始日志、标定与TIME_ASSUMPTIONS、参数版本|真实观测可重放且算法语义一致；缺证据仍UNKNOWN|
|P4 独立操作实验|按trial_id记录真实操作；开发/验证用于调参，测试trial锁定；同trial重叠窗不跨分区；比较即时/10秒规则|标注指南、trial清单、划分、混淆/拒判/误报/召回/延迟报告|样本和限制公开；不拿规则输出当真值，不用删除拒判提高分数|
|P5 云端与故障联合验收|在本地闭环稳定后验证IoTDA回执、断WAN、本地提醒、Outbox重试与来源禁止；实测传输与业务确认区别|脱敏回执、故障矩阵、日志|本地/云/联系人分别验收；当前联系人仍非MVP承诺|
|P6 交付与复核|独立Reviewer按CT矩阵复查；完整安装、启动、恢复、演示、限制和回滚文档；整洁环境重跑|版本发布说明、验收签字、演示包|未通过项明确保留，不以Mock代替硬件/云|

P0与硬件资料收集可并行，P1/P2不必等采购；正式部署/真实通知另按授权实施。以上为批次，不预设未经确认的工时或比赛截止日期。ML不在必要路径；真实数据证明规则不足且具备独立样本时再单独验证模型。

## 3. B部分工程化必须补什么
- M3：确认可靠boot/时间映射，处理真实采样节奏，避免“区间不恰好结束于窗尾”导致过多UNKNOWN；语义调整必须升版及回归。
- M4：当前完整历史快照重算用于参考正确性。正式持续运行要设计有界状态/持久化、原始日志保留策略、幂等消费及故障恢复；用现有参考算法交叉核对。
- M5：保留质量门控与10秒规则，固化评估身份/过旧查询策略，验证全部原因码和质量组合。未检出不等于真实无人，保留不可区分反例。
- 接口：在各实际入口调用正式DTO；spikes之间目前有路径导入，不是可直接发布的包。统一依赖、配置与测试夹具。

## 4. 推荐阅读顺序（不要按目录全读）
第一遍看全貌：本文→spikes/docs/B/B部分_分批交付说明.md→spikes/docs/B/SP-04/R06_开发报告.md。先知道做成什么、没做到什么。
第二遍看链路：SP-03/README.md与待确认口径表.md→M4/技术总结与敏捷计划.md与内部输入与计算口径.md→M5/R01_规则与接口约定.md。先理解时间、未知、特征，再理解规则。
第三遍看最新验收：M3 R06_开发报告.md及R05修复→M4 R07_开发报告.md→M5 R06_开发报告.md→docs/contracts/CONTRACT_ACCEPTANCE.md。将模拟结果与正式门槛分开。
第四遍亲自跑：M4/demo.py→M5/demo.py→M5/evaluate.py→全部回归；最后对照JSON和测试理解代码。
第五遍做开发或组会复盘时，再按下表回读每轮报告和审查记录。

## 5. 文档地图：总入口与正式依据
以下路径均相对仓库根目录。
|文档|包含什么|什么时候读|
|---|---|---|
|README.md|项目介绍、运行环境与历史基线|首次接触项目|
|docs/README.md|全项目文档导航及各线入口|找跨组资料|
|spikes/docs/B/B部分_分批交付说明.md|B线分批提交、复现命令、历史路径和范围|组会交付/拉取分支后|
|docs/project/DEVELOPMENT_技术总结与敏捷计划.md|I-001至I-013依赖和验收提案，含历史状态|排正式实施任务，不能当实时进度表|
|docs/project/UPSTREAM_REVIEW.md|运行栈和上游复用核查|工程化依赖选择|
|spikes/docs/B/B_任务单.md|B负责SP-03/SP-04的目标、步骤与交付|理解原始任务|
|docs/spikes/SPIKE_TRACKER.csv|Owner/Reviewer/依赖与状态记录|每轮同步进度|
|docs/spikes/templates/SPIKE_ISSUE_TEMPLATE.md|实验任务模板|新建一轮任务|
|docs/spikes/templates/SPIKE_REPORT_TEMPLATE.md|实验报告模板|结束留痕|
|docs/contracts/STATUS.md|契约线状态及对接|确认批准边界|
|docs/contracts/CONTRACT_ACCEPTANCE.md|C0-C5、CC/CT证据与验收记录|正式模块放行必读|
|docs/contracts/CONTRACT_COMPLIANCE.md|历史符合性问题与探针|追溯契约缺陷|
|docs/contracts/CONTRACT_REVIEW_DRAFT.md|评审裁决草案|理解讨论背景|
|docs/contracts/CONTRACT_JOINT_REVIEW_REPORT.md|联合评审材料与裁决背景|准备会签，不视为已签|
|reference/reference_02/00_Contracts_V1.2_修订候选.md|当前候选字段、未知、来源、事件与API增量语义|与机器模型一起读|
|reference/reference_02/00_Contracts_V1.1_深化规范.md|历史深化基线，未冲突处仍适用|查设计背景|
|reference/reference_02/modules/M3_时序对齐与质量治理.md|M3职责和边界|理解模块责任|
|reference/reference_02/modules/M4_特征融合与状态记忆.md|M4十二特征与持续状态要求|同上|
|reference/reference_02/modules/M5_轻量AI情境识别.md|M5规则/ML边界与实验要求|同上|
|reference/reference_02/modules/M6_情境决策与事件状态机.md|下游安全事件职责|与C对接|
|reference/reference_02/tests/BEHAVIOR_TEST_MATRIX.md|正式行为测试索引|验收追踪|
|docs/audit/REPO_AUDIT.md、GAP_ANALYSIS.md、DEPENDENCY_RISKS.md|历史资产、缺口及依赖风险|追溯初始依据，非最新完成清单|

## 6. 文档地图：M3 / SP-03每份材料
目录spikes/SP-03/。
|文档|内容|
|---|---|
|README.md|运行说明、最初口径及各轮追加入口|
|REPORT.md|所有报告与M4计划索引|
|待确认口径表.md|flow、TTL、seq、boot、截止和M4输入等待确认的十项口径|
|R01_开发报告.md|统一输入、四条观测回放及初次环境问题|
|R02_开发报告.md|固定截止窗口、区间覆盖和来源引用修复|
|R03_开发报告.md|分源TTL、流式推进、boot隔离与容量保护|
|R04_开发报告.md|五组黄金边界、迟到追溯及审计引用修复|
|R01至R04_阶段审查.md|四轮阶段问题分级、复现和整改顺序|
|R05_开发报告.md|容量原子恢复、启动资格、追赶上限及版本修复|
|R06_开发报告.md|21条三源观测、双窗黄金和独立运行自查|

## 7. 文档地图：M4每份材料
目录spikes/SP-03-features/。
|文档|内容|
|---|---|
|README.md|最新交付入口和演示/回归命令|
|技术总结与敏捷计划.md|M3完整算法总结与M4原始分轮计划；实际轮次后来扩展|
|内部输入与计算口径.md|窗口、引用观测、配置和检查点内部接口提案|
|R01_开发报告.md|十二特征字典及四组基础手算|
|R02_开发报告.md|流量均值/峰值/活动占比及独立参考核对|
|R03_开发报告.md|水接触、人员比例/变化、总覆盖和当时项目进度|
|R04_开发报告.md|历史连续时长、TTL/缺口中断和回放限制|
|R05_开发报告.md|流量变化计数、人员窗尾点与未知边界|
|R06_开发报告.md|统一十二特征入口、历史/配置/窗口核验|
|R07_开发报告.md|检查点、恢复/故障、候选输出及阶段收尾限制|
|data/feature_dictionary.csv|十二字段名称、单位、定义与缺失口径|
|data/hand_cases.json|独立手写基础计算预期|

## 8. 文档地图：M5每份材料
目录spikes/SP-04/。
|文档|内容|
|---|---|
|README.md|最新规则验证交付入口与组会讲解|
|规则验证规划与审核记录.md|审核原始规划及用户修改记录；草案15秒已被10秒覆盖|
|R01_规则与接口约定.md|规则顺序、IDLE证据、时效/身份、质量及后续细化|
|R01_开发报告.md|批准阈值、15个手写场景和定义检查|
|R02_开发报告.md|门控、2304组合互斥、质量/原因细化|
|R03_开发报告.md|分类引擎、原因、身份和实际管线边界|
|R04_开发报告.md|缺失矩阵、无效配置修复、水接触独立和阈值交叉|
|R05_开发报告.md|8个合成trial基线对照、拒判代价与失败反例|
|R06_开发报告.md|新进程恢复、故障拒绝、六轮成果与最终限制|
|data/rules_config.json|当前实验默认：无人流水10秒、IDLE5秒、覆盖0.8等|
|data/hand_cases.json|规则手写期望场景，不是实际人员数据|
|data/evaluation_trials.json|合成操作注释与二元对照目标|

## 9. 代码地图：什么时候看哪个文件
|模块|文件|作用|
|---|---|---|
|M3|src/replay.py|原始观测确定性回放|
|M3|src/alignment.py|固定截止、有效区间、覆盖/终态和候选窗口|
|M3|src/stream.py|显式时钟、缓存/boot、原子push与分批追赶|
|M3|tests/与data/|边界、人工黄金、三源场景及构造工具|
|M4|src/basic_flow.py|有效流量积分和基础特征|
|M4|src/state_features.py、transitions.py|状态比例、转换、配置绑定|
|M4|src/continuous.py|历史连续链与流水/未检出交集|
|M4|src/engine.py|统一十二特征与输入重建核验|
|M4|src/checkpoint.py|快照保存恢复和完整候选FeatureWindow|
|M4|demo.py|两窗真实模拟输出与恢复演示|
|M5|src/gates.py|可信快照、版本、时效、质量和IDLE证据|
|M5|src/rules.py|四情境、原因、规则版本与身份|
|M5|src/scenarios.py|独立合成观测构造|
|M5|demo.py|消费M4实际工件生成候选情境|
|M5|evaluate.py|基线与阈值对照、拒判统计|
|公共|edge/contracts/models.py|候选DTO及跨字段验证|
|公共|reference/reference_02/contracts/*.schema.json|机器可读结构约束|

以上src路径分别位于spikes/SP-03、spikes/SP-03-features、spikes/SP-04。测试先看test_basic_flow/test_engine/test_rules等对应能力，再看故障/恢复；不要从所有测试文件第一行开始通读。

## 10. 实际证据怎么找
- M3：data/r06_three_source.json人工预期；evidence/r06_windows.json实际窗口。
- M4：evidence/r07_feature_windows.json十二特征输出；evidence/checkpoints/真实历史快照；r07_tests.txt收尾回归。
- M5：evidence/r03_assessments.json情境输出；evidence/r05/comparison.json逐场景基线/指标；evidence/r06_tests.txt收尾，prepush_tests.txt推送前回归。
- evidence中的旧日志是历史当时结果；不互相相加当总测试数。最初问题复现脚本可能因后来修复而不再按旧逻辑运行。
- 快照含原机器路径。换目录先运行M4/demo.py，再M5/demo.py重新生成本机引用；内容摘要检查点不可手改。

## 11. 跨组资料怎么接着读
A线相关任务/软件收尾/实物实验文件见docs/spikes/A_*；AB_交叉自检报告.md与AB_第二轮交叉核对.md用于跨组信息对接。它们是其他工作线后来新增资料，本地图未重新审计其完成声明；联合计划前应逐项核对实际代码/日志，不能继承B线171项结果。
C线与云：spikes/docs/C/SP-06/README.md及REPORT.md、spikes/docs/C/SP-06_编码计划.md；docs/integration/IOTDA_INTEGRATION_技术总结与敏捷计划.md及IoTDA_人工对接操作指南.md。本次地图不代表重新验收这些模块。

## 12. 下一次最小任务建议
先开一次P0口径复核：每组提前看本文、M3/待确认口径表.md、M4/R07_开发报告.md、M5/R06_开发报告.md；会后形成“决定/证据/Owner/下一步”表。随后只选一条模拟在线纵向链路做P1/P2小迭代，不同时重构所有模块。每轮继续代码自检、独立预期交叉检查和受影响回归，并新增真实报告。
