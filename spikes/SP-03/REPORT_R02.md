# 第 2 轮报告｜固定截止窗口原型

日期：2026-10-29。状态：PARTIAL。已完成有限文件窗口核心验证，完整 SP-03 尚未通过；独立 Reviewer 待指定。本轮 review 与交叉检查均由同一开发代理完成，不冒充独立评审。

## 组会讲解
上一轮能重复播放消息，本轮开始把异步消息整理成窗口。程序为每个指定窗尾设置固定截止时间，截止相等的消息先纳入，然后发布窗口；某一路完全沉默也不会阻塞。未知和过期保留为 unknown，覆盖率按有效时间段并集计算。先用手算结果核对，再做契约和启动回归。当前没有硬件、实时服务和性能结论。

## 开发内容与思路
- src/alignment.py：先验证原始 DTO，再执行身份检查和每窗截止过滤，计算三源摘要，最后调用 AlignedWindow 正式候选模型检查输出。
- 时间完全由输入 window_ends 和 received_at 决定；没有真实 sleep。固定 published_at=end+L，为实验逻辑发布时间。
- water/presence 状态保持至下一条观测或 TTL；未知/无效消息打断状态保持。TTL 边界按已过期处理。
- flow 采用“时间戳是统计间隔终点”的实验假设，仅统计实际间隔覆盖；不把区间均值外推至 TTL。窗尾没有新间隔时终态保守为 unknown，此口径待 A/B 评审。
- 窗口 (t-W,t]；窗前状态可贡献窗内覆盖；窗尾点可改变终态但贡献零时长。区间覆盖按持续时间处理，不等于仅按点时间筛选。
- lateness 按每个目标窗口独立判断；错过一个窗口的观测仍可进入后续窗口。
- 拒绝事件时间晚于接收时间的输入并加质量标记，为保守实验策略，不是已验证的硬件时钟容差。
- 完全相同的重复 ID 去重；同 ID 不同内容或同 device/sensor/boot/seq 不同 ID 拒绝。seq 暂按源级处理，待 A 确认。
- 配置摘要进入 alignment_config_version 和 window_id；不同配置不会得到相同窗口身份。

## Review 与修复
1. 检查左边界前驱、右边界点、TTL 相等、迟到截止相等、晚到跨窗口、未知中断、序号重置、重复冲突、未来时间和流量区间裁剪。
2. 发现来源引用最初只覆盖有效读数，会漏掉造成未知的观测；已修复，新增回归断言保留中断观测 ID。
3. 黄金样例独立手算：water 在 [20,25) 有效 5 秒，随后明确未知；30 秒窗口覆盖率 5/30，窗尾 unknown；flow/presence 覆盖为 0。
4. 使用既有候选 DTO 验证每份输出，并执行现有 contracts 和 smoke 测试；实际结果见 evidence/r02_tests.txt。

## 运行与证据
```powershell
.\.venv-app\Scripts\python.exe -m pytest spikes/SP-03/tests tests/contracts tests/smoke -q -p no:cacheprovider
.\.venv-app\Scripts\python.exe spikes/SP-03/src/alignment.py spikes/SP-03/data/r02_case.json --output spikes/SP-03/evidence/r02_windows.json
```
输入与手算预期：data/r02_case.json。实际窗口：evidence/r02_windows.json。

## 未完成边界及下一小轮
- 当前是有限离线批处理，扫描全部输入，无持续服务的有界缓存和压力验证；不可当生产算法。
- 支持 boot 进入身份键、重置 seq 不冲突；尚未验证设备级重启使其他源旧状态失效、旧 boot 延迟消息隔离和时间重新映射。不能声称重启治理完成。
- 目前以统一 TTL 实验，尚需按源配置、异常时钟漂移策略和更完整的来源审计。
- 空输入设备默认 demo，正式入口需显式传设备身份。
- 样例数量仍少，下一轮先补齐完整 SP-03：设备级 boot 隔离、流式时钟/缓存、分源 TTL 和更大黄金场景集；通过后再推进 M4，避免带着基础缺口进入特征开发。
- 本轮没有修改正式 Contract；所有数据 synthetic / prototype_only。硬件、MQTT、IoTDA 未验收。
