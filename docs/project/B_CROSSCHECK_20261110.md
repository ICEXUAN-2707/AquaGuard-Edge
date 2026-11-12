# B 部分交叉自检｜2026-11-10

结论：现有 B-EVAL-001 可作为“8 场景仿真规则原型”的联调数据。
源算法回归、独立计数核对、原生检查点回放与 C 历史工件适配均通过。
本轮发现并修复两项包一致性校验缺口；未修改 B 算法、标签、已有结果或 C 分支。
这属于同一代理的自动化交叉检查，不代替 B Owner 审核或独立人工验收，不放行 G3。

## 1. 审查基线

- 本地及已推送前端/交接包基线：b341c0c。
- 远端 main：ad40d93；B 分支 pr/b-algorithm-validation：fdade70。
- 当前工作树中的 SP-03、SP-03-features、SP-04 与该 B 分支无文件差异。
- B-EVAL-001：b-synthetic-8-478d2679798cfec3，8 trial、5 配置、3 正例/5 负例。
- C 兼容核查固定在 48de234beb5f1e2bad2936d4fdc3a129e4925941，
  不代表 C 分支随后新增提交也经过本轮审核。
- 其他成员尚未提交/同步的成果不计入。未切换或修改其他工作树。

## 2. 本轮实际执行

| 范围 | 本轮结果 | 本地证据 |
|---|---|---|
| M3 对齐/流式/边界 | 42 passed / 1.09s | audit/b-crosscheck-m3-20261110.xml |
| M4 特征/检查点 | 43 passed / 1.61s | audit/b-crosscheck-m4-20261110.xml |
| M5 规则/原始评估 | 54 passed / 3.91s | audit/b-crosscheck-m5-20261110.xml |
| 规范化包/破坏性副本探针 | 14 passed / 7.22s | audit/b-crosscheck-package-20261110.xml |
| 独立交叉脚本 | 54 项断言 PASS | audit/b-crosscheck-20261110/result.json |

各模块在独立 Python 进程中运行，避免同名模块导入污染。不将历史测试数累加为完成度。
独立脚本核对包记录的 B 源文件 SHA256、重新运行原 evaluate、独立六分类计数、
召回/拒判分母、逐 trial 原始观测→原生 M4 restore→M3 重算、不可区分反例，
以及固定 C 适配器是否逐值保留 records/metrics 和 simulation 来源。
C 检查只覆盖本地受控导入，不是 HTTP/浏览器集成或云验收。

## 3. 发现与处置

| ID | 级别与状态 | 事实、影响与处理 |
|---|---|---|
| BC-01 | P1，已修复 | 删掉规范化 methods 中一个方法并更新文件哈希，旧 verify 仍 PASS。现在要求原始/规范化方法清单完整且无重复。 |
| BC-02 | P1，已修复 | 修改 trials 中的标签并更新哈希，旧 verify 仍 PASS。现在核对 trial 标签/操作/参数、数据集计数及摘要、观测、检查点、预测引用和审查案例。 |
| BC-03 | P1，待 B 推进 | 原 evaluate.metrics 在空集和无正例集合下均抛 ZeroDivisionError。当前固定 8 场景不触发，但后续 split/子组评估会遇到。应为空集给明确拒绝/状态，无正例召回用 null+原因，不补 0。 |
| BC-04 | P0 评审，待确认 | 原 B0/B1/B2 与 C0/C1/C2 的映射、任务/标签解释仍待 B Owner 确认。保持原 ID，不能代签。 |
| BC-05 | G3 缺口，未完成 | 8 个手工开发场景无 held-out split、无 C3、无真实延迟或泛化证据。这是范围限制，不是通过单测即可消除的缺陷。 |

BC-01/02 初始复现副本：audit/b-crosscheck-probes-20261110。
新测试还覆盖重复方法、错误样本数、观测误改、审查标签误改，并保留已有哈希/覆盖/路径测试。
BC-03 探针：audit/b-crosscheck-20261110/source-metric-boundaries.json。

本轮仅增强脚本及测试，已发布评估包的原始数值与字节不变。
旧报告 builder_sha256 对应生成时构建器，不替换为本轮校验器摘要。
这些检查证明内部一致性和与本次源基线对应，不提供数字签名或来源授权。

## 4. 对结果的解释

- B0_flow：TP 3、FP 4、拒判 0；B2_10s：TP 2、FP 1、正例拒判 1、负例拒判 2。
- B2_10s 在这组数据中减少误报，但部分结果转为拒判；不能称为最优或泛化提升。
- positive_recall_all 的分母包含全部 3 个正例，正例拒判不可从分母剔除。
- FP 是 trial 级候选判断，不是 M6 事件误报或每小时误报。
- left20 与 hidden-person 的观测完全相同、操作标签不同；该反例必须保留。
- 候选情境不能表述为已证明实际无人。短暂离开/未来返回等标签口径需在 B 评审中说明。
- 合成 DEVICE_SYNCED 与固定逻辑发布时间，不证明真实时钟同步或实测响应延迟。

## 5. C 已有实现与接口边界

C 的 48de234 已提供：

- GET /api/evaluations/{evaluation_id}
- GET /api/experiments/{trial_id}/evaluations
- 受控 CLI 导入、严格 legacy DTO、记录/计数/比例校验。

本轮将本包 raw/comparison.json 交给固定版本的 load_legacy，验证导入结果与原记录/指标一致。
无需重新开发另一套同义 API。现接口消费 legacy 结果，不会自动带上本规范化包全部版本和数据摘要。
现有 relation_type=reference 只代表参考报告，不能在页面写成“当前 MQTT trial 的实测性能”。
完整 B 元数据、C3 或新指标仍须协商后续报告版本，不能静默塞进固定 legacy 字段集合。

## 6. 复现

使用现有应用环境，分目录独立运行 pytest，并为 basetemp 指定全新目录。
交叉脚本：

```powershell
python scripts/build_b_evaluation_package.py --verify deliverables/B-EVAL-001
python -m pytest tests/delivery/test_b_evaluation_package.py -q -p no:cacheprovider
python scripts/crosscheck_b_evaluation.py --output audit/new-b-crosscheck --c-ref 48de234beb5f1e2bad2936d4fdc3a129e4925941
```

后续任务与依赖见 [B 后续推进计划](B_NEXT_STEPS_20261110.md)。
