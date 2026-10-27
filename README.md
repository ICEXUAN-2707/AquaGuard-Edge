# 水知安 AquaGuard Edge

基于水流、水接触、人体存在三源时序融合与端边云协同的异常监测项目。D0 审计已完成，现已建立 I-001 本地 API 与前端运行基线；目前只有健康检查及连接检查页，尚无传感、事件或固件功能。仓库为私有仓库。

## 本轮交付

- [文档导航与双线执行入口](docs/README.md)：按审计、契约评审、Spike 和集成资料分类，并列出当前先后关系。
- [A 组员任务单](docs/spikes/A_任务单.md) / [B 组员任务单](docs/spikes/B_任务单.md)：可直接分发给零基础组员的操作步骤和验收要求。
- [组长分发话术](docs/spikes/组长分发话术.md)：可复制到组员聊天中的任务说明。

- [仓库审计](docs/audit/REPO_AUDIT.md)：实际资产、技术栈、测试和证据索引。
- [能力差距](docs/audit/GAP_ANALYSIS.md)：M1–M8、Gate 与实验缺口。
- [契约符合性](docs/contracts/CONTRACT_COMPLIANCE.md)：V1.1 冲突和可复现探针。
- [契约修订候选](reference/reference_02/00_Contracts_V1.2_修订候选.md)：`schema_version=1.1` 的字段与联合决议草案。
- [契约验收门槛](docs/contracts/CONTRACT_ACCEPTANCE.md)：C0–C5 放行标准、命令和未完成项。
- [依赖风险](docs/audit/DEPENDENCY_RISKS.md)：许可、环境、SDK 和三人协作风险。
- [开发计划](docs/project/DEVELOPMENT_PLAN.md)：优先级、Issue、依赖、验收命令。
- [IoTDA 集成计划](docs/integration/IOTDA_INTEGRATION_PLAN.md)：最小路径与云端前置条件。

## 重现本轮审计

在仓库根目录用 PowerShell 执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r audit/requirements.lock.txt
.\.venv\Scripts\python.exe audit/run_audit.py
```

该脚本读取 reference，输出审计证据，不修改参考文件。原有测试单独运行：

```powershell
.\.venv\Scripts\python.exe -m pytest reference/reference_02/tests -q
```

历史 D0 审计结果为 19 passed，另有 18 个探针记录当时 `schema_version=1.0` 的缺陷；这些证据保留在 `audit/evidence/`。2026-10-27 候选版的最新结果为结构测试 45 passed、DTO/API 与启动测试 32 passed；执行命令与完成边界见 [契约验收门槛](docs/contracts/CONTRACT_ACCEPTANCE.md)。

## 开发路线

先完成 V1.2 契约候选版的 A/B/C 会签与 C0–C2 门槛，再开发模拟输入→规则→唯一事件→SQLite→本地页面的纵向闭环；随后验证真实采集、实验与轻量 ML，最后完成真实 IoTDA 回执与断云补传。

当前并行执行两条线：契约会签以 V1.2 候选规范的 D1–D5 为议程；技术验证按 A（SP-01/02）、B（SP-03/04）、C（SP-05/06）分派。Spike 只提交证据和改进建议，候选 Schema 的正式冻结仍需 A/B/C 会签。完整目录见 [docs 导航](docs/README.md)。

V1.1 深化规范与五项 ADR 是历史基线；当前机器文件已按 [V1.2 修订候选](reference/reference_02/00_Contracts_V1.2_修订候选.md) 更新。候选版尚未完成 A/B/C 联合会签，不能宣称正式冻结；残留实施门槛见 [契约验收门槛](docs/contracts/CONTRACT_ACCEPTANCE.md)。

## 本地 API 基线

上游候选源、许可核查和运行栈决策见 [I-001 核查记录](docs/project/UPSTREAM_REVIEW.md)。在仓库根目录执行：

```powershell
python -m venv .venv-app
.\.venv-app\Scripts\python.exe -m pip install -r requirements-app.lock.txt
$env:AQUAGUARD_DEVICE_ID = 'home01'
.\.venv-app\Scripts\python.exe -m edge
```

打开 `http://127.0.0.1:8000/health`，按 Ctrl+C 停止。启动验收：

```powershell
.\.venv-app\Scripts\python.exe -m pip check
.\.venv-app\Scripts\python.exe -m pytest tests/smoke/test_startup.py -q -p no:cacheprovider
```

前端连接检查页可在另一个终端启动：

```powershell
cd web
npm ci
npm run dev
```

`npm run build` 已通过。连接检查页不是传感或事件业务页面。

## 许可状态

当前未授予本项目开源许可证；参考资料保留原样。已找到一个高度吻合的 Smart Hydro Alert 候选仓库并固定所检提交，但其被检文件列表未包含 LICENSE/NOTICE，原资料也未给出 URL 来证明其身份。本仓库采用自建基线，尚未导入其代码；细节见 [I-001 核查记录](docs/project/UPSTREAM_REVIEW.md)。密钥、真实数据库与本地环境不提交。
