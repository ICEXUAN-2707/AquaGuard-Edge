# PR #12：诊断与 checkpoint 优化解耦批次

来源固定为 abe27a7e35e72a620c22db270e37a8a6e9649c37。本分支仅提取 C 诊断，不整批合并该 PR。

| 内容 | 本批处置 |
|---|---|
| #14 只读分析/存储工具 | 已在独立集成候选审查，不从旧 #12 覆盖 |
| #15 调度/监督 | 已在独立集成候选审查，不带旧版本覆盖 |
| C runtime_diagnostics、API、run、online、store、projections、context_events、water | 提取诊断插桩；run.py 三方应用，保留 #13 mqtt_timing 参数与消费 sidecar |
| online.verification_scope | 已移除，保持 checkpoint 原保存与每次完整重算逻辑 |
| SP-03-features/src/checkpoint.py 与缓存测试 | 不提取；属于优化阻塞项，后续若采用须新版本重建与复验 B 工件 |
| test_pause_recovery | 只提取 TTL/恢复不补造数据的功能测试，不提取缓存命中断言 |
| runtime_endurance.py、benchmark_journal.py、相关执行测试 | 继续单独待审；未加入本分支、不运行一小时/压力实验 |
| PR #12 历史 B 文件、工件与验收结果 | 不覆盖当前 main 已合并 B 工件；历史证据不充作当前通过 |

本分支与主集成候选独立，未纳入最终集成候选，也未合并远端 main。诊断不是性能优化成功或长时可靠性证明。

验证：诊断/暂停恢复/正式运行入口/Journal 组合 20 项通过；前批诊断/Journal/启动 19 项通过，范围重叠不相加。新增断言原 checkpoint 不提供 verification_scope，单次发布保持 5 次独立完整计算。

复现：应用环境执行 pytest spikes/C-business/tests/test_runtime_diagnostics.py spikes/C-business/tests/test_pause_recovery_decoupled.py spikes/C-business/tests/test_runtime.py spikes/C-business/tests/test_mqtt_journal.py -q。
实际源差异需与独立集成基线比较，不将旧 PR #12 中相对 main 的 B 文件差异误当成诊断依赖。

更新基线至集成代码候选 ec08881 后，诊断/恢复/正式入口/Journal 与监督/证据交叉组合 37 项通过；B 工件 67 项完整性与 38 项测试通过。证据 docs/audit/pr12-diagnostics-review-20261117/tests.xml。此分支仍单独保留，不纳入主集成候选。
