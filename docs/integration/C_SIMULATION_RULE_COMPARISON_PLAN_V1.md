# 第一版仿真规则对照：C 只读结果接口与实验关联规划

日期：2026-11-10。状态：实施提案，尚未新增接口、冻结契约或导入实验结果。
范围：现有实验诊断页、JSON/JSONL、检查点及 SQLite；不新增实验平台。

## 1. 依据和已确认事实

1. 前端提交 `6a9be48` 的 `docs/project/B_RESULTS_FRONTEND_HANDOFF_PROPOSAL.md`：
   推荐独立 `GET /api/evaluations/{evaluation_id}`；实验与结果显式关联；
   浏览器不读任意本地路径、不执行工件；该文档自身是提案，非已冻结接口。
2. [最终交付基线](../AquaGuard_Edition11_Topic1_PlanB_V1.0/00_DELIVERY_BASELINE_V1.0.md)
   要求实验诊断展示对照、误报/召回/拒判/延迟及原始数据追溯。
3. [G0–G4 路线](../AquaGuard_Edition11_Topic1_PlanB_V1.0/01_INTEGRATION_ROADMAP_G0-G4.md)
   区分 G1 本地闭环与 G3 价值证明；仿真展示不能放行真实 trial/ML。
4. [M8 基线](../../reference/reference_02/modules/M8_用户产品与实验平台.md)：
   复用三页，来源明确、指标附口径、只读查询及证据导出。
5. [B R05 报告](../../spikes/docs/B/SP-04/R05_开发报告.md)、
   `spikes/SP-04/evaluate.py`、`data/evaluation_trials.json`、
   `evidence/r05/comparison.json`：已有 8 个手写操作注释的合成 trial，
   比较 B0_flow、B1_instant、B2_5s/10s/15s；任务是二元候选检测。
6. 当前 `ExperimentResult` 1.1 只有 trial_id/source/status/时间/asset_refs，
   DTO 禁止多余字段；`api.py` 和 `projections.py` 已提供元数据查询。
   当前运行中的 mqtt-trial/demo-trial 不等于 B 的 synthetic-* trial。

没有查到已冻结且名为“第一版仿真规则对照”的专门决议；本计划综合以上文档
与本次用户要求，不把前端提案当作已批准的新契约。前端提案位于另一分支，
此次只读其已提交版本，未合并或改动前端工作树。

## 2. 第一版目标与非目标

第一版展示 B 已实际执行的 B0/B1/B2 规则对照，明确 simulation、8 个构造场景、
二元目标和标签来源。保留 B 的方法原名与版本，不擅自映射为 C0/C1/C2/C3。
显示 tp/fp/tn/fn、两类拒判、总数、拒判率及包含拒判正例的召回分母。
不宣称真实家庭准确率、统计显著性、阈值最优、事故概率或 ML 已完成。

10 秒相比即时少两次误触发的案例实际变为 UNKNOWN，不能算成正确负例。
必须展示“静止在场但未检出”失败反例：与离开场景输入相同、标签相反。
未计算的延迟/F1/置信区间/模型指标使用 null 与具体原因，绝不填 0。
默认 10 秒不因展示阈值对照而改变；不触碰在线安全路径、ACK、Outbox 或云。

## 3. B/C/前端交接责任

| 生产者 | 最小交付 | C 的处理 |
|---|---|---|
| B | 带版本 evaluation JSON、trial 清单及独立操作标签、逐 trial 预测、配置/代码版本、输入 hash | 受控本地导入、严格校验、按 evaluation_id 固化结果 |
| B | 指标定义、分子/分母、方法版本与阈值、失败案例和限制 | 保留原值与口径，检查一致性，不替 B 重跑/重定义指标 |
| B | 数据/检查点引用、复现命令、恢复一致性结果 | 存储摘要与受控 artifact ID；缺失项明确标注 unavailable |
| B | 模型卡或规则方法说明 | 第一版可为规则说明；ML 未实现时明确 not_applicable |
| C | 只读结果、实验关联、错误码、已校验 fixture | 交前端联调，旧实验接口兼容 |
| 前端 | 在现有实验诊断页展示方法表、来源/版本/限制、逐 trial 反例和导出 | 不重算指标、不把本地路径当作可下载 URL |

现有 comparison.json 可用于形状适配，但缺 evaluation_id、完整版本和来源摘要。
不直接把历史 JSON 当正式完整报告；先约定最小交接清单并由 B 生成/补齐。
如暂以历史工件导入，记录 legacy 适配、原 hash 和缺失原因，不能伪造历史生成时间。

## 4. 候选接口（实施前以 fixtures 固定）

| 接口 | 内容 | 兼容/权限 |
|---|---|---|
| GET /api/experiments/{trial_id} | 保持原 ExperimentResult 1.1 | 原有 Bearer；无字段偷加 |
| GET /api/evaluations/{evaluation_id} | 版本化、已验证的离线报告 | 新独立只读 DTO；同 Bearer，无网络计算 |
| GET /api/experiments/{trial_id}/evaluations | 显式关联的 evaluation_id、B trial_id、关联类型与来源 | 新只读 DTO；未关联返回空列表，实验不存在返回 404 |

第一版无浏览器上传、执行评估/训练、文件路径查询和 HTTP 写入入口。
工件由受控本地 CLI 导入；不在 GET 请求内扫描目录、执行 B 脚本或修改业务状态。
结果随既有服务提供，沿用只绑定 loopback、鉴权与无凭据日志的边界。
实验关联不是“文件名看起来相似”或“都叫 simulation”。

建议 evaluation DTO 使用单独 `report_schema_version=1`，与原 schema_version=1.1
分开管理；新版本不受支持则拒绝导入，不修改共享 A/B 合同来迎合页面。

报告最小组成：

- identity：evaluation_id、report_schema_version、created_at（未知可 null+原因）、
  evaluation_code_commit、artifact_sha256、dataset_id/version/hash。
- scope：source=simulation、binary_candidate 任务、标签定义/来源、trial 数量、
  class_counts、sample_unit=trial。window_count 未交付时不可拿 trial_count 替代。
- methods：B 的 method_id/version、阈值/配置、特征版本；模型版本可 null+原因。
- metrics：原始六类计数、指标值、numerator/denominator、unit=fraction、
  population/split、unavailable_reason。n 必须等于六类计数之和。
- records：trial_id、独立目标、操作注释、逐方法 prediction（true/false/null）、
  失败案例说明与证据 ID。null 表示拒判，不能转为 false。
- provenance/limitations：工件清单、配置/代码 hash、复现命令、未测延迟、
  无真实独立试验/无训练、规则说明或模型卡状态。

现有 8 场景没有训练/验证/测试切分，split 明确写 scenario_set/no_training，
不伪造 train/test 清单。未来同任务、同数据/分区及同分母才允许方法比较。
simulation 和 hardware 分报告，不静默合并。

## 5. 标识、存储与导入

新增同一个业务 SQLite 内的两张小表即可：
`evaluations(evaluation_id PK, report_version, artifact_sha256, body)` 与
`experiment_evaluations(experiment_id, evaluation_id, evaluation_trial_id, relation_type, provenance)`。
关联支持多对多；B 单个 evaluation 可包含多个 trial，一次产品演示也可关联多个报告。
同 ID 同 hash 导入幂等，同 ID 异内容冲突，不能覆盖历史结果；报告与关联原子提交。

relation_type 至少区分 reproduction（该运行实际复现该 B trial）与
reference（仅供规则展示参考）。mqtt-trial 只有明确来源映射才可标 reproduction；
历史 R05 报告不能作为当前 MQTT 演示的同一批效果证据。尚无运行关联的 evaluation
也可凭显式 ID 独立读取，不为展示伪造一个已完成运行 trial。

导入路径只允许配置的受控目录，拒绝越界、链接逃逸、未知字段、超限报告、
重复 trial/method ID、非有限数值、来源混合、缺失方法预测及计数/分母不一致。
第一版建议 JSON 上限 2 MiB、最多 1000 trial/16 方法；实际阈值在 fixture 阶段确认。
hash 固定原始工件；规范化报告另留 hash，不声称导入 hash 等于整个数据集 hash。
查询只返回 artifact ID/类型/hash，不返回任意磁盘绝对路径、凭据或可执行内容。

## 6. 按顺序实施与验收

| 步骤 | C 交付 | 退出条件 |
|---|---|---|
| C-E1，先做 | 最小 DTO/字段说明、B 8-trial fixture、指标口径与 ID 映射表 | B 和前端可据同一 fixture 联调；缺失项有原因；方法命名无偷换 |
| C-E2 | 本地导入 CLI、两表存储、hash/关联/幂等校验 | 拒绝坏报告且无部分写入；导入后重启可查；不改变事件/Outbox |
| C-E3 | 两条新 GET、旧 GET 回归、API 示例 | 401/404/不支持方法/无关联/报告缺失明确；GET 无副作用；旧契约不变 |
| C-E4 | 给前端 fixture/错误示例，扩展既有诊断页联调 | 分数/分母/null/拒判/反例/来源/版本真实展示；导出内容与 API 一致 |
| C-E5 | 真实服务与浏览器联合验收，补入证据包及索引 | 版本工件→导入→关联→GET→页面→导出同轮可追溯，保留失败用例 |

至少验证：同 ID 异 hash、整数/布尔混淆、比例越界与 NaN、零分母、无计算值、
假 COMPLETE、引用未知 trial、跨来源关联、关联为空、服务重启、越权、路径逃逸、
读取不修改 DB、页面旧响应覆盖/切换报告/断开清空、未知方法及缺失方法。
不要为填满表格而添加尚未执行的 C3 或延迟结果。

## 7. 与 C 其他收尾的关系

当前本地 G1 闭环证据见 [收尾索引](C_LOCAL_CLOSEOUT.md)。本轮用户指定的
第一版规则对照优先做 C-E1→E3，随后与前端联合完成 C-E4→E5。
长时墙钟运行、日志/检查点保留及云链路独立排队，不阻塞只读离线结果查询。
本计划不是 G3/ML、真实设备效果或最终竞赛验收的放行记录。
