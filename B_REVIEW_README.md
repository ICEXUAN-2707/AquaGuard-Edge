# B 扩展实验：审阅与复现入口

本 PR 新增离线候选代理实验，不修改既有规则/对齐/特征算法、C 接口或水安全路径。阶段总结见 B_STAGE_VALIDATION_REPORT_20261113.md。

本次交付补齐独立输入包 B-PROXY-INPUTS-001（216 行特征、来源清单、冻结分区及近重复审计）。测试与训练入口改用该包，克隆后不依赖作者 .local 目录。文件保留原始字节，以兼容已记录摘要。

环境：Python 3.12；创建独立 venv，按输入 manifest 的 provenance.packages 安装锁定依赖。本轮依赖版本为 pydantic 2.14.1、pydantic-core 2.50.1、annotated-types 0.8.0、typing-extensions 4.16.0、typing-inspection 0.4.5。无 sklearn。

工作区根执行：
python -m unittest discover -s scripts -p test_b*.py -v
python scripts/train_b_proxy.py --features deliverables/B-PROXY-INPUTS-001 --labels deliverables/B-CANDIDATE-PROXY-001 --output .local/review-train
python scripts/evaluate_b_proxy.py --features deliverables/B-PROXY-INPUTS-001 --labels deliverables/B-CANDIDATE-PROXY-001 --model-dir deliverables/B-PROXY-MODEL-001 --output .local/review-eval
python scripts/verify_b_proxy_fallback.py --checkpoints .local/review-eval/checkpoints --model-dir deliverables/B-PROXY-MODEL-001 --output .local/review-fallback
python scripts/verify_b_phase_delivery.py .local/review-verify

输出目录必须不存在。测试在归档输入上有限重复训练，验证模型哈希不变；评估重放不允许调参。旧文档里的 .local/p1/p2 路径为历史执行证据路径，本入口给出可移植的新命令。

结论：18 开发留出 trial 主评价 C2/C3 同分，没有 ML 收益证据。标签由规则衍生，非真实占用真值；真实效果、在线全链路、C 会签及硬件安全验收未完成。当前报告不承诺发布或事件接管。

PR ??????????????? B_FREEZE_VALIDATION_FIX.md??? 24 ??????/??/????????????????
