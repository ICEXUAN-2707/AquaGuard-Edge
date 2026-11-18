# 诊断栈日志 P2 修复与合并准备

修复基线 cc63638。原问题：run.py lifespan 使用 open('w')，相同业务数据库的启动/重启会清空之前的栈证据。

修复：改为追加打开 .service-stacks.log，启动时追加 UTC/PID 分隔行并 flush；保持原路径、30秒诊断触发、关闭/取消流程和所有业务时钟语义。不删除或轮转历史文件。

新增回归 test_restarts_append_native_stacks_without_truncating_prior_evidence：预存历史字节，通过真实应用 lifespan 启动/退出两次，在每次 watchdog 注册时立即调用原生 faulthandler.dump_traceback（无30秒等待），验证旧内容保持前缀、第二次保持第一次全部字节并追加新栈、两个启动标记和资源释放。

最终诊断、暂停恢复、Journal、运行时、投影与水事件专项47项通过。证据 docs/audit/p2-stack-preservation-20261118/diagnostics-final.xml。初轮新增测试使用 LF 字符串与 Windows CRLF 原始字节比较而失败（其余46项通过）；改用写入后的实际字节作为基线，没有削弱历史字节保留断言，首次记录 first-line-ending-failure.xml 保留。

本次仅修复该 P2，未改变 B 冻结 checkpoint，未启动 MQTT、长时实验、计划任务或真实云。合并目标先为 review/integration-candidate-20261117；main 的进一步合并目标仍按用户明确回复执行。集成后需跑固定交叉范围，合并诊断不意味着引入 PR #12 缓存优化/旧执行工具，也不证明历史低覆盖事件根因已修复。
