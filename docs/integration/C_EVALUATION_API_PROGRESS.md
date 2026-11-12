# 第一版仿真规则对照：只读接口增量

日期：2026-11-10。依据 C_SIMULATION_RULE_COMPARISON_PLAN_V1 和前端交接提案。

## 已实现

- `evaluations.py`：独立 report_schema_version=1 严格 DTO，保留 B 方法原名，
  二元目标、逐 trial 标签/预测、六类计数及比例分母；未知指标不补 0。
- 受控本地 CLI 导入 B R05 comparison.json；校验目录边界、2 MiB 上限、
  重复 JSON 字段、非有限数、标签/预测布尔类型、trial 唯一性、完整方法集合、
  计数和比例。校验重算只用于核对，不替换 B 发布的原指标。
- 同库 evaluations/experiment_evaluations 两表，报告与关联原子提交；
  同 ID 同内容幂等，异内容冲突，跨来源关联拒绝。
- `GET /api/evaluations/{evaluation_id}`：独立只读报告，沿用 Bearer。
- `GET /api/experiments/{trial_id}/evaluations`：显式 reference 关联，
  未关联为空列表，未知 trial/evaluation 为 404；原 ExperimentResult 1.1 不变。
- 不提供 HTTP 上传/计算/训练接口，不读取浏览器指定路径，不触碰告警/Outbox。

当前为历史工件适配 `b-r05-legacy-v1`，不是最终 B 交接格式已经冻结。
供联调的独立 Schema 与真实适配示例位于 `docs/contracts/evaluations/`
的 `report-v1.schema.json`、`rules-r05.example.json`；示例由当前 B 历史工件生成，
不含人为添加的 ML/延迟结果。嵌套来源信息仍为 legacy 元数据，后续 B 格式需另行细化。
生成时间、评估代码 SHA、完整数据集 hash、延迟、ML 缺失均公开；文件 SHA
仅证明原报告内容。关联只开放 reference，不接受未经证据核对的 reproduction。
一份报告自带 B trial 清单；第一版关联粒度为整份报告，不含逐 trial 复现绑定。

## 复现

已有独立业务库可执行：

```powershell
..\.venv-app\Scripts\python.exe spikes/C-business/evaluations.py --db audit/your-run/business.sqlite --root spikes/SP-04/evidence/r05 --report spikes/SP-04/evidence/r05/comparison.json --evaluation-id rules-r05
```

若需关联，另加 `--experiment-id mqtt-trial`，前提是该库确有此 simulation
实验记录。此关联只表示参考；没有关联也能按 evaluation_id 独立读取报告。
API 路径分别为 `/api/evaluations/rules-r05` 与
`/api/experiments/mqtt-trial/evaluations`，使用已有服务和 Bearer 凭据。
CLI 导入与在线服务写入需按当前单实例原型运行边界安排，禁止替换运行中的数据库。

## 验证与下一步

独立 DTO/API/原投影回归 22 passed / 3.48s：audit/c-evaluations-dto-final.xml。
首轮坏报告测试因 Windows 默认 GBK 读 UTF-8 失败，已修正，未改报告值规避失败。
完整回归另见最终 XML；晚加 DTO 后的变化由上述专项覆盖。
完整 C-business/SP-06/contracts/smoke 回归：294 passed / 214.74s，退出 0，
`audit/c-evaluations-final.xml`。与 22 项专项范围重叠，不相加。
`git diff --check` 通过。未执行新结果页面的浏览器验收，不声称前端已接入。

下一步为 B 版本化工件确认、前端结果表与异常状态接入、真实浏览器同轮展示和
新增结果纳入证据导出白名单。本批不宣称页面或完整 C0–C3/ML 已实现。

## 完整 C0–C3 / ML 差距

M5 规定 C0 单水流阈值/C1 多源即时/C2 时序规则/C3 ML。
这些编号不要与本地/云/联系人确认级别或契约 Gate 编号混淆。

| 工作包 | 当前 | 还需开发/补证 |
|---|---|---|
| 三个规则基线 | B0/B1/B2 原型和 8 合成场景已运行 | 明确 C0/C1/C2 映射、统一任务/数据/版本和配置，不直接改名充当完整实验 |
| 数据/标签/分区 | 手写合成操作注释，有不可区分反例 | 带版本观测/标签/trial 清单；独立 trial 分组 split；训练/调参/测试隔离 |
| C3 训练 | 未发现实现 | 特征预处理、训练 CLI、模型与版本/配置产物、可复现随机种子 |
| C3 推断与降级 | 规则与质量门控已有 | 模型加载/版本验证、UNKNOWN、缺模型/错版本回退 rules；不替代 water 快路 |
| 统一评估 | 已有二元计数、拒判和正例召回 | 同一任务/分区的 C0–C3 评估；适用时 F1、实测延迟、样本数/分母及失败例；模型卡 |
| C 展示与验收 | 本批只读结果/参考关联 | 版本化 B 报告接入、方法表/限制/反例、同轮 API→页面→导出及跨报告状态测试 |

结论：规则基础已在，但完整 ML 实验链路尚未建立，不宜给单一完成百分比。
即使先完成合成数据训练与展示，也只能称仿真 ML 可行性；真实效果需要独立
实测数据和测试集。保留无收益或表现更差结果，不能承诺 ML 必然优于规则。
