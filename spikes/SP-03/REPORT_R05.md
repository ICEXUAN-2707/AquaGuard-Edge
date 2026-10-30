# 第 5 轮｜阶段审查整改简报

日期：2026-10-29。状态：本轮软件整改验证通过；完整 SP-03 仍 PARTIAL。synthetic / prototype_only。

## 按顺序修复
1. 容量恢复：push 在副本上先推进到期窗口、清理过期数据，再检查容量；全部成功才提交。失败不改变真实时钟、缓存和窗口游标，避免丢失已生成但未交付的窗口。
2. 启动资格：事件时间晚于接收时间的输入直接拒绝；切换 boot 额外要求 valid 和非 RECEIVED_FALLBACK。异常输入不会清空状态或退役旧周期。仅为原型资格门槛，不能证明一个未见过的 boot 一定比当前更新；可靠启动身份仍需设备证据。
3. 输出上限：新增 max_windows，默认每次 advance 最多 100 个窗口。next_end 为追赶游标；大跨度 push 需要超过此上限时明确拒绝且不提交，调用方先重复 advance(received_at, inclusive=False) 追赶后重试，再处理同时间戳消息和截止。
4. 版本与入口：算法语义版本改为 sp03-r05-v1，与配置摘要共同构成窗口身份；回放改用与对齐一致的原始观测质量校验。

## 验证与自查
新增缓存恢复、失败原子性、异常新 boot 不变更状态、分批窗口无重复无遗漏、未知新 boot 拒绝和原始质量入口测试。全部回归实际结果见 evidence/r05_tests.txt；命令如下：

```powershell
.\.venv-app\Scripts\python.exe -m pytest spikes/SP-03/tests tests/contracts tests/smoke -q -p no:cacheprovider
```

注意测试总数包含现有 contracts/smoke。本轮为同一代理 review 与自检，未经过独立 Reviewer。

## 剩余边界
- 同时间戳必须先 push 全部消息再 advance；接口仍依赖调用约定。
- 重启仍保守清空旧周期覆盖；未完成真实时钟映射和设备启动身份验证。
- 旧阶段复现脚本和证据保留原样，代表修复前状态；不能当作当前实现的预期输出。当前修复由新增回归断言证明。
- 流量区间端点、TTL 实测、完整三源长序列与独立评审仍待补齐；测试 fixture 组织整理未纳入本轮功能修复。
- 暂不进入正式 M4 集成；下一轮可先整理口径决策表和补全三源综合样例。
