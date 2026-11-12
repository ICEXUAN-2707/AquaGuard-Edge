# C3 轻量模型卡：c3-decision-tree-v1-70bd368a859b

## 基本信息

- 模型族：`decision-tree`（纯 Python 决策树，无外部 ML 依赖）
- 模型格式：`b-exp-tree-v1`
- 特征版本：`m4-r06-v1`
- 模型文件：`audit/b-independent-20261112/r07/model/c3-model.json`
- 文件摘要：`e365d855f51a3394ab6a559bd6b83d483707312532940a0f820c2a780c291e8a`
- 训练用冻结清单：`5e50db579e8ab29582d05090ac88aa564f9ab02f69320268b93703346f1f912c`
- 训练 trial：`idle-train-1101`, `attended-train-1114`, `attended_wet-train-1127`, `static_present-train-1140`, `intermittent_flow-train-1153`, `transient_brief-train-1166`, `left_10-train-1179`, `left_20-train-1192`, `async_sources-train-1296`, `duplicates-train-1309`
- 训练样本：10（正例 4）

## 输入特征

- `flow_mean_lpm`
- `flow_max_lpm`
- `flow_active_ratio`
- `flow_streak_sec`
- `flow_change_count`
- `presence_occupied_ratio`
- `presence_transition_count`
- `absence_after_flow_sec`
- `data_coverage_ratio`

明确排除：`water_contact`, `water_contact_sec`。水接触是独立安全信号，不进入模型，模型也无法抑制或延迟该信号。

## 超参数

- `max_depth=2`
- `min_samples_leaf=2`
- `criterion=gini`
- 平票策略：`positive`（平票判正例，避免静默漏报）

## 样本外指标（eval split）

- 分母：共 17 项，可判定 10 项，证据不足、应拒判 7 项。
- 证据不足项正确拒判：5/7；不并入普通二分类分母。
- 训练与评估使用相同场景族的不同种子，不构成独立真实场景验证。

- n=17，tp=4，fp=0，tn=6，fn=0，拒判正例=0，拒判负例=0
- 召回（含拒判分母）：1.000；误报率：0.000

## 加载与回退

- 加载时校验模型格式、特征版本、特征名列表、排除特征列表、内容摘要与树结构。
- 模型缺失：`MODEL_MISSING`；版本不匹配：`MODEL_VERSION_MISMATCH`；内容损坏：`MODEL_CORRUPT`。任一情况回退到 C2 规则结果，并在结果中保留 `fallback=true` 与原因码。
- 影子推断：C3 只记录候选与分数，不发布 `SituationAssessment`，不进入 M6，不改变 C0/C1/C2 输出。

## 限制

- 合成样本量很小，模型只证明“可训练、可加载、可影子运行”，不证明真实环境收益。
- 特征与标签都由仿真操作时间线生成；本轮模型只形成一次 `presence_occupied_ratio` 切分，不能说明它学到了可迁移的时序语义。
- 未做超参数搜索、交叉验证或统计显著性检验。
