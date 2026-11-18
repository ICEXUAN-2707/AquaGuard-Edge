# PR #12 只读工具独立批次

基线 main=5f5bc94；源 PR #12=abe27a7。本批只提取下列文件，不带入运行时、checkpoint 优化、调度任务或历史验收工件。

|文件|用途|交付边界|
|---|---|---|
|scripts/analyze_runtime_observation.py|汇总已有采样中的 503、调度间隔与诊断耗时|缺失的采样间隔/暂停量为 null；无自动根因判定，无自动 PASS|
|scripts/audit_runtime_storage.py|以只读 SQLite 事务盘点表、显式 checkpoint 引用及可选 Journal 计数|显式关闭连接；没有观察到引用不等于可删除，数据库与目录非原子快照|
|tests/delivery/test_runtime_analysis.py|验证缺失诊断与实测零值的区分|不启动服务或实验|
|tests/delivery/test_runtime_storage_audit.py|验证引用盘点、数据库字节不变、缺失库不被创建|不删除 checkpoint|

命令（仓库根目录）：

```powershell
python scripts/analyze_runtime_observation.py <已有samples.jsonl>
python scripts/audit_runtime_storage.py --db <已有business.sqlite> --checkpoints <已有目录> --journal <已有journal.sqlite>
```

验证：以上两份测试共 4 项通过，证据 docs/audit/runtime-tools-20261114/tests.xml。拆分后在 main 基线运行，不依赖 PR #12 的运行时接口，也不改变 B REQUIRED_SOURCES。

本批可独立代码审查；没有合并 main。原 PR #12 中调度/运行时/缓存优化仍保留待拆分。长时实验、真实 MQTT/云端验收继续暂停。本批测试不证明当前可靠性达标。
