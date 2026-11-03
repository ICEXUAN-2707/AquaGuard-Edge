# C-R05｜本地Mock Outbox阶段收尾

## main合并兼容性复核（2026-11-03）

PR目标调整为main后，将origin/main（f0b703d）合入C分支。保留main的A/B交接延迟导入与缺模块友好报错、条件测试保护、B文档及归档结构，同时保留C的R05进度与C0–C9复现章节。无冲突标记/未解决索引，格式检查通过。

合并后执行C业务、SP-06、A的test_handoff_b/test_core、contracts与smoke：147 passed in 21.74s，退出0，临时目录为spikes/C-business/local/check-main-merge01。该范围含既有测试，不与128项累加；前端未修改，浏览器验收限制仍保留。

日期：2026-11-03。限定Mock范围实现并回归收尾；真实IoTDA、生产可靠性、正式迁移与独立评审未验收。R04浏览器和持续在线调度待办继续保留。

## 交付与交叉自检

|能力|实现|
|---|---|
|不可变发送快照|store.py新增outbox_payloads，事件、转换、同步记录及转换时刻的消息同事务提交；旧消息不读取最新事件重建|
|持久认领|outbox.py保存attempt token、尝试号、认领时刻、租约截止与结果；两连接竞争只有一次有效认领|
|退避与恢复|next_retry_at持久化，指数退避/封顶/最大次数；未到期不领，租约过期转重试，消息ID与载荷保持不变|
|配置一致性|delivery_policy保存配置和版本，重启变更明确拒绝，迁移另行评审|
|结果隔离|token/尝试号/状态/租约联合校验；迟到STALE、重复DUPLICATE、不同结果冲突|
|独立回执|ACCEPTED需Mock传输回执；mock-consumer业务回执另行记录并校验，不推导联系人送达|
|显式运行|run.py worker提供有限steps、间隔与Mock模式；serve默认不发送，无SDK/真实网络/联系人调用|

自检发现旧Outbox仅有同步DTO，缺转换时刻的发送内容。若读取最新事件，会把后来ACK/物理变化带入旧消息，故新增快照并纳入事务。另补租约token防止旧结果覆盖新尝试、策略持久化防重启漂移、独立业务回执防混淆确认层级。worker仅改投递表，不改事件或转换事实。

仅simulation允许Mock发送，其他origin可见FAILED且不调用发送。错误保存受控码，任意adapter异常/凭据文字不写入结果。原payload与新ACK后的事件对照、发送失败后事件不变均有测试。

## 实跑证据

```powershell
.\.venv-app\Scripts\python.exe -m pytest spikes/C-business/tests spikes/SP-06/tests tests/contracts tests/smoke -q -p no:cacheprovider --basetemp spikes/C-business/local/check-r05-final01
```

128 passed in 31.90s，退出0，含13项R05专项。覆盖持久退避/上限/次数、稳定快照、租约恢复、迟到/重复/冲突结果、双连接认领、回执校验、旧库缺快照、快照事务回滚、配置变更、来源拦截、独立业务回执及真实worker CLI。

首轮专项8项、中间126项回归均通过；与最终范围重叠，不累计。前端未改，本批未重复构建。系统盘空间不足，测试临时库在工作区独立目录，未删除系统或用户文件。以上为同开发代理交叉自检，Reviewer待指定。

## 操作与限制

命令见[演示手册R05章节](C-business/LOCAL_DEMO.md)。默认实验策略base=1秒、cap=60秒、lease=10秒、max_attempts=5，无jitter；不是实测生产参数。CLI采用默认配置，程序接口可显式配置，同库重启须一致。

- destination沿用候选huawei_iotda，但provider明确为mock，不能计真实云C2或联系人C3验收。
- 旧实验库可能缺历史发送快照，明确报错，不重建历史；新seed独立库验证，正式迁移另行设计，不删旧库。
- worker与serve独立运行，缺系统服务监督、统一worker健康、FAILED受控重投、队列容量与保留策略。
- 当前扫描受控小数据量，无吞吐/压力/断电/磁盘损坏结论；两连接测试不等于生产多worker验收。
- 不承诺严格投递顺序或exactly-once；载荷含event_version，未来接收端须去重/版本治理。
- 快照不是数字签名，不防恶意直接改库；第二目的地需先评审唯一键迁移。
- 真实SDK错误/超时映射、回调关联、TLS、许可依赖、jitter留SP-05/Gate3；本批无网络调用。
- R04浏览器验收、完整M6关闭/复发/升级、契约会签与独立验收仍未完成。

后续复核本地Mock与查询接口，再核验真实IoTDA账号/物模型/SDK/证书；条件具备后验证属性、消息、可关联回执及断WAN联合恢复。正式实现按契约门槛迁移，不直接把原型当生产交付。
