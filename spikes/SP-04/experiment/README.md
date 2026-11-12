# B 实验包（R07）

本目录实现“冻结仿真场景 + 在线/离线一致 + C0–C3 对照 + 统一报告”，不复制或修改既有 M3/M4/M5 算法。所有结果只适用于明确设定的仿真条件。

## 一键运行

在仓库根目录：

```powershell
.\.venv-app\Scripts\python.exe spikes/SP-04/experiment/run.py --output spikes/SP-04/evidence/r07
```

输出：

- `evidence/r07/report.json`：完整报告（版本、划分、指标、逐 trial 窗口、失败、不可区分、回退、在线一致）；
- `evidence/r07/trial_index.json`：实验页可用的轻量表；
- `evidence/r07/metrics.md`：指标定义与结果表；
- `evidence/r07/model_card.md`：C3 模型卡；
- `evidence/r07/reproduce.txt`：复现命令；
- `evidence/r07/scenarios_v1.json`、`evidence/r07/model/c3-model.json`：冻结清单与模型副本。

## 约束

- 标签来自 `scenarios_v1.json` 的人工操作时间线，`manifest.py` / `generate.py` 不导入规则、特征或模型；
- 修改场景必须同步 `scenarios_v1.sha256`，否则冻结测试失败；
- 模型缺失/版本不匹配必须回退 C2，不得伪造 ML 结论；
- C3 是影子推断：不发布 `SituationAssessment`，不进入 M6，不读取水接触特征。

## 测试

```powershell
.\.venv-app\Scripts\python.exe -m pytest spikes/SP-04/tests -q -p no:cacheprovider
```

详细设计与限制见 [R07 开发报告](../../docs/B/SP-04/R07_开发报告.md)。
