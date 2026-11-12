# B 实验指标（b-exp-report-v1）

范围：`synthetic_prototype_only`。一个 scenario 的一个冻结种子为一个独立 trial；窗口在 trial 内聚合为一次告警决策。

## 指标定义

- `n`：评估 trial 数（一个 scenario 的一个冻结种子为一个 trial）。
- `decidable`：期望为候选或明确无候选、且仿真证据足以判定的 trial 数。
- `unknown_required`：证据不足、正确输出为 UNKNOWN 的 trial 数（含不可区分场景）。
- `tp`：期望候选且输出候选的 decidable trial 数。
- `fp`：期望无候选却输出候选的 decidable trial 数（按 trial 计，不按重叠窗计）。
- `tn`：期望无候选且输出无候选的 decidable trial 数。
- `fn`：期望候选却明确输出无候选的 decidable trial 数。
- `rejected_positive`：期望候选但输出 UNKNOWN 的 decidable trial 数。
- `rejected_negative`：期望无候选但输出 UNKNOWN 的 decidable trial 数。
- `precision`：tp / (tp + fp)；无候选输出时为空。
- `recall`：tp / (tp + fn + rejected_positive)；拒判正例计为未检出。
- `recall_decided`：tp / (tp + fn)；只统计方法实际给出二值结论的正例。
- `false_positive_rate`：fp / (fp + tn + rejected_negative)；拒判负例保留在分母。
- `rejection_rate`：(rejected_positive + rejected_negative) / decidable。
- `correct_abstentions`：unknown_required 中输出 UNKNOWN 的 trial 数。
- `decided_without_evidence`：unknown_required 中仍给出候选的 trial 数。
- `negative_without_evidence`：unknown_required 中仍明确判为无候选的 trial 数。
- `detection_delay_sec`：成功检出的正例中，首个候选窗口窗尾减操作真值 onset（秒）；含窗口步长与 10 秒规则阈值，不含真实网络/硬件时延。

## 总体结果

| 方法 | n | 可判定 | tp | fp | tn | fn | 拒判正例 | 拒判负例 | 召回 | 误报率 | 拒判率 | 延迟中位数(s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C0 流量阈值基线 | 34 | 20 | 8 | 10 | 2 | 0 | 0 | 0 | 1.000 | 0.833 | 0.000 | 10.000 |
| C1 即时多源规则 | 34 | 20 | 8 | 2 | 10 | 0 | 0 | 0 | 1.000 | 0.167 | 0.000 | 10.000 |
| C2 时序/上下文规则 | 34 | 20 | 8 | 0 | 12 | 0 | 0 | 0 | 1.000 | 0.000 | 0.000 | 10.000 |
| C3 轻量 ML 影子推断 | 34 | 20 | 8 | 0 | 12 | 0 | 0 | 0 | 1.000 | 0.000 | 0.000 | 10.000 |

## 评估集（C3 的样本外结果）

n 包含可判定与证据不足项；二分类指标只针对可判定项。证据不足项正确拒判请查看 report.metrics 中 correct_abstentions / unknown_required；不能把 n 当作二分类分母，当前结果不证明 C3 优于 C2。

| 方法 | n | tp | fp | tn | fn | 拒判正例 | 拒判负例 | 召回 | 误报率 |
|---|---|---|---|---|---|---|---|---|---|
| C0 流量阈值基线 | 17 | 4 | 5 | 1 | 0 | 0 | 0 | 1.000 | 0.833 |
| C1 即时多源规则 | 17 | 4 | 1 | 5 | 0 | 0 | 0 | 1.000 | 0.167 |
| C2 时序/上下文规则 | 17 | 4 | 0 | 6 | 0 | 0 | 0 | 1.000 | 0.000 |
| C3 轻量 ML 影子推断 | 17 | 4 | 0 | 6 | 0 | 0 | 0 | 1.000 | 0.000 |

## 失败反例（按方法，含 train/eval）

- `C0_threshold_flow` / `attended-eval-2218` / FALSE_POSITIVE：期望 no_candidate，实际 True（FLOW_ACTIVE）。期望无候选但方法给出候选。
- `C0_threshold_flow` / `attended-train-1114` / FALSE_POSITIVE：期望 no_candidate，实际 True（FLOW_ACTIVE）。期望无候选但方法给出候选。
- `C0_threshold_flow` / `attended_wet-eval-2235` / FALSE_POSITIVE：期望 no_candidate，实际 True（FLOW_ACTIVE）。期望无候选但方法给出候选。
- `C0_threshold_flow` / `attended_wet-train-1127` / FALSE_POSITIVE：期望 no_candidate，实际 True（FLOW_ACTIVE）。期望无候选但方法给出候选。
- `C0_threshold_flow` / `intermittent_flow-eval-2269` / FALSE_POSITIVE：期望 no_candidate，实际 True（FLOW_ACTIVE）。期望无候选但方法给出候选。
- `C0_threshold_flow` / `intermittent_flow-train-1153` / FALSE_POSITIVE：期望 no_candidate，实际 True（FLOW_ACTIVE）。期望无候选但方法给出候选。
- `C0_threshold_flow` / `invalid_presence-eval-2388` / DECIDED_WITHOUT_EVIDENCE：期望 unknown，实际 True（FLOW_ACTIVE）。证据不足却给出候选。
- `C0_threshold_flow` / `invalid_presence-train-1244` / DECIDED_WITHOUT_EVIDENCE：期望 unknown，实际 True（FLOW_ACTIVE）。证据不足却给出候选。
- `C0_threshold_flow` / `late_presence-eval-2405` / DECIDED_WITHOUT_EVIDENCE：期望 unknown，实际 True（FLOW_ACTIVE）。证据不足却给出候选。
- `C0_threshold_flow` / `late_presence-train-1257` / DECIDED_WITHOUT_EVIDENCE：期望 unknown，实际 True（FLOW_ACTIVE）。证据不足却给出候选。
- `C0_threshold_flow` / `presence_miss-eval-2337` / INDISTINGUISHABLE_OUTPUT：期望 unknown，实际 True（FLOW_ACTIVE）。不可区分场景仍给出确定输出。
- `C0_threshold_flow` / `presence_miss-train-1205` / INDISTINGUISHABLE_OUTPUT：期望 unknown，实际 True（FLOW_ACTIVE）。不可区分场景仍给出确定输出。
- `C0_threshold_flow` / `presence_stop-eval-2354` / DECIDED_WITHOUT_EVIDENCE：期望 unknown，实际 True（FLOW_ACTIVE）。证据不足却给出候选。
- `C0_threshold_flow` / `presence_stop-train-1218` / DECIDED_WITHOUT_EVIDENCE：期望 unknown，实际 True（FLOW_ACTIVE）。证据不足却给出候选。
- `C0_threshold_flow` / `slow_presence-eval-2439` / DECIDED_WITHOUT_EVIDENCE：期望 unknown，实际 True（FLOW_ACTIVE）。证据不足却给出候选。
- `C0_threshold_flow` / `slow_presence-train-1283` / DECIDED_WITHOUT_EVIDENCE：期望 unknown，实际 True（FLOW_ACTIVE）。证据不足却给出候选。
- `C0_threshold_flow` / `static_present-eval-2252` / FALSE_POSITIVE：期望 no_candidate，实际 True（FLOW_ACTIVE）。期望无候选但方法给出候选。
- `C0_threshold_flow` / `static_present-train-1140` / FALSE_POSITIVE：期望 no_candidate，实际 True（FLOW_ACTIVE）。期望无候选但方法给出候选。
- `C0_threshold_flow` / `transient_brief-eval-2286` / FALSE_POSITIVE：期望 no_candidate，实际 True（FLOW_ACTIVE）。期望无候选但方法给出候选。
- `C0_threshold_flow` / `transient_brief-train-1166` / FALSE_POSITIVE：期望 no_candidate，实际 True（FLOW_ACTIVE）。期望无候选但方法给出候选。
- `C1_instant_multisource` / `late_presence-eval-2405` / DECIDED_WITHOUT_EVIDENCE：期望 unknown，实际 True（PRESENCE_ABSENT）。证据不足却给出候选。
- `C1_instant_multisource` / `late_presence-train-1257` / DECIDED_WITHOUT_EVIDENCE：期望 unknown，实际 True（PRESENCE_ABSENT）。证据不足却给出候选。
- `C1_instant_multisource` / `presence_miss-eval-2337` / INDISTINGUISHABLE_OUTPUT：期望 unknown，实际 True（PRESENCE_ABSENT）。不可区分场景仍给出确定输出。
- `C1_instant_multisource` / `presence_miss-train-1205` / INDISTINGUISHABLE_OUTPUT：期望 unknown，实际 True（PRESENCE_ABSENT）。不可区分场景仍给出确定输出。
- `C1_instant_multisource` / `slow_presence-eval-2439` / DECIDED_WITHOUT_EVIDENCE：期望 unknown，实际 True（PRESENCE_ABSENT）。证据不足却给出候选。
- `C1_instant_multisource` / `slow_presence-train-1283` / DECIDED_WITHOUT_EVIDENCE：期望 unknown，实际 True（PRESENCE_ABSENT）。证据不足却给出候选。
- `C1_instant_multisource` / `transient_brief-eval-2286` / FALSE_POSITIVE：期望 no_candidate，实际 True（PRESENCE_ABSENT）。期望无候选但方法给出候选。
- `C1_instant_multisource` / `transient_brief-train-1166` / FALSE_POSITIVE：期望 no_candidate，实际 True（PRESENCE_ABSENT）。期望无候选但方法给出候选。
- `C2_temporal_rules` / `presence_miss-eval-2337` / INDISTINGUISHABLE_OUTPUT：期望 unknown，实际 True（POSSIBLE_UNATTENDED_FLOW）。不可区分场景仍给出确定输出。
- `C2_temporal_rules` / `presence_miss-train-1205` / INDISTINGUISHABLE_OUTPUT：期望 unknown，实际 True（POSSIBLE_UNATTENDED_FLOW）。不可区分场景仍给出确定输出。
- `C3_lightweight_ml_shadow` / `late_presence-eval-2405` / NEGATIVE_WITHOUT_EVIDENCE：期望 unknown，实际 False（NO_CANDIDATE）。证据不足却明确判为无候选。
- `C3_lightweight_ml_shadow` / `late_presence-train-1257` / NEGATIVE_WITHOUT_EVIDENCE：期望 unknown，实际 False（NO_CANDIDATE）。证据不足却明确判为无候选。
- `C3_lightweight_ml_shadow` / `presence_miss-eval-2337` / INDISTINGUISHABLE_OUTPUT：期望 unknown，实际 True（ML_INFERENCE）。不可区分场景仍给出确定输出。
- `C3_lightweight_ml_shadow` / `presence_miss-train-1205` / INDISTINGUISHABLE_OUTPUT：期望 unknown，实际 True（ML_INFERENCE）。不可区分场景仍给出确定输出。

## 不可区分场景（保留，不并入误报/召回）

- `presence_miss-train-1205`：人员实际在场但传感器未检出；输入与 left_10 相同，任何方法都无法从当前观测区分。 输出：`{"C0_threshold_flow": true, "C1_instant_multisource": true, "C2_temporal_rules": true, "C3_lightweight_ml_shadow": true}`
- `presence_miss-eval-2337`：人员实际在场但传感器未检出；输入与 left_10 相同，任何方法都无法从当前观测区分。 输出：`{"C0_threshold_flow": true, "C1_instant_multisource": true, "C2_temporal_rules": true, "C3_lightweight_ml_shadow": true}`

## 限制

- 全部结果来自固定种子的合成仿真；只能证明在明确设定的仿真条件下各方法表现如何，不能证明真实环境泛化能力。
- 17 个场景族各 2 个 trial（共 34 个），样本量很小，不构成统计显著性，也不报告置信区间。
- C3 只在训练集上拟合、在评估集上影子推断；它不追求优于规则，训练样本仅 10 个，不能据此宣称 ML 收益。
- 10 秒无人在场流水阈值、0.1 LPM 流量阈值与 0.8 覆盖率来自既有实验默认值，不是实测最优或标定结论。
- 检测延迟按 5 秒窗口步长计，只表示决策延迟，不含真实采集、网络与硬件时延。
- 在线/离线一致仅覆盖本实现的同一批观测与同一到达顺序，不等于正式服务并发、崩溃恢复或真实时钟验证。
- C3 是影子推断，不发布 SituationAssessment，不参与 M6 决策，也不能读取或覆盖水接触安全特征。
- 没有真实硬件、真实 trial 操作日志与独立 Reviewer；所有结果是 prototype_only。
