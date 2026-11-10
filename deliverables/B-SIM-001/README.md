# B-SIM-001｜扩展仿真数据与声明分区

这是下一轮 B 实验的数据准备，不是已训练/已评估模型，也不代表 G3 通过。
默认 12 个 cohort × 6 个场景 = 72 trial，每个 trial 有 30/35/40 秒三个窗口标签。
同 cohort 的所有场景及同 trial 的所有重叠窗留在同一分区；声明的测试集不能用于调参。
场景：空闲、有人流水、短暂离开、持续离开、静止人员未检出、人员传感掉线。
标签来自操作脚本，不导入/调用被评估规则。短暂离开的负标签包含未来返回的先验；
静止在场与真实离开存在观测不可区分反例，不能据此宣称在线识别真实无人。

文件：dataset.json（身份/来源/限制）、split_manifest.json（分区）、trials.json（场景与标签依据）、
labels.jsonl（窗口标签）、observations.jsonl.gz（标准库 gzip 可读的完整观测）、manifest.json（文件哈希）。
观察身份在每个 trial 中唯一；不要把各 trial 合并成一个在线设备流。
分类器只能使用传感特征，不得使用场景名、生成参数、ID、标签或分区信息作为预测输入。

复现：python scripts/build_b_sim_dataset.py --output <全新目录> --seed 20261110 --cohorts 12
核验：python scripts/build_b_sim_dataset.py --verify <数据目录>
输出拒绝覆盖旧目录。生成时不计算 C0–C3 指标，不读取测试集调参。
