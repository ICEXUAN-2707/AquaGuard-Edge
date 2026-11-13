# 墙钟运行观测第一批

基线main=2a04f74；分支feat/runtime-endurance-20261112。本批新增观测工具与专项验证，不修改事件策略、算法、数据库结构或保留/删除逻辑。

## 代码

- scripts/runtime_endurance.py：默认3600秒真实墙钟运行，独立目录/端口和临时凭据；采集健康与live状态、Windows进程树RSS、SQLite含WAL/SHM体积、检查点体积/文件数、事件/转换/Outbox记录数。凭据不写入元数据。输出run.json、samples.jsonl和result.json。
- Windows使用系统API观察虚拟环境启动器及子进程，不新增第三方依赖。非Windows内存明确为不可用。退出仅清理自己创建的进程树，并检查端口关闭；强制终止不证明优雅退出。
- 数据库以只读URI查询；结束后检查完整性及同设备/类型重复OPEN事件。前45秒是冷启动观察阶段，不计入稳态接口门槛。增长按实测端点计算，并单列稳态范围；数值只是描述，不能据短时斜率诊断泄漏或预测容量。
- tests/delivery/test_runtime_endurance.py：缺失库不创建、坏库识别、未知子进程内存不伪造为0、增长分母和存储分类测试。

## 本轮证据与限制

1. 初版526b509做180秒试运行：19次采样，稳态14次接口可用，完整性ok、重复OPEN=0；初版RSS只测到启动器，此内存值不用于业务资源结论，原结果保留。
2. 0da3810进程树版180秒：19次采样、稳态14次接口可用，完整性ok、重复OPEN=0；峰值RSS 62,246,912字节，末次SQLite 208,896字节、检查点3,090,363字节/26文件。只能说明短程行为，尚未证明长期有界。
3. 526b509独立MQTT recovery场景PASS，120.25秒；真实停报后过期、edge重启、新boot恢复通过，云未连接。无新增硬件证据。
4. 5951692做60秒自有进程树清理试运行PASS，后续端口查询未发现遗留监听；最终513d30b另加端口门槛和稳态增长并重新验证，结果以归档final/result.json为准。
5. 工具和启动器联合回归7项通过；前端构建通过。本批不重复无关算法全量回归。

以上不是小时级长期验收。原始数据库/检查点/日志仅本地保存，推送只含去敏元数据、采样、结果及JUnit。

## 复现

在完整仓库根目录、已安装应用依赖的Python环境执行：

```text
python scripts/runtime_endurance.py --directory audit/new-one-hour-run --seconds 3600 --interval 15 --port 8042
python -m pytest tests/delivery/test_runtime_endurance.py tests/delivery/test_demo_launcher.py -q -p no:cacheprovider
```

运行目录必须不存在，端口必须空闲。脚本前台持续运行，原始日志保留本地；未提供生产监控或自动清理服务。simulation模式不生成SP-02 Journal，其增长需要后续MQTT长时专项，不能用本轮SQLite数据替代。

## 下一批

先开展小时级墙钟基线，分别量测simulation和MQTT Journal；按检查点增长及实验asset_refs引用关系设计保留方案，保护恢复所需及已导出证据，增加磁盘不足/删除中断测试后再实施。暂停输入和重启继续保持独立场景与证据范围。
