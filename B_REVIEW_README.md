# B 扩展实验：审阅与复现入口

本 PR 新增离线候选代理实验，不修改既有规则算法、C 接口、事件决策或水安全路径。独立交叉自检见 B_CROSS_SELF_CHECK_20261113.md；阶段报告见 B_STAGE_VALIDATION_REPORT_20261113.md。

输入包 B-PROXY-INPUTS-001 随 PR 提供 216 行特征、完整冻结来源清单、分区及重复审计。克隆后不依赖作者的 .local，临时输出目录必须不存在。

环境：Python 3.12，独立虚拟环境；按输入 manifest 的 provenance.packages 安装。当前版本：pydantic 2.14.1、pydantic-core 2.50.1、annotated-types 0.8.0、typing-extensions 4.16.0、typing-inspection 0.4.5。无 sklearn 依赖。

在工作区根执行：

```text
python -m unittest discover -s scripts -p test_b*.py -v
python scripts/train_b_proxy.py --features deliverables/B-PROXY-INPUTS-001 --labels deliverables/B-CANDIDATE-PROXY-001 --output .local/review-train
python scripts/evaluate_b_proxy.py --features deliverables/B-PROXY-INPUTS-001 --labels deliverables/B-CANDIDATE-PROXY-001 --model-dir deliverables/B-PROXY-MODEL-001 --output .local/review-eval
python scripts/verify_b_proxy_fallback.py --checkpoints .local/review-eval/checkpoints --model-dir deliverables/B-PROXY-MODEL-001 --output .local/review-fallback
python scripts/verify_b_phase_delivery.py .local/review-verify
```

来源冻结包括提取、训练、标签、评估、回退和验证入口，以及 M3/M4、规则/门控/配置和契约依赖。来源摘要仅统一 CRLF/LF，保留其他字节；原数据与交付工件仍检查原始字节。训练计划绑定来源清单，缺文件、删项、配置或实现变化必须拒绝。

最终核验会重算归档预测的主指标、分层、原因和失败案例；检查回退记录完整唯一、模型及标签/协议关联，并实际发现和执行测试。自检摘要不替代重新运行模型评估。

18 个开发留出 trial 的主评分点 C2/C3 同分，没有 ML 收益证据。规则衍生标签不是独立真实占用真值，开发留出也不是未知测试；真实效果、在线全链路、实物安全和 C 会签尚未完成。

历史文档的 .local 路径是原执行证据位置，新的可移植命令以上述入口为准。模型因来源元数据修订改变摘要，结构、候选方案与评估指标未改变。PR 保持未合并。
