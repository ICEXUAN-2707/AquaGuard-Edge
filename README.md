# 水知安 AquaGuard Edge

基于水流、水接触、人体存在三源时序融合与端边云协同的异常监测项目。当前为 **D0 审计阶段**，尚无可启动的业务服务、固件或页面。仓库为私有仓库。

## 本轮交付

- [仓库审计](REPO_AUDIT.md)：实际资产、技术栈、测试和证据索引。
- [能力差距](GAP_ANALYSIS.md)：M1–M8、Gate 与实验缺口。
- [契约符合性](CONTRACT_COMPLIANCE.md)：V1.1 冲突和可复现探针。
- [依赖风险](DEPENDENCY_RISKS.md)：许可、环境、SDK 和三人协作风险。
- [开发计划](DEVELOPMENT_PLAN.md)：优先级、Issue、依赖、验收命令。
- [IoTDA 集成计划](IOTDA_INTEGRATION_PLAN.md)：最小路径与云端前置条件。

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

本轮结果：19 passed；另有 18 个审计探针记录当前缺陷及新旧版本兼容情况，探针不是生产验收测试。详见 `audit/evidence/pytest.log` 与 `contract_probes.json`。

## 开发路线

先完成上游许可与固件路线核查、V1.1 契约联合评审，再开发模拟输入→规则→唯一事件→SQLite→本地页面的纵向闭环；随后验证真实采集、实验与轻量 ML，最后完成真实 IoTDA 回执与断云补传。

契约以 `reference/reference_02/00_Contracts_V1.1_深化规范.md`、同目录 schemas 和五项 ADR 为依据。内部冲突见符合性报告，须 A/B/C 联合裁决。D0 未修改这些冻结资料。

## 许可状态

当前未授予本项目开源许可证；参考资料保留原样。Smart Hydro Alert 只有名称，无已确认 URL、commit 或 LICENSE，尚未导入其代码。未来复用须先完成来源和许可核查。密钥、真实数据库与本地环境不提交。
