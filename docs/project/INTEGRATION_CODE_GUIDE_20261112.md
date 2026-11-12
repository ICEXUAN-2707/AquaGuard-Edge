# 集成代码说明与评审导航

本集成把仅有基线入口的 main 推进到可持续接收仿真数据、维护事件、展示四页工作台并导出实验依据的本地软件候选。main 基线 ad40d93；运行验证版本分别为 a6aab02 与 2b425f2；378723c 归档结果。后续本说明提交仅补文档，不冒充运行验证版本。

## 运行入口与数据链路

|文件|职责与评审重点|
|---|---|
|edge/__main__.py|命令行启动入口，将配置交给服务运行入口。|
|edge/app.py|装配应用与运行模式；区分 baseline、simulation、mqtt，保持默认基线与显式业务运行配置的边界。|
|edge/runtime.py|运行时生命周期、持续输入与业务调度装配；启动/退出与资源归属是评审重点。|
|scripts/demo.py|演示预检与启动：拒绝既有证据目录和占用端口，生成本机凭据，记录去敏版本元数据。B状态限定为SYNTHETIC_SCOPE_VERIFIED，硬件与云不放行。|
|spikes/C-business/run.py|本地业务服务及依赖装配，完整运行仍依赖仓库内spikes，不能仅复制edge目录部署。|
|spikes/C-business/online.py|在线观测推进B分析及独立水接触路径，维护当前快照和分析输出。|
|spikes/C-business/mqtt_journal.py|从SP-02持久Journal消费仿真观测；处理游标、时间水位、旧boot、迟到/过期输入及重启边界，原始输入保留可追踪。|
|spikes/C-business/b_bridge.py|对接B检查点/分析工件，保留来源和时效语义，不将历史工件伪装为实时读数。|

业务链：仿真或本机MQTT→持久Journal/在线输入→M3/M4/M5及独立水接触信号→事件/SQLite/Outbox→API→四页工作台。现有MQTT输入限定simulation，不代表硬件来源适配完成。

## 事件、存储、同步与报告

|文件|职责与评审重点|
|---|---|
|spikes/C-business/store.py|本地数据库持久化、事务和查询支撑；检查事件版本及幂等约束。|
|spikes/C-business/lifecycle.py|事件生命周期与关闭条件；确认知晓不会清除物理异常，恢复且已确认后允许关闭，复发建立新事件。|
|spikes/C-business/context_events.py|将情境输出连接到事件业务，维持分析与事件的边界。|
|spikes/C-business/outbox.py、delivery.py|待发送消息、投递调度与结果处理；本地pending、传输回执和业务送达分开表达。|
|spikes/C-business/api.py|认证的事件查询/详情/确认/关闭、live、assessment、sync、experiment和evaluation接口；拒绝不可用证据。|
|spikes/C-business/evaluations.py|离线报告导入和实验关联，区分legacy与新版本，reference不等同于当前在线trial结果。|
|spikes/C-business/evaluations_r07.py|R07版本/来源/模型摘要与指标一致性校验及只读消费；保留拒判分母、分区、失败案例。|
|spikes/C-business/export_evidence.py|打包可追踪证据与校验摘要；运行数据库和凭据不作为本轮公开归档推送。|

## 云适配与隔离原型

|文件组|职责与状态|
|---|---|
|cloud_config.py、cloud_mapping.py|云配置与消息映射；配置存在不等于真实设备接入验收。|
|adapters/base.py、client_protocol.py、mock.py|投递抽象、客户端协议与模拟实现，保留Mock边界。|
|adapters/iotda.py、iotda_auth.py、iotda_transport.py|IoTDA适配、鉴权与传输层实现；真实账号、设备及关联回执仍需独立验收。|
|adapters/paho_client.py、paho_reasons.py|Paho客户端封装与原因码处理；本地broker验证不等于真实IoTDA证明。|
|experiments/process_channel.py、process_frames.py、process_probe.py、parent_death_harness.py|进程通道、帧与父进程退出等隔离实验。仍为原型研究，不描述成已正式发布的生产连接器。|

## B实验与数据资产

|文件组|职责与边界|
|---|---|
|spikes/SP-04/experiment/config.py、manifest.py、scenarios_v1.json及sha256|固定实验版本、允许特征与场景清单。C3排除水接触特征。|
|experiment/generate.py、replay.py|按冻结操作脚本生成观测/标签并比较在线/离线，不用分类器输出制造真值。|
|experiment/methods.py、metrics.py|C0–C3方法对照及trial级指标；拒判正例保留在召回分母，证据不足样本单列。|
|experiment/ml.py、run.py、report.py|训练集拟合轻量树、影子推断、异常回退C2及版本化报告生成。小样本合成结果不支持真实泛化或ML收益声明。|
|spikes/SP-04/evaluate.py|既有评估入口的空集、非法值及分母边界加固；不能与R07入口混用报告口径。|
|scripts/build_b_evaluation_package.py、crosscheck_b_evaluation.py|B评估交付包构建、校验与交叉核对。|
|scripts/build_b_sim_dataset.py|生成/校验72trial分组数据，train/validation/test=36/18/18；数据准备不等于完成扩展训练。|
|deliverables/B-EVAL-001、B-SIM-001|版本化评估与仿真数据包；历史来源摘要不随新源码重写。|

## 四页工作台

|文件|功能与状态处理|
|---|---|
|web/src/c-main.jsx|请求轮询、凭据/设备上下文、页面装配；本次新增有界会话历史，切换凭据/设备清空，最多360条/30分钟。|
|web/src/c-navigation.jsx|实时总览、数据可视化、事件确认、实验诊断四入口。|
|web/src/c-overview.jsx|三源快照、情境、安全信号与同步状态，未知与正常分开显示。|
|web/src/c-analytics.jsx、c-analytics.css|新增覆盖率趋势、三源状态轨迹、事件处理分布、关键计数；5/15/30分钟切换及JSON导出。只展示页面会话数据，事件限最新100项，不宣称全量历史或流量数值曲线。|
|web/src/c-events.jsx|事件筛选/详情/时间线、确认/关闭及导出，明确确认与物理恢复的差别。|
|web/src/c-experiment.jsx、c-evaluation.jsx|运行trial查询、评估报告选择、对照/分区/案例与导出，reference明确标注。|
|web/src/c-state.js|ACK/关闭请求意图与响应顺序管理，避免不确定重试换键、迟到结果覆盖新查询。|
|web/src/c-request.js、c-display.js|请求和错误处理、标签/时间/证据年龄展示；无效时间不产生令人误以为正常的新鲜度。|
|web/src/c-workbench.css|工作台主样式及响应式布局；新增图表使用原生SVG，不增加图表依赖。|

## 验证、运行和回滚

- 构建：`npm ci --prefix web`，`npm run build --prefix web`。
- 管线：应用Python运行 `-m pytest spikes/SP-03/tests spikes/SP-03-features/tests spikes/SP-04/tests tests/contracts tests/smoke tests/delivery -q -p no:cacheprovider`，本轮262通过。
- R07 API：`spikes/C-business/tests/test_evaluations_r07.py`，本轮9通过。
- 前端状态/展示：`node --test web/tests/c-display.test.js web/tests/c-state.test.js`，6通过。
- `spikes/SP-02/src/verify_workbench.py --lifecycle --evaluation-report ...`：新目录本机MQTT、API及浏览器13项通过；需要已有Mosquitto、Playwright/Chromium和前端构建。
- `web/tests/analytics-acceptance.cjs`：图表、时间范围、导出、390px、断开清空和页面异常检查通过。冷启动先等待30秒窗口及轮询，首次20秒超时失败被保留。
- `tests/delivery/test_demo_launcher.py`：新增启动范围元数据断言，保留凭据不落档要求。
- `tests/smoke/test_simulation_runtime.py`及C-business各领域测试提供运行/存储/传输等专项；历史结果不混写为本轮全量C回归。

证据：docs/audit/integration-final-20261112/与B复验文档。用户已确认工作台和可视化人工验收通过，不代填人员独立签字。新增可视化无API/数据库迁移，可独立revert其提交；整批回滚保留共享提交历史并先备份运行数据。

剩余：实物制作/标定/来源适配、真实IoTDA关联回执与断网补传、长期运行、B扩展训练评估和最终材料。云未连接、Outbox待同步不代表云成功；本PR不自动放行G2/G3或合并main。
