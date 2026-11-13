# P2 首轮训练与验证选择

已实现 scripts/train_b_proxy.py，验证标签、合同、特征及方案摘要；验证窗口唯一归属与固定九特征允许清单。只有 train 的可用代理标签用于拟合，validation 用于预注册选择，test 不预测。

实际结果：train 108 窗口中 75 可用、33 受限；validation 54 中 40 可用、14 受限。两个预注册候选均为验证 trial 等权窗口错误 0，按平分规则选择深度 1、叶最小样本 2 的树。15 个 validation trial 有可评分窗口，不能把它描述为全部 18 trial 完全正确。

模型与锁定记录：.local/b-expanded/runs/p2-proxy-001/model.json、model.lock.json。选定模型 SHA256：c08c77aba41d2b4cdfd7c1670dc9f828b337b1ff551b6bb60e20b7b6dd15bfbd。训练入口未调用 test 预测，test 只记录清单计数；尚未执行 C0–C3 测试比较。

验证：重复训练模型哈希一致，摘要不符拒绝加载；当前 test_b*.py 共 10 项通过。

结果仅为规则衍生候选代理的一致性。开发留出曾暴露、特征存在跨区碰撞，没有独立测试或真实效果保证。本次无人工会签，未改事件路径/水安全路径。

后续：完善数据加载的 cohort/完整谱系再校验与故障验证，再进行同范围 C0–C3 开发留出报告。不得看结果调阈值；真实占用效果仍需独立操作标注。

P2 收尾：输入完整谱系/cohort 校验、最终训练、加载往返和异常加载验证完成。11 项测试通过。最终模型与锁定记录已归档 deliverables/B-PROXY-MODEL-001；test 未评估。详见该目录 MODEL_CARD.md。


本轮交叉自检补齐运行入口冻结与跨工件语义检查；当前模型标识以 model.lock.json 为准。此前测试数量为历史记录，最新验证见 B_CROSS_SELF_CHECK_20261113.md。
