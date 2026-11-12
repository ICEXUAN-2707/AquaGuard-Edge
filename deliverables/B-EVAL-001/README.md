# B 第一版规范化仿真评估包

这是现有 8 个手工合成场景的开发诊断结果，不是独立测试集或真实性能报告。
原始 B 方法 ID、预测和计数保持不变；C0–C2 映射待 B 确认，C3 未提供。
拒判单列，不能当作正确负例；逻辑发布时间不能用于真实延迟结论。

evaluation.json：规范化报告与指标定义。trials.json：场景、标签依据和检查点。
observations.jsonl：以 trial_id 隔离的原始合成观测，不能直接合并为在线数据流。
predictions.jsonl：逐场景/方法预测。review_cases.json：误判和拒判审查案例。
raw/comparison.json：原 B 结果。raw/checkpoints：内容寻址、可重算的原生快照。
manifest.json：除自身外所有文件的大小与 SHA256；不等于独立签署。

从仓库执行：python scripts/build_b_evaluation_package.py --output <全新目录>
核验：python scripts/build_b_evaluation_package.py --verify <包目录>
每次生成新目录，不覆盖旧证据。时间和 checkout_commit 可以变化；源文件哈希和数据确定报告身份。
本包不是公共 DTO/API 契约；供 B/C 确认格式与受控接口后接入现有实验页。
