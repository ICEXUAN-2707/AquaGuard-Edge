# 水知安依赖与协作风险

> 本文保留 D0 当时的审计事实。2026-10-26 后续开发找到了一个高度吻合的上游候选源并核查其提交与许可文件；最新结论见 [UPSTREAM_REVIEW.md](../project/UPSTREAM_REVIEW.md)。

状态等级沿用 REPO_AUDIT。风险优先级和缓解措施均为 INFERRED 建议；事实核查逐条注明 VERIFIED 或 UNVERIFIED。

## 许可与版本

|风险|事实与证据|优先级及处理建议|
|---|---|---|
|上游复用无依据|UNVERIFIED：Smart Hydro Alert 只有名称，无 URL、commit、LICENSE、依赖或源码。业务基线提取第150–155段、源清单|P0 I-001：取得准确仓库和固定 commit，核对许可证、NOTICE、前后端/固件及资源来源；无法确认时采用自建最小链，不复制未知许可代码|
|项目无开源授权|VERIFIED：初始资料中没有 LICENSE/NOTICE；`reference_manifest.json`|P1：本轮创建私有仓库，未替用户选择开源许可证。公开发布前确定自有资料和代码授权|
|原包依赖未锁定|VERIFIED：reference_02/README 第4条只给 pip install pytest jsonschema；无 lock、pyproject、requirements|P0：审计使用独立 .venv 并保存版本锁；业务依赖在 I-001 选择后另锁，不能把审计环境当生产环境|
|系统环境缺测试依赖|VERIFIED：首次系统 Python 报 No module named pytest；独立环境已19 passed|已缓解；`audit/evidence/environment.json`、pytest.log、pip_check.log；README 提供重建命令|
|业务环境未验证|UNVERIFIED：ESPHome/PlatformIO、Mosquitto、FastAPI/React、IoTDA、浏览器工具链版本和服务连通性|P0/P1 对应 Gate 验证；源清单没有构建/启动配置，不能给出已运行栈版本|
|SDK 文档许可口径不一致|VERIFIED：官方仓库显示 Apache-2.0，而 README §5 写 BSD-3；见下方官方来源|P1 I-010：固定 SHA，读取该版本 LICENSE 和依赖各自许可后再集成；不只根据 README 一句话选许可证|
|SDK 环境与本地不同|VERIFIED 为资料：官方 README 准备环境列 Python3.11.4、paho-mqtt1.5.0、schedule1.1.0、APScheduler3.10.4；本次审计 Python3.12.10|P1 I-010：独立兼容性 spike；不要盲升 MQTT 大版本，不安装全部可选 demo 依赖；Python3.12兼容性 UNVERIFIED|
|供应链漏洞未知|UNVERIFIED：pip check 只检查依赖一致性，未做 CVE 扫描；未取得生产依赖锁|P1 I-001/I-010：冻结实际依赖后检查公告与许可证，记录扫描日期、版本与例外；不把 pip check 写成安全认证|

官方资料核对日期 2026-10-26：[SDK README](https://github.com/huaweicloud/huaweicloud-iot-device-sdk-python)、[LICENSE](https://github.com/huaweicloud/huaweicloud-iot-device-sdk-python/blob/main/LICENSE)。以上仅为资料阅读，未把 SDK 下载或安装到业务环境。

## 当前审计环境锁

VERIFIED：Python3.12.10、pytest9.1.1、jsonschema4.26.0、SQLite3.49.1，完整解析依赖见 `audit/requirements.lock.txt` 与 `audit/evidence/pip_freeze.log`。`pip_check.log` 退出0；这不是跨平台验证或生产版本选型。SQLite 实际线程、WAL、锁等待和崩溃恢复仍 UNVERIFIED。

## 运行和设计风险

|风险|证据事实|优先级及后续验证|
|---|---|---|
|三路与未知值合同不可表达|VERIFIED；CONTRACT_COMPLIANCE CC01–04 与 contract_probes|P0 I-002 联合评审后才能固定 DTO|
|设备电平/校准/脉冲系数靠猜|UNVERIFIED；M1 §6–9、Spec提取第125段|P0 I-013 低压隔离台架，记录型号/引脚/实测电平/标定表；固件路线二选一|
|时钟、TTL 与窗口参数未经实测|VERIFIED 为默认参数而非实测；V1.1 §3；业务基线第108–129段|P0 I-004，W30/S5/L2 与TTL全配置化，记录时间映射与沉默截止|
|重叠窗导致模型评估泄漏|UNVERIFIED 真实数据流程；ADR-002、CT12|P1 I-011，先 trial 分组再训练；独立标签和split_manifest|
|双通路竞态和确认误关闭|UNVERIFIED 行为；ADR-003/005、CT06/07/14|P0 I-008，事务与唯一约束覆盖并发/重放，ACK不能改变物理恢复事实|
|进程退出丢同步数据|UNVERIFIED；M7 §5–9|P0 I-008/I-010，SQLite Outbox 为权威，SDK内存缓存不能替代；测试 SENDING 崩溃恢复|
|云资源或回执缺失|UNVERIFIED；V1.1 §6，M7 §9|P1 I-010，先 Mock 可控故障；真实权限/实例/设备和云侧日志到位再验收 C2|
|来源在下游丢失|VERIFIED：SensorObservation有source，Event/Transition无source/trial字段；schema properties|P0 I-002/I-008，联合评审通过来源关联/存储元数据保留隔离，不擅自给公共 DTO 加字段|

## 三人共享文件和接口

VERIFIED 为分工依据：Spec 提取第51–67段，A=M1/M2/M7，B=M3/M4/M5，C=M6/M8。A/B/C 是工作线占位，真实成员姓名和可投入时间 UNVERIFIED。以下路径为 INFERRED 未来边界，当前不存在业务目录。

|共享面|主责与评审|冲突风险与约束|
|---|---|---|
|reference/reference_02/contracts、主规范、examples、契约测试|A/B/C 联合评审|冻结文件禁止单人改名/枚举/单位；契约修订单独PR，不混入各模块功能PR|
|edge/adapters → alignment|A主责/B评审；SensorObservation|时间来源、去重键、坏包隔离；A不替B定义窗口语义|
|alignment → features → inference|B主责/A+C审边界|W/S/L、TTL、feature_version、缺失掩码、模型兼容；统一时间和特征实现供在线/回放复用|
|SafetySignal、SituationAssessment → decision|C主责/B+A评审|情境与安全可并存，唯一M6决定事件；两路不得各自创建事件|
|edge/storage、迁移、事务接口|A实现存储/C核准业务转换|高冲突文件指定A维护迁移、C调用事务接口；一次变更event/transition/outbox共同提交|
|API/OpenAPI、ACK模型、web生成类型|C主责/A+B评审|HTTP返回、错误和版本冲突共享；前端只能通过API修改状态|
|配置、依赖锁、Compose、CI、README|I-001建立单一维护者|同一PR统一版本与入口，模块PR避免同时改公共启动文件|
|experiments/标签、split、fixtures|B维护/C审页面与导出/A审采集|保留trial和来源；禁止UI自动把预测结果当真值|

INFERRED：使用短分支和小PR；提交前对公共契约与fixtures做差异检查。各线先消费固定DTO fixture，存储与决策通过事务接口联调，不各写一套共享数据库。依据 Spec 全局开发约定及 V1.1 §7。
