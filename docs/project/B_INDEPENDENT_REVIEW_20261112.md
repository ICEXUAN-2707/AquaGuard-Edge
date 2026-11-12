# B 独立复验记录（2026-11-12）

## 结论

固定集成候选 d1653cd 的 B 合成仿真软件复现与报告接口复验通过。可解除“B 软件正确性未经本轮重跑”的暂停；仅限以下已测范围。G3 整体、真实硬件效果、独立人员签署及 ML 收益均未放行。本记录由 Codex 执行，不代替人员 Reviewer 签字。

## 版本与方法

刷新 origin 后：main=ad40d93，集成=d1653cd，B 实验套件=ce2ee65，B 指标/分组数据=a3f1279。两条 B 提交均已包含在集成候选中。使用新建的 detached 工作树 .b-independent-review，Python 使用父目录既有 .venv-app；未修改算法、阈值、历史报告或其他工作树。未新装依赖，环境隔离不等同于全新机器安装复验。

## 本轮实际执行

在独立工作树根目录，以 ../.venv-app/Scripts/python.exe 执行：

```text
-m pytest spikes/SP-03/tests spikes/SP-03-features/tests spikes/SP-04/tests tests/contracts tests/smoke tests/delivery -q -p no:cacheprovider --junitxml=audit/b-independent-20261112/regression.xml
spikes/SP-04/experiment/run.py --output audit/b-independent-20261112/r07
scripts/build_b_sim_dataset.py --verify deliverables/B-SIM-001
-m pytest spikes/C-business/tests/test_evaluations_r07.py -q -p no:cacheprovider --junitxml=audit/b-independent-20261112/report-api.xml
audit/b-independent-20261112/check_report.py
```

- 管线/契约/启动/交付范围：262 passed，195.64 秒。
- R07 报告消费接口专项：9 passed，4.97 秒。不将其数量外推为全系统验收。
- R07 重建：34 trial、17 场景族、136 窗口，在线/离线不一致为 0。
- 缺失模型与版本不匹配两种回退：各 17 个评估 trial，均与 C2 一致。
- 新旧报告 metrics、trials、online_offline、fallback_check 完整对象相等；顶层变化仅 model、reproduction 元数据，数值与逐 trial 结果无漂移。见 comparison.json。
- B-SIM-001 自校验 PASS：72 trial、216 窗口标签、5422 观测，train/validation/test=36/18/18；training_complete=false。

证据保存在该工作树 audit/b-independent-20261112/：两份 JUnit XML、重新生成的 R07 全部工件、比较脚本及 comparison.json。原历史证据未覆盖。

## 口径核对

- R07 按 trial 聚合而非重叠窗口累计；召回分母保留拒判正例，误报率分母保留拒判负例；证据不足的 unknown-required 样本另列，不混入可判定样本。
- 旧 evaluate.py 与 R07 experiment/metrics.py 是不同评估入口，不应混用方法名或分母。前者边界回归已在本轮 SP-04 测试范围执行。
- 静态检查 train_shadow 仅使用 train 且 expected 非 unknown 的样本；模型使用固定传感特征允许清单，水接触特征被排除。未发现该入口使用 eval 标签训练。
- R07 固定场景各使用训练/评估种子，不能称为未见场景族泛化。B-SIM-001 则是另一套分组数据准备，不能拿其 72 trial 宣称 R07 已完成扩展训练。
- R07 报告版本为 b-exp-report-v1，C 消费适配专项通过；这不等于浏览器新一轮验收。

## 结果边界与下一步

可判定的 20 个 trial 中，C0/C1/C2/C3 的 FP 分别为 10/2/0/0，TP 均为 8；其余 14 个证据不足 trial 另列。C2/C3 在可判定范围同分，不能宣称 ML 优于规则。人员漏检、迟到等反例仍保留，不能把 0 误报写成全场景无误报。10 秒延迟是仿真决策延迟，不含真实采集和网络。

下一步可开展同版本软件闭环与浏览器人工验收；报告中将“B 待复验”更新为“合成仿真限定范围复验通过，真实效果待验”。B Owner 后续确认标签/分区并执行 B-SIM 独立训练评估；硬件仍在制作，真实日志、标定、长期运行与真实云验收继续保留。C3 继续影子运行，不接管水接触安全路径。
