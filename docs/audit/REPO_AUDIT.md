# 水知安 D0 仓库审计

审计日期：2026-10-26。审计对象为本工作区接收的 reference 资料包，不包含未提供的 Smart Hydro Alert 上游源码。任务依据：`reference/task_LoTDA_WaterMonitor.txt` 第一阶段及输出要求。

## 证据等级

- VERIFIED：本轮直接读到的文件事实或命令实测；文档写明某设计属于 VERIFIED 的“规范事实”，不代表功能已实现。
- INFERRED：由资料推导的设计建议、风险和开发估算，尚未实现。
- UNVERIFIED：需要上游源码、硬件、运行服务、实验数据或云账户才能判断。

所有六份报告沿用以上定义；表格状态作用于整行。证据中的 JSON 定位使用对象键或 probe 名；Word 定位使用 `audit/evidence/*.txt` 的段落序号，保留原始 Word 路径，不冒充页码。本轮完整提取正文与表格文本，未进行 Word 版式审查。

## 当前结论

|状态|发现|证据|
|---|---|---|
|VERIFIED|初始工作区只有 reference；不是已有 Git 仓库，没有业务服务可启动|初始命令 `Get-ChildItem -Force`、`rg --files reference`、`git status --short` 返回 not a git repository；源资产清单 `audit/evidence/reference_manifest.json`|
|VERIFIED|参考源文件共 32 个：7 docx、12 md、11 json、1 py、1 txt|`reference_manifest.json` 全表；`audit/run_audit.py` 的 manifest 生成逻辑|
|VERIFIED|真正可执行的原有代码只有 Schema 测试；九个 DTO schema 和九类黄金样例是合同资产|`reference/reference_02/tests/test_json_schema_contracts.py` 全文；`contracts/*.schema.json`、`contracts/examples.json`|
|VERIFIED|创建私有 GitHub 仓库 ICEXUAN-2707/AquaGuard-Edge|`audit/evidence/github_repository.json`：full_name、private、created_at、html_url|
|UNVERIFIED|Smart Hydro Alert 的许可、技术栈、Topic、可运行性和可复用代码|`audit/evidence/01_业务基线与冻结决议_V0.5.txt` 第150–155段；无上游 URL、commit、源码或许可文件|

## 实际目录与设计目录

|实际路径|内容|状态与证据|
|---|---|---|
|reference/reference_01/|V0.5 四份 Word、README、早期 JSON 示例|VERIFIED；manifest 对应路径|
|reference/reference_02/|V0.6 主规范、三份 Word、M1–M8 Markdown、九份 Schema、examples、测试与行为矩阵|VERIFIED；manifest 对应路径|
|reference/task_LoTDA_WaterMonitor.txt|D0 工作边界与六份交付要求|VERIFIED；文件全文|
|audit/|本轮新增只读审计脚本、环境锁和证据|VERIFIED；`audit/run_audit.py`，不包含业务模块|
|根目录六份报告、README、.gitignore|本轮新增审计交付与仓库导航|VERIFIED；对应文件|

INFERRED：`firmware/`、`edge/adapters/`、`edge/alignment/`、`edge/features/`、`edge/inference/`、`edge/decision/`、`edge/storage/`、`edge/cloud/`、`web/`、`experiments/`、根目录 `contracts/` 和业务 `tests/` 均是未来建议，尚未建立。依据 `audit/evidence/04_Spec_模块工程规格与Issue_V0.5.txt` 第8–10段与源清单。

## 技术栈与运行入口

|项目|当前事实|等级与证据|
|---|---|---|
|已运行审计环境|Windows 11，Python 3.12.10，SQLite 运行库 3.49.1|VERIFIED；`audit/evidence/environment.json`。SQLite 库存在不等于业务数据库已创建|
|已安装测试依赖|pytest 9.1.1，jsonschema 4.26.0；依赖一致性检查通过|VERIFIED；`environment.json`、`pip_freeze.log`、`pip_check.log`|
|设计中的端与边|ESP32、YF-S201、FC-37、LD2410C、Mosquitto、Python/Pydantic|VERIFIED 为规范；`modules/M1_感知采集.md` §5、`M2_消息通信与标准化.md` §5；UNVERIFIED 为设备与接入实测|
|设计中的应用和存储|FastAPI、React、SQLite；WebSocket 可选；MongoDB 仅可选兼容投影|VERIFIED 为规范；`M8_用户产品与实验平台.md` §5；Architecture 提取第113–128段|
|设计中的算法和云|规则、决策树/随机森林、华为 IoTDA 设备侧 SDK|VERIFIED 为设计；`M5_轻量AI情境识别.md` §3–5、`M7_事件持久化与华为云协同.md` §3–5|
|业务启动方式|不存在 app、package.json、固件构建清单、Compose、数据库迁移或业务依赖锁|VERIFIED；源清单。不能给出已验证的 uvicorn/npm/固件启动命令|

## 实际测试与静态审查的区别

VERIFIED：系统 Python 首次执行 `python -m pytest reference/reference_02/tests -q` 失败，原因 No module named pytest；随后创建本地 `.venv` 安装测试依赖，运行 `audit/run_audit.py`，得到 **19 passed**，退出码 0。持久证据 `audit/evidence/pytest.log`；环境锁 `audit/requirements.lock.txt`。当前可复现命令见 README。

VERIFIED：19 项由 9 个黄金样例、8 个错误版本、1 个缺 device_id、1 个多余 status 字段组成。依据原测试函数 `test_golden_example_valid`、`test_wrong_schema_version_rejected`、`test_missing_device_id_rejected`、`test_unknown_extra_field_rejected`。没有跨字段、时序、状态机、数据库、MQTT、API、浏览器或云端实测。

VERIFIED：另执行 18 个审计探针（13 个定向反例和5个旧样例兼容检查），结果保存在 `contract_probes.json`。这些探针记录接受/拒绝行为，不作为“18 个功能测试通过”。具体缺陷见 CONTRACT_COMPLIANCE。

UNVERIFIED：行为矩阵 CT01–CT16 尚无实现测试；硬件标定、网络故障、重启、模型指标、真实云端回执全部没有运行证据。证据 `reference/reference_02/tests/BEHAVIOR_TEST_MATRIX.md` 全文、源清单。

## 需求任务覆盖

|任务号|交付位置|结论等级|
|---|---|---|
|1 目录、栈、启动|本报告实际资产与运行入口|VERIFIED，业务运行 UNVERIFIED|
|2 许可、依赖、环境|DEPENDENCY_RISKS|已安装环境 VERIFIED；上游许可 UNVERIFIED|
|3 M1–M8 能力|GAP_ANALYSIS|静态实现范围 VERIFIED|
|4 字段、枚举、接口、DB|CONTRACT_COMPLIANCE|Schema 探针 VERIFIED；服务与 DB UNVERIFIED|
|5 测试分类|本报告测试部分及日志|VERIFIED|
|6 三人共享边界|DEPENDENCY_RISKS 协作部分|INFERRED，依据 Spec 分工|
|7 Issue、依赖、验收|DEVELOPMENT_PLAN|INFERRED 计划，未执行项逐一标注|
|8 IoTDA 最小集成|IOTDA_INTEGRATION_PLAN|官方资料 VERIFIED；真实连接 UNVERIFIED|

## 关键规范与证据索引

VERIFIED：完整阅读材料为 manifest 列出的 32 文件。V0.5 正文与表格提取见 `audit/evidence/01_业务基线与冻结决议_V0.5.txt`、`02_PRD_产品需求文档_V0.5.txt`、`03_Architecture_Contracts_V1.txt`、`04_Spec_模块工程规格与Issue_V0.5.txt`；V0.6 三份 Word 同名提取亦在该目录。Markdown 模块 §1–10 是模块设计本源；V1.1 Markdown §1–8 是字段、接口和事务依据。

VERIFIED：五项 ADR 在业务基线第89–107段以及 V1.1“已冻结原则”中，而非五个独立 ADR 文件。其含义依次为三轴分离、独立真值与 trial 分组、双路径唯一 M6、C1/C2/C3 分级验收、业务事务与同步状态分离。本轮未改变这些决议。
