# B 后续开发第一批｜评估边界与扩展仿真数据

分支：feat/b-evaluation-next-20261110；独立工作树 .b-evaluation-next。
基线：34ed76c。未修改前端、C 工作树、公共 API、既有 B-EVAL-001 数值或部署。

## BP-05：评估器边界已实现

`spikes/SP-04/evaluate.py::metrics`：

- 空集合给出明确 ValueError，不再意外除零。
- 无正例时 positive_recall_all=null，拒判仍按全部样本计算，不补 0。
- 无负例及全拒判保留正确分母；正例拒判不算 FN，但必须通过召回与拒判同时展示。
- 标签必须为 bool；预测必须为 bool/null。拒绝 0/1、字符串、NaN/Infinity 和缺失方法。
- 删除重复导入，禁止输出非有限 JSON 数值。

最终 M5/评估回归：68 passed / 5.00s。
新增完整对象对比证明原 8 场景报告与 B-EVAL-001/raw/comparison.json 完全一致。
本地报告：audit/b-next-metrics-verified-20261110.xml。
首轮新增不漂移夹具因父目录层级错误失败，修正路径后全量重跑通过；未改算法值绕过失败。

旧 B-EVAL-001 保留原始来源摘要与构建记录；它描述的是上一源基线。
当前 metrics 源文件变化后，不能要求“当前源码字节等于旧包来源字节”；
旧包自身哈希/语义校验仍通过，不重写历史证据。

## BP-06：B-SIM-001 数据与声明分区已生成

位置：[B-SIM-001](../../deliverables/B-SIM-001/README.md)。
数据 ID：b-sim1-65ff0bbbac70fcc2；源为 simulation。

| 内容 | 数量 |
|---|---|
| cohort | 12 |
| trial | 72（24 正例 / 48 负例） |
| 窗口标签 | 216（每 trial 在 30/35/40 秒各一个） |
| 原始三源观测 | 5,422，标准 gzip 压缩 JSONL |
| 训练 / 验证 / 测试 trial | 36 / 18 / 18 |

场景：空闲、有人流水、短暂离开、持续离开、静止人员未检出、人员传感掉线。
采样周期 1/2/5 秒、合成流量和接收延迟等由固定种子及 cohort 参数决定。
每条观测通过现有 SensorObservation DTO 校验，身份按 trial 隔离。
标签由操作脚本产生，不导入/调用规则分类器生成真值。

同 cohort 所有场景、同 trial 所有重叠窗留在同一分区；
unattended / hidden_present 的观测值相同而标签相反，成对保留在同一分区。
随机种子、分区清单、原始数据、标签和文件摘要均可复现；拒绝覆盖旧目录。

### 必须保留的限制

- 这是数据准备，不是已训练/已评估的 C3，也不是统计代表性样本。
- 各分区包含相同场景族；参数可能重复，不能宣称未见场景族或真实世界泛化。
- brief_leave 的负标签使用完整操作脚本（包括未来返回），不是在线可观察真值。
- hidden_present 与无人离开观测不可区分，不能以学习器承诺解决传感器信息不足。
- 2 秒采样可能不在 35 秒窗尾产生 flow 端点，UNKNOWN 是合法结果。
- 合成 DEVICE_SYNCED、K=60 脉冲标定不是实测硬件证据。
- 本数据只针对用水情境，water 为干；不得用 C3 替代快速水接触信号。
- 数据用于离线实验，不能直接作为当前 simulation-only MQTT wire 的真实硬件输入。
- 模型只能使用已批准的传感特征，禁止使用 ID、场景名、生成参数、标签或 split 作为特征。

### 实际验证

- 首轮数据 + 旧评估包测试：21 passed / 14.95s（7 项数据 + 14 项评估包）。
- 补充原生管线后数据测试：8 passed / 11.44s。
- 原生检查仅使用训练/验证场景×采样周期组合，验证 M3、12 特征、M4 restore、M5 合法输出；
  不以测试集选择阈值，不产生模型性能指标。
- B-SIM-001 自校验 PASS；B-EVAL-001 自校验仍 PASS。

本地报告：audit/b-next-data-20261110.xml、audit/b-next-data-native-20261110.xml。
重复范围不相加为项目完成率。

## 复现

```powershell
python scripts/build_b_sim_dataset.py --output audit/new-b-sim --seed 20261110 --cohorts 12
python scripts/build_b_sim_dataset.py --verify deliverables/B-SIM-001
python -m pytest spikes/SP-04/tests -q -p no:cacheprovider
python -m pytest tests/delivery/test_b_sim_dataset.py tests/delivery/test_b_evaluation_package.py -q -p no:cacheprovider
```

使用现有应用 Python 环境，无新增 NumPy/scikit-learn/训练依赖。
生成器和数据校验均为项目内部实验工具，不新增公共服务或通用框架。

## 下一批：最小 C3 与完整对照

1. B Owner 确认任务/标签口径、C0–C2 映射与分区；必要调整必须升版数据，不覆盖本包。
2. 从现有 M3/M4 生成版本化特征，固定 12 字段允许清单及缺失处理；隔离辅助 ID/标签。
3. 在 train 拟合一个轻量模型，在 validation 做有限选择并记录；锁定后再评估 test。
4. 同一测试范围运行 C0–C3，保留拒判与分母、不可区分反例、失败结果和模型卡。
5. 模型加载/版本错误明确回退，C3 先影子运行，不改 water 快路或擅自替换正式规则。
6. 与 C 协商支持新方法/元数据的报告版本，不能直接塞进固定五方法 legacy 接口。

## 项目进度

D4 新增边界修复和可复现分区数据；完整 C3、独立实验报告与 G3 验收仍待完成。
D2 前端仍在独立分支，不自动读取本新数据包。D1 硬件与 D3 云链路本轮未改动。
BP-05 已实现并测试；BP-06 完成第一版准备，仍待 B 审核及后续评估，不等于 G3 放行。
