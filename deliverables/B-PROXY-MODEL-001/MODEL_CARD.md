# B-PROXY-MODEL-001 模型卡与 P2 收尾

P2 已完成工程范围训练/验证选择与模型锁定。无人工会签，无真实场景效果验收。原始 B-SIM-001 未修改。

目标：规则衍生的因果观测候选代理。不得称真实无人识别或独立 ML 收益。C3 仅影子运行，不接管事件和水安全路径。
模型：既有纯 Python 决策树，max_depth=1，min_samples_leaf=2，Gini，正例平分。九特征允许清单沿用 SP-04，不包含水接触、ID、场景、标签及分区。

输入谱系：原数据 verify、源清单哈希、冻结分区哈希、cohort 归属、窗口唯一性、特征/标签/合同哈希及特征源代码哈希在拟合前核验。锁定文件同时保存训练入口与输入校验器哈希。特征包清单含实际 Python/依赖版本。

仅 train 拟合：108 窗口中 75 可用。validation：54 中 40 可用，覆盖 15 trial；14 受限窗与其余 trial 不隐去。深度 1、2 的验证 trial 等权窗口错误均为 0，按预注册平分规则选深度 1。未合并 train+validation 重拟合，未改阈值。

结果只表示对工程代理的验证集一致性。原数据存在观测不可区分反例，特征有跨区碰撞，test 已暴露为开发留出；不能作真实准确率或未见场景泛化证明。

模型 SHA256：567a3d496f72721cc56d161e26c477f7d6ca3bd4b7a1353618438b0ef74a2132。
重复训练哈希相同；模型写入/加载往返一致。缺失、损坏、错特征版本加载均拒绝；这些是加载器验证，不冒充 P4 的完整 C2 回退集成验证。

test_evaluated=false：未调用开发留出预测。P3 须先核对 model.lock.json 与模型摘要，再一次性按锁定方案比较 C0–C3；禁止看结果反复调参。

复现（先按 B_P1_CLOSEOUT.md 重建父特征与分区）：
python scripts/train_b_proxy.py --features .local/b-expanded/runs/p1-features-004 --labels deliverables/B-CANDIDATE-PROXY-001 --output <不存在的新目录>
默认冻结分区位置为 .local/b-expanded/runs/p0-repair-001/repaired_split_proposal.json；迁移机器需保持同样布局或通过 Python run 的 source/split_path 参数显式指定，哈希仍须匹配。
验证：python -m unittest discover -s scripts -p test_b*.py -v
本轮 11 tests passed，非全系统回归。

交付：model.json、model.lock.json、training_plan.lock.json、本模型卡。下一阶段为 P3 开发留出同范围对照及失败案例，P4 回退集成和 C 报告协商未完成。
