# B-CANDIDATE-PROXY-001

独立的因果证据候选代理标注版本，保留原 B-SIM-001。216 个窗口：候选正例 64、负例 96、UNKNOWN 56。

contract.json 明确阈值和发布时间，labels.jsonl 逐窗记录原因、原操作脚本标签及输入哈希；manifest.json 绑定标签、合同、生成脚本和上游特征。

重要限制：标签由观测特征按固定工程条件生成，属于规则衍生代理目标，不是独立人工标注。因此只能支持候选规则近似/工程一致性实验，不能证明 C3 比 C2 更有效，也不能作为真实无人用水识别率。原操作真值仍单独保留，隐藏人员场景继续是反例。无人工签署。

training_plan.lock.json 已预注册两个候选：深度 1 或 2、叶节点至少 2、Gini、正例平分。仅 train 拟合，validation 按 trial 等权平均窗口错误选择，平分选较浅模型；不在 train+validation 重拟合。不搜索阈值。质量拒判单列并保留完整报告分母。

当前 test 为已暴露的开发留出，模型和配置实际锁定后才计算其指标，不称独立未知测试；查看后不得回流调参。本轮尚未训练，实际模型哈希尚待 P2 生成锁定。

复现：python scripts/publish_b_proxy_labels.py --features .local/b-expanded/runs/p1-features-004 --output <不存在的新目录>
测试：python -m unittest discover -s scripts -p test_b*.py -v
依赖父特征包可按 B_P1_CLOSEOUT.md 重建，父哈希必须匹配；不得绕过摘要校验。

P0 的原始 episode 真值无法变成可靠在线可辨识真值。本包通过明确缩小为代理任务解决开发标注边界；真实效果验收仍需新的独立操作标注与实物数据。
