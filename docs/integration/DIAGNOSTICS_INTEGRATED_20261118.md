# 诊断 P2 修复后集成记录

本次完成诊断分支到集成候选的合并，不修改远端 main。原候选 f897320；诊断修复 ef63a67；实际合并代码提交 11ecbb8409cc0463ce78be46d9581e5e832d5aaf。

## 修复与验证

- run.py 栈日志由覆盖改为追加，启动记录 UTC/PID，关闭仍取消 watchdog 并释放句柄。
- 新回归在应用生命周期中真实调用 faulthandler.dump_traceback，连续启动/退出两次，验证原始字节保留并追加新记录，没有等待30秒或启动实际 MQTT。
- 诊断、暂停、Journal、运行时、投影及水事件专项47项通过。新增测试初轮因 Windows CRLF 与 LF 常量比较失败，已按实际原始字节作为基线，首次报告保留。
- 合并后串行复跑原集成227项范围，加诊断与暂停测试，235项通过，0失败/错误/跳过（89.39秒）。范围重叠，不与47相加。
- 39个B冻结源逐文件与 origin/main 比较，差异为空；未引入 verification_scope、checkpoint缓存优化或旧 runtime_endurance/benchmark 工具。

证据：docs/audit/p2-stack-preservation-20261118/diagnostics-final.xml、merged-regression.xml、merged-frozen.json。仅 .gitattributes 审计规则冲突，双方规则均保留，没有丢弃历史记录。

## 范围与后续

集成候选含 #14 只读工具、#15 通用监督、#13 离线装配/MQTT软件候选及独立提取的 #12 诊断。采用本候选或完整回移修复后复验，不能直接批准尚未含补丁的旧PR头。

本次不合入 main；下一步通过远端集成 PR 审查，再按用户明确的目标执行主线合并。源PR关闭/取代也在该次集成放行时处理。原PR #12中checkpoint优化、历史B差异、旧长时工具仍排除。

实际 MQTT、长时、真实云与最终作品验收未放行。历史正常模拟低覆盖失败根因未独立确认，不能以本批通过宣布主机或长期可用性问题已修复。日志追加不提供自动删除/轮转授权，恢复实验前仍需检查磁盘和采样条件。
