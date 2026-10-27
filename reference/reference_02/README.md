# 水知安 V0.6｜合同与八模块业务本源资料包

1. 先阅读 `00_Contracts_V1.1_深化规范.md` 历史基线，再阅读 `00_Contracts_V1.2_修订候选.md` 的覆盖决定；候选版尚待 A/B/C 会签。
2. `01_Contracts_V1.1_字段接口与自动化测试.docx` 是历史排版版，不代表当前 `schema_version=1.1` 候选合同。候选机器材料为 Markdown、contracts/*.schema.json、examples.json、scenario_s01.json、tests/ 和仓库根目录的 `edge/contracts/`。
3. `02_M1-M4_详细业务基线.docx`、`03_M5-M8_详细业务基线.docx` 为统一组内阅读版。八份模块独立Markdown是各自开发的本源文档。
4. 结构测试依赖 `pytest jsonschema`，DTO 语义测试依赖应用环境的 Pydantic；从仓库根目录按 `CONTRACT_ACCEPTANCE.md` 执行两层命令。
5. 当前自动化包括 JSON Schema 结构/反例和 DTO 单对象语义测试；业务行为测试在 `tests/BEHAVIOR_TEST_MATRIX.md` 标明，必须随着对应模块代码实现而落地。不得将设计文档或模型测试等同于系统实测。
6. 本版依据已附着的 V0.5 四份文档和五项冻结修订；真实仓库、ESP32硬件和 IoTDA仍待Gate验证。
