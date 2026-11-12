# 存储审计与Journal探针

新增scripts/audit_runtime_storage.py与只读引用测试；工具/启动器联合9项通过。对既有MQTT恢复库审计：270条observations、270次attempts、rejected=0；检查点6个/323587字节，发现1个显式已引用文件、0个缺失引用，另5个未观察到引用。后者不代表可以安全删除，deletion_authorized=false；外部导出和内存引用未穷尽。

新增scripts/benchmark_journal.py，默认分别创建300/600/1200条观测的新库。每条观测经现有normalize生成合法DTO；测量Journal.accept包含SQLite提交，不含网络、ACK或edge消费。输出每组累计入库时长及末100条均值/最大值。禁止覆盖既有目录。

本次入库总时长约10.96/13.97/36.35秒，末100条均值约36.27/21.25/73.40ms；非单调，不能根据单次结果拟合复杂度或证明吞吐退化。试验与simulation小时观测共享主机，调度、磁盘及其他负载会影响结果。静态审查确认core.Journal.accept每条新输入扫描并解析已有observations，因此大规模扩展风险仍应专项处理。

两项新增工具都不改现有业务库、Schema、Journal或检查点保留逻辑。下一批先独立重复更大Journal规模并量测ACK/消费lag，再审查索引化seq高水位兼容方案，不直接迁移或清理运行库。保留策略候选见docs/integration/STORAGE_RETENTION_DESIGN_20261112.md。

小时观测运行的是afa33c8基线；本轮审计与探针代码在独立进程执行，不进入被观测服务。运行环境并非隔离空载主机，小时结果只覆盖实际条件。
