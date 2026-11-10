# B-EVAL-001｜第一版规范化评估包交接

状态：已重新计算、规范化并校验；待 B Owner 审核，未正式验收。
范围：复用当前仓库 B 的 8 个手工构造合成场景，不修改 B 算法、标签或公共 API。

## 交付位置

- [包说明](../../deliverables/B-EVAL-001/README.md)
- [规范化报告](../../deliverables/B-EVAL-001/evaluation.json)
- [原 B 对照结果](../../deliverables/B-EVAL-001/raw/comparison.json)
- [场景、标签依据和检查点索引](../../deliverables/B-EVAL-001/trials.json)
- [逐场景逐方法预测](../../deliverables/B-EVAL-001/predictions.jsonl)
- [误判与拒判案例](../../deliverables/B-EVAL-001/review_cases.json)
- [文件校验清单](../../deliverables/B-EVAL-001/manifest.json)

报告 ID：`b-synthetic-8-478d2679798cfec3`。
8 个场景：3 个正例、5 个负例，每个场景评估一个窗口。
共 5 个配置：B0_flow、B1_instant、B2_5s、B2_10s、B2_15s；对应三类规则，
不是 5 个模型。B2 三个配置是阈值敏感性对照，不是 C3。

| 原方法 | 命中正例/全部正例 | 误报预测数 | 拒判/全部场景 |
|---|---|---|---|
| B0_flow | 3/3 | 4 | 0/8 |
| B1_instant | 2/3 | 3 | 1/8 |
| B2_5s | 2/3 | 3 | 1/8 |
| B2_10s | 2/3 | 1 | 3/8 |
| B2_15s | 1/3 | 1 | 4/8 |

误报是逐场景候选判断计数，不是 M6 告警事件数或每小时误报。
召回分母包括被拒判的正例；不能只展示 FN=0 而隐去正例拒判。
规则在这些构造场景中的差异不能支持泛化准确率或最优阈值结论。

## 版本与证据

报告保留实际对齐、特征、规则语义及配置版本，源文件 SHA256、数据集摘要、
Python/Pydantic 版本与构建器摘要。checkout_commit 是生成时的检出上下文，
构建器可能尚未存在于该提交；构建器 SHA256 才是本次脚本字节标识。

包内路径均为相对引用；原生检查点保留内容寻址和内容。
不同场景会复用 observation_id，必须以 trial_id 隔离；不能直接合并为在线观测。
原始合成数据的 DEVICE_SYNCED 时间标记不是已经证明真实设备时间同步。

## 复现与验证

从仓库根目录、现有应用 Python 环境执行：

```powershell
python scripts/build_b_evaluation_package.py --output audit/new-b-evaluation-run
python scripts/build_b_evaluation_package.py --verify deliverables/B-EVAL-001
python -m pytest tests/delivery/test_b_evaluation_package.py -q -p no:cacheprovider
```

输出目录必须全新，拒绝覆盖旧包。两次生成的时间和检出上下文可不同，
同一源字节和数据下，报告 ID、预测及指标一致。manifest 检查字节与语义一致性，
不是数字签名或独立审批。Git 对本包禁用换行转换，防止跨平台检出损坏哈希。

本轮测试 8 项通过：原始计数/口径、不可区分反例与 trial 身份隔离、
重复生成、损坏证据、改写计数后重签哈希、缺失预测、包外路径与禁止覆盖。
本地 JUnit：audit/b-package-tests-20261110.xml。

## 接下来分别需要做什么

**B 审核**：确认任务/标签解释、原方法与 C0–C2 的展示映射、默认配置及指标口径。
报告中的映射仍是 PENDING_B_REVIEW；C3、Macro-F1、真实延迟和事件频率均未提供。

**C 接入**：以本包为样例确认结果响应契约，校验可信包及 trial/报告关联，
提供受控只读接口和证据下载。不直接开放任意本地路径，不修改旧 1.1 DTO 的含义。

**前端接入**：仍扩展现有实验页，展示规则对照、指标分母、案例和证据。
当前尚未将本包硬编码进页面或绕过 C 接口。

## 项目进度

D4 新增可交接的仿真规则评估包；D2 获得可用结果样例，实际数据接入仍待 C。
D1 硬件和 D3 云协同本轮未改动。无独立测试划分、ML 或真实实验，G3 未通过。
