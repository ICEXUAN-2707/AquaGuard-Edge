# MQTT 资源、OS 时钟与观测预算

本批基线 038cf96，仍在 PR #13。它保留既有离线 simulation_test 云 worker、MQTT 阶段业务断言与 ACK 汇总，新增实际运行前的观测配置。未运行 broker、计划任务、长时或真实云实验，没有合并 main。

|文件|改动及边界|
|---|---|
|scripts/mqtt_runtime_observation.py|通过保留的 Windows Popen 句柄读取各自有直属子进程 RSS/峰值 RSS、累计 CPU、优先级和创建 FILETIME；不按 PID 重开句柄。按 name/PID/创建时间区分进程实例，PID 重用不混合。失败记录 available=false，不补零；不覆盖孙进程总资源|
|同上：OS 时钟|GetTickCount64 与 QueryUnbiasedInterruptTimePrecise（或非 Precise 回退）配对，比较阶段内含/不含低功耗时间的增量。缺失、来源变化或反向时钟为未知；保留原始值。记录 50ms 量化容差。差值是 OS 排除时间证据，不单独认定 Modern Standby 或 503 根因|
|同上：assess|基于原计划时长/间隔固定 expected_samples，计数覆盖率与阶段首尾/中间最大观测空档；实际超时不改变计划分母，但计入尾部空档。汇总采集耗时与进程资源；不把缺失指标作为 0|
|scripts/prepare_mqtt_protocol.py|支持 --thresholds JSON 文件，将显式预算固化进 plan.json；不自定项目性能标准。缺少预算保留 observation_thresholds=null，计划仍可准备，但无观测预算通过结论|
|scripts/mqtt_local_backend.py|每次采样记录活动自有进程的资源与 OS 时钟；shutdown 后无活动进程并不伪造资源指标。没有依赖尚未合并的 PR #15，后续集成可再归并共用原语|
|scripts/mqtt_protocol_runner.py|记录采集耗时、阶段偏移与 OBSERVED 收据/observation_checks。正常连续期显式预算下，VIOLATED/INCOMPLETE 会终止后续阶段并执行清理。其他故障/启动/退出阶段保留观测结论，不能把正常门槛无区别套用。采集耗时计入间隔，不为每轮额外累计固定等待；不补采错过的历史记录|
|tests/delivery/test_mqtt_runtime_observation.py|虚拟低功耗时间/尾部缺口、原计划分母、缺指标/反向时钟、PID 重用、无预算、非法预算、Windows 原生时钟及短空白子进程测试|
|test_mqtt_protocol_runner.py、test_mqtt_protocol_plan.py|补充预算满足、缺证据、超预算的执行分支及无效预算在创建输出前拒绝|

## 预算配置契约

JSON 必须显式包含以下五项，不接受布尔值、NaN/inf、缺项或多余项：

|字段|含义与有效值|
|---|---|
|max_sample_gap_seconds|允许的观测空档，正数，秒|
|min_coverage_ratio|样本数/原计划样本数门槛，(0,1]|
|max_os_excluded_seconds|允许的 OS 排除时间，非负数，秒；检查时额外容忍声明的 50ms 量化误差|
|max_collection_seconds|单次采集耗时上限，正数，秒|
|max_process_rss_bytes|每个观测进程的 RSS 上限，正数，字节，不是总机内存预算|

这些数值应在实际实验前，依据机器条件与作品目标显式确定。本批没有把测试夹具中的数字当成已批准阈值。PREPARED/COMPLETED、局部 SATISFIED 均不能改写整体 acceptance_passed/long_run_acceptance=false。

## 验证与剩余内容

首批专项 41 项通过（包含 Windows 原生只读时钟及数秒空白子进程）；最终组合离线回归 172/172 通过（41.07 秒），见 docs/audit/offline-worker-20261117/observation-regression.xml。两组范围重叠，不相加。这些是软件测试，不是实际 MQTT、容量或一小时实验结果。

资源/OS/覆盖/预算现已具备代码和离线测试，仍需在恢复后的实际 MQTT 短联调中验证。软件收口还缺 checkpoint 引用/增长、publisher 到业务消费的端到端延迟、完整依赖/broker 版本锁及阈值选择，然后才进入固定版本长时验证。PR #12 的 checkpoint 与 B 冻结源冲突、PR #12–#15 的独立审查/合并，以及 D1/D3/D4 实物、真实云、真实 trial 和比赛材料缺口不因本批消失。
