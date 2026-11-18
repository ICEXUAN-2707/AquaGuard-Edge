# PR #12 剩余内容处置（独立于集成候选）

原 head abe27a7e35e72a620c22db270e37a8a6e9649c37；禁止整批 merge，特别不能用旧分支 B 文件覆盖 main 的冻结版本。

1. 只读分析/存储盘点：由 #14 独立审查并装配，不重复提取原 #12 旧版本。
2. 调度/进程监督：由 #15 独立审查并装配，保持默认 preview；未注册/启动任务。
3. 诊断：从 .review-pr12-diagnostics-20261117 单独提取，基于 ec08881；2026-11-18 补修栈日志P2（ef63a67）后已合入集成候选11ecbb8，合并后235项回归通过。详见 DIAGNOSTICS_INTEGRATED_20261118.md。此前独立切分cc63638记录保留为历史。
4. checkpoint 优化：从诊断批次移除 verification_scope 导入/包装，不修改 SP-03-features/src/checkpoint.py。原 save/restore 保持每次验证；新测试确认单次发布 5 次独立计算，没有缓存。若以后确要该优化，另行版本化来源清单、标签/模型/报告绑定，重建复验 B 工件与差异，不可关闭 REQUIRED_SOURCES 校验。
5. runtime_endurance.py、benchmark_journal.py 和长时执行用例：不纳入本批；还需要预算、授权、接口及清理单独审查。
6. 历史 docs/audit 和失败记录：保留历史，不把它当成拆分代码的当前 PASS。PR #12 里其他历史 B 代码/工件差异不迁入。

独立诊断改动：C api/context_events/online/projections/run/store/water、runtime_diagnostics，及诊断/暂停恢复测试。run.py 使用三方应用，保留 #13 mqtt_timing 参数和提交后时序 sidecar，没有用旧文件整批覆盖。

验证：独立诊断/暂停恢复/正式入口/Journal 20 项通过，更新到 ec08881 基线后加交叉接口的 37 项通过；B 67 项工件及 38 测试通过。各范围重叠不相加。证据在该独立分支 docs/audit/pr12-diagnostics-review-20261117/ 和 .local/diagnostics-rebased.xml。

这是已实现的可评审诊断批次，不是 checkpoint 性能改进通过、不代表长期可靠性或实际实验获批，也未合并回原 PR #12 或远端 main。
