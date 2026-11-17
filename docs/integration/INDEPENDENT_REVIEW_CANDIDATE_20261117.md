# 独立评审与离线集成候选（2026-11-17）

## 固定输入与顺序

main 基线为 5f5bc942db8acf1532a2b180e0e6248290309c14，未在原工作区、原 PR 分支或远端 main 上修改代码。按 #14 → #15 → #13 审查并在独立 worktree 装配，#12 不整批合并。

| PR | 固定提交 | 评审结果 |
|---|---|---|
| #14 | b4e8825aa8b911529f48323e8a56d0de78089814 | 4 项原短测通过；部分 timing 字段及 #13 采样格式兼容问题在候选修复 |
| #15 | 3d49bd1ba558087e09c4a99bb58af91ca1b56837 | 8 项原短测通过，含 Windows Job/句柄及默认预览；不注册调度或启动长时任务 |
| #13 | 5421ced3cd96dd85d1e676cbfa1e2c0ed3891a36 | 实际 head 优先于正文中的旧 a21a429；装配、证据、停报排空、版本锁完成本轮审查与补测 |
| #12 | abe27a7e35e72a620c22db270e37a8a6e9649c37 | 独立拆分诊断；缓存优化、执行工具及历史 B 差异不纳入候选 |

## 意见及候选内闭合

- #14 缺部分 timing 字段会 KeyError：改为缺失值 null，实测零保持零，增加回归。
- #14/#13 采样字段 elapsed_sec 与 elapsed_seconds 不一致，shutdown live=null：两种时钟字段均可读；带 phase 的样本按预声明 continuous 阶段汇总，故障不偷偷混进正常分母；保持诊断无自动根因/PASS。
- #13 checkpoint 的 asset_refs 越界/相对引用被忽略，以及引用文件损坏 JSON 未校验：增加计数和 fail-closed 回归，不改变 checkpoint 保存/恢复算法或授权删除。
- #13 预检与真正启动间的源码版本窗口：实际 start 前再次核对 tracked revision 和 dirty 状态，不仅检查 Python/依赖/broker 锁；新增“失败前不得启动/建输出”的用例。
- #13 原评审的错误数据库初始化问题：最新代码已有只读结构、unique OPEN 索引、持久策略检查，硬件绑定和旧策略拒绝保留；本轮不做旧库迁移。
- 补 ACK/延迟记录不完整、ACK 数不足、队列未排空、消息间停报的直接用例。保留现有自身进程清理边界，不清理用户进程。

以上修复在隔离候选中，不意味着原 PR head 已包含补丁，也未向 PR 发布评论或 Review。正式合并应选择本候选，或将补丁回移后复验，不能忽略这些差异直接批准原 head。

## 交叉回归与失败保留

| 范围 | 结果 |
|---|---|
| 首轮广范围：delivery/C业务/SP02 unit/契约/启动 | 494 passed，265.91 秒，早于最后补充测试，仅作覆盖调查 |
| 评审修复针对性 | 38 passed，5.10 秒 |
| 初次跨接口：协议分析/监督只读工具/证据 | 21 passed，1.51 秒 |
| #13 原 202 范围 + #14/#15/新增交叉（较早版本） | 221 passed，79.10 秒 |
| 最终组合第一次 | 226 passed / 1 failed，81.44 秒；原失败保留 |
| 公开 simulation 单独复验 | 2 passed，42.00 秒 |
| 最终串行组合 | 227 passed，82.19 秒；含停机排空补测 |
| B 冻结交付 | 67 文件完整性、38 测试通过；39 REQUIRED_SOURCES 与 main 的变更交集为空 |

范围重叠，不相加冒充测试总数。数据库、临时测试文件只放 D 盘，本次进程设置 TEMP/TMP，不改系统持久环境。

失败详情：公开 simulation 的两个 live 窗已经更新，但 assessment=UNKNOWN；只读取失败数据库确认 reason=FLOW_COVERAGE_LOW，流量覆盖约 0.2995，人员/水覆盖约 0.6247。原门槛为 0.8，未放宽、未改断言。质量保护符合既定拒判行为，但导致该次正常模拟 smoke 断言失败；调度/资源根因未独立证实，不能仅根据重跑通过宣布已修复主机或长期可用性。恢复实际实验前仍需检查采样完整性、主机资源与磁盘条件。

证据：docs/audit/independent-review-20261117/，包含失败、单独重跑、最终串行结果及低覆盖投影。未启动 MQTT broker、真实云、一小时实验或计划任务；已有测试仅本地 HTTP/数秒监督子进程。

## 集成候选与边界

工作区 .review-integration-20261117，分支 review/integration-candidate-20261117。运行代码修复提交 ec08881e84fc840f8aa044b1c34d140bfd68fb88。最终提交（含补测与报告）由本地 tag review/integration-20261117-candidate 固定；精确 SHA 与证据哈希另记于本工作区 .local/integration-candidate.lock.json，避免报告自引用。

只作为离线软件候选，acceptance_passed=false，actual_experiments_paused=true。原 PR14/15 Draft 不由此自动转正式，未合并/推送 main、未向他人发布消息。真实 MQTT/长时/云/实物及人员会签仍未放行。

复验入口：使用匹配应用锁的 Python，pytest tests/delivery spikes/C-business/tests spikes/SP-02/tests/unit tests/contracts tests/smoke -q（广范围）；最后精确 25 文件范围由 final-serial-227.xml 的 testcase.classname 可还原。B 用 scripts/verify_b_phase_delivery.py <全新输出目录>。不要仅把运行秒数改大执行长时场景。
