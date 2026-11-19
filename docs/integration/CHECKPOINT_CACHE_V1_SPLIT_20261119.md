# PR12 剩余批次 B：独立可选 checkpoint 缓存 v1

新模块 spikes/SP-03-features/src/checkpoint_cached_v1.py，标识 m4-verified-content-cache-v1。没有修改原 checkpoint.py，也没有改 C online.py 或现有 B 特征/训练/评估入口；默认流水线仍完整重算 5 次，原冻结清单和 B 模型报告均保留。

显式调用者才可使用 verification_scope/restore：作用域首次读取调用冻结 checkpoint.restore 独立验证，后续仍每次读取并检查内容摘要与文件名；只复用已验证内容，最多 4 个条目，返回深拷贝，按实际路径更新 state_checkpoint_ref。离开作用域销毁缓存；没有 scope 时每次完整验证。

本模块仅提供未来调用者可选实现，并不代表当前 B/C 已启用优化，不以缓存次数减少宣称运行时吞吐/准确率收益。将来接入新运行时需单独评审调用范围和版本/工件绑定，不可将含优化的结果冒充旧冻结实验。

验证：SP-03-features 全套 51 项通过（包含 8 个缓存用例），覆盖输出与原实现相等、深拷贝、路径、配置、每次摘要校验、重新命名后的伪造版本/结果、嵌套/异常退出和容量。B 67 工件/38 测试通过，39 必需来源未改。

没有导入原 PR12 的 online.verification_scope 包装或旧调度入口。没有执行实际 MQTT、长时或真实云实验。

复验：pytest spikes/SP-03-features/tests -q；python scripts/verify_b_phase_delivery.py <新输出目录>。
