# B 扩展实验交付状态与无收益决策

## 当前状态
P0：已发布工程代理标签；未获得独立真实占用真值。
P1：九特征和质量/重复审计完成，来源与环境记录完整。
P2：有限验证选择与模型锁定完成，无后验调参。
P3：开发留出 C0–C3 对照与 C2/C3 配对分析完成，主结果同分，没有已证实 ML 收益。延迟因缺独立 onset 不可评估。
P4：实际 C3 适配器在 18 trial、54 窗口的三类模型故障中 162 次回退 C2 一致；原工件未修改。范围仅快照适配器；不是在线服务或真实水安全验收。

仍未完成：真实数据采集、独立占用/事件标注、在线/离线全链路与真实延迟验证、真实硬件安全测试、C 新报告兼容会签、人员 Reviewer 签署。不得将本文件解读为整个 B 或 G3 正式放行。

## 如果独立测试仍没有改善
先区分结论：区间宽且包含零是证据不足；若有足够精度排除预定的最小有用收益，可以说在该环境/指标范围内没有达到有用改善。只有按预设等效或非劣设计得到相应区间，才可称等效/非劣；普通“不显著”不能替代它们。

不强制修改算法。默认保留已验证 C2 为正式决策方案，C3 保持影子或归档，保留如实模型卡和失败报告。若比赛交付要求轻量 ML，交付可运行、可复现且有边界说明的模型实验即可，不虚构收益。

只有存在明确失败模式才发起新版本：
- 覆盖不足/掉线/标定不准：先修感知、时间和质量，不用模型掩盖。
- 相同输入对应不同真实状态：现有输入不可辨识；需独立额外感知证据或缩小任务，不靠增加树深度解决。
- 特征遗漏了可在线获得的有效信息：在技术边界内验证新特征版本。
- 模型容量确实不足且独立证据支持：有限调整轻量树参数，仍不增加复杂训练框架。

每次变更应由开发集/独立 pilot 提出假设，预先固定指标和候选，用新独立测试检验；已读测试集永久保留为开发数据，不改名重复使用以证明收益。如果 C2 已满足实际需求且更简单，停止增加 ML 复杂度是有效工程结论。

## C 报告交接提案（尚未会签）
新包 B-PROXY-EVAL-001 使用独立 schema b-proxy-p3-report-v1，明确 source=simulation、task=rule-derived proxy、development_holdout_exposed=true、shadow_only=true。
主单位为固定 40 秒窗的 trial，54 重叠窗口作为辅助，不塞进旧 R07 指标。UNKNOWN、拒判分母、模型/标签/协议哈希及不可估延迟必须保留。
C 兼容协商前只作为独立工件提供，不写入旧 ExperimentResult、不覆盖 b-exp-report-v1、不自动上传或推送给他人。C 应在采用前明确版本映射、缺字段行为和回归范围。

## 复现索引
P0/P1：B_P1_CLOSEOUT.md。
P2：deliverables/B-PROXY-MODEL-001/MODEL_CARD.md。
P3：deliverables/B-PROXY-EVAL-001/README.md、PAIRED_COMPARISON.md。
P4：python scripts/verify_b_proxy_fallback.py --checkpoints .local/b-expanded/runs/p3-proxy-001/checkpoints --model-dir deliverables/B-PROXY-MODEL-001 --output <不存在的新目录>。
工件哈希见 B_DELIVERY_MANIFEST.json；不含原始观测的完整镜像，父数据仍为 deliverables/B-SIM-001。
