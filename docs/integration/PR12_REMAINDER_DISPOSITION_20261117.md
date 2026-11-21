# PR #12 剩余内容处置（独立于集成候选）

## 2026-11-21 主线状态与准备复核

主线固定为0db5e605c3677a18c5be461b6ec5ec74f51e5577。PR #19/#20已合并，#12已关闭为被替代、未整批合并。可选缓存未接入既有B/C流程。

本次C盘可用约2.82GB，D盘约479.59GB；先前“C盘为0”是历史观测，不作为当前状态。空间已改善，启动前仍须复核。运行锁、端口和273秒基线阶段计划已重新核验，backend.preflight通过；未启动实际实验、broker服务、计划任务或云。预算未配置，仅用于基线采集准备，不给出性能验收结论。证据见docs/audit/acceptance-refresh-20261121/。

原 head abe27a7e35e72a620c22db270e37a8a6e9649c37；禁止整批 merge，特别不能用旧分支 B 文件覆盖 main 的冻结版本。2026-11-18更新：只读工具、通用监督及独立诊断已随PR #16进入main（f9d9858）；以下未纳入的优化/旧执行工具继续单独处置。主线依据见 MAIN_INTEGRATION_ACCEPTANCE_20261118.md。

1. 只读分析/存储盘点：由 #14 独立审查并装配，不重复提取原 #12 旧版本。
2. 调度/进程监督：由 #15 独立审查并装配，保持默认 preview；未注册/启动任务。
3. 诊断：从 .review-pr12-diagnostics-20261117 单独提取，基于 ec08881；2026-11-18 补修栈日志P2（ef63a67）后已合入集成候选11ecbb8，合并后235项回归通过。详见 DIAGNOSTICS_INTEGRATED_20261118.md。此前独立切分cc63638记录保留为历史。
4. checkpoint 优化：从诊断批次移除 verification_scope 导入/包装，不修改 SP-03-features/src/checkpoint.py。原 save/restore 保持每次验证；新测试确认单次发布 5 次独立计算，没有缓存。若以后确要该优化，另行版本化来源清单、标签/模型/报告绑定，重建复验 B 工件与差异，不可关闭 REQUIRED_SOURCES 校验。
5. runtime_endurance.py、benchmark_journal.py 和长时执行用例：不纳入本批；还需要预算、授权、接口及清理单独审查。
6. 历史 docs/audit 和失败记录：保留历史，不把它当成拆分代码的当前 PASS。PR #12 里其他历史 B 代码/工件差异不迁入。

独立诊断改动：C api/context_events/online/projections/run/store/water、runtime_diagnostics，及诊断/暂停恢复测试。run.py 使用三方应用，保留 #13 mqtt_timing 参数和提交后时序 sidecar，没有用旧文件整批覆盖。

验证：独立诊断/暂停恢复/正式入口/Journal 20 项通过，更新到 ec08881 基线后加交叉接口的 37 项通过；B 67 项工件及 38 测试通过。各范围重叠不相加。证据在该独立分支 docs/audit/pr12-diagnostics-review-20261117/ 和 .local/diagnostics-rebased.xml。

诊断批次已随PR #16进入main，没有回写原PR #12；checkpoint性能优化、长期可靠性与实际实验仍未放行。
