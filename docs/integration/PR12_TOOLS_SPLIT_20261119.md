# PR12 剩余批次 A：显式执行的离线工具

仅提取 runtime_endurance.py、benchmark_journal.py 与对应测试，不覆盖 main 已合入的调度、诊断、run.py 或 checkpoint。

观察工具必须 --execute；默认 3600 秒还必须 --allow-long-run，最长一天。预算和参数在建目录/启动进程前检查。Windows Job 限定本次进程树，保留持久收据，清理失败回退持有的进程对象；HTTP 不使用系统代理，SQLite 显式关闭连接。结果只给 COMPLETED/INCOMPLETE，acceptance_passed 与 long_run_acceptance 均为 false，不作为 MQTT/云或长期可靠性验收。

Journal 探测也必须 --execute，总预算最多 10000 次写入；它不是 MQTT 吞吐测试。默认调用拒绝且不创建输出。运行输出必须是新目录。

本批只验证代码：21 项工具/监督短测通过，包括启动失败不误报成功、默认门控与 3 条本地 Journal 小样本。未运行实际观察、broker、云、一小时或压力实验；实际实验继续暂停。

B 冻结工件 67 项与 38 测试通过，39 必需源未变。栈日志追加修复和主线默认预览调度器未覆盖。

复验：pytest tests/delivery/test_runtime_endurance.py tests/delivery/test_endurance_supervisor.py -q。必须匹配应用环境并将测试临时目录放有足够容量的工作盘。
