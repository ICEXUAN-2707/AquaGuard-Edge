# P1 特征管线收尾记录

日期：2026-11-13。状态：P1 的本轮开发与定向验证完成，属于合成数据开发管线交付；P0 新标签未发布，因此 training_ready=false，不自动进入 P2。

## 已交付
- extract_b_expanded_features.py 复用 M3 align 与 M4 compute，显式投影固定九特征；水接触、场景、ID、分区、操作标签不进入模型向量。
- 30 秒窗、2 秒等待、10 秒 TTL、流量阈值 0.1；收到时间 <= end+2，事件时间 <= end。缺失和非有限特征不插值、不补零；质量与完整向量分别记录。
- 每行记录 trial/window/publication、输入历史哈希与数量、特征版本；清单记录源数据/分区/特征哈希、源码哈希、Git 基线与环境版本。源码未提交状态由哈希明确标识。
- 三分区完整性、唯一归属、cohort 不跨区防护；按场景/分区列拒判、样本数和碰撞。
- 独立原始数据未覆盖；两次提取 features.jsonl 逐字节相同。

## 实际结果
216 窗口，160 个质量与特征均可用，56 个受限。拒判原因可重叠，不相加冒充窗口数。
10 组跨区相同特征向量，主要为稳定空闲/有人流水及受限掉线样本。
固定工程尺度的最大坐标差审计：阈值 0.05；8175 对完整跨区向量中，339 对完全相同，8 对近似。特征重复不证明源数据泄漏，也不证明数据独立；不因审计结果调参、迁移分区或删样本。
该近重复检查仅针对九维特征空间；未提供原始时序距离、感知设备泛化或真实场景独立性证明。原测试集已暴露，修复分区只作开发留出。

## 验证
python -m unittest discover -s scripts -p test_b*.py -v
结果：7 tests passed，覆盖分区防护、源数据不变、输出拒绝覆盖、未来信息隔离、延迟端点恢复、合法 UNKNOWN、允许清单及非法值、固定尺度距离。
使用本工作区 .venv/Scripts/python.exe。依赖实际版本见特征 manifest；不是全系统回归或人员会签。

## 复现（输出必须不存在）
python scripts/repair_b_sim_split.py --source deliverables/B-SIM-001 --output .local/b-expanded/runs/reproduce-p0
python scripts/extract_b_expanded_features.py --source deliverables/B-SIM-001 --split .local/b-expanded/runs/reproduce-p0/repaired_split_proposal.json --output .local/b-expanded/runs/reproduce-p1
python scripts/audit_b_feature_proximity.py --features .local/b-expanded/runs/reproduce-p1 --output .local/b-expanded/runs/reproduce-p1/proximity.json

## 证据索引
最新特征：.local/b-expanded/runs/p1-features-004/features.jsonl
来源/版本/环境/分层：同目录 manifest.json
近重复审计：同目录 proximity.json
前次复现对照：p1-features-003/features.jsonl

## 进入 P2 前
完成 P0 独立标签版本及标注依据，固定候选目标、操作真值与 UNKNOWN 的关系；避免以 C2 衍生标签宣称 ML 优于规则。明确开发留出限制，预注册验证候选及测试使用政策。尚未训练、未生成新模型、未改 C 接口，C3 继续影子运行，水安全路径不变。
