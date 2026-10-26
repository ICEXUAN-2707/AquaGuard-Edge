# 水知安 V0.6｜合同与八模块业务本源资料包

1. 优先阅读 `00_Contracts_V1.1_深化规范.md`；随后按工作线阅读模块设计。
2. `01_Contracts_V1.1_字段接口与自动化测试.docx` 是便于审核的排版版；权威机器可编辑版本为 Markdown + contracts/*.schema.json + tests/。
3. `02_M1-M4_详细业务基线.docx`、`03_M5-M8_详细业务基线.docx` 为统一组内阅读版。八份模块独立Markdown是各自开发的本源文档。
4. Python依赖：`pip install pytest jsonschema`；运行 `python -m pytest tests -q`。
5. 初始自动化只有 JSON Schema 结构烟雾测试；业务行为测试在 `tests/BEHAVIOR_TEST_MATRIX.md` 标明，必须随着对应模块代码实现而落地。不得将设计文档等同于实测代码。
6. 本版依据已附着的 V0.5 四份文档和五项冻结修订；真实仓库、ESP32硬件和 IoTDA仍待Gate验证。
