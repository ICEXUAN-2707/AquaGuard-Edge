# G1 第二批交叉自检

日期：2026-11-05。范围为隔离模拟原型，公共 DTO 和已冻结 Schema 未变。

|检查|实现与证据|边界|
|---|---|---|
|时序与来源|周期写入前重新 gate/classify 检查点；仅 simulation；持久拒绝旧窗口和同时间不同 assessment|不证明硬件时钟可信|
|事件去重|数据库唯一 OPEN 键；周期水接触与快路复用 open_water；情境风险独立类型|OPEN 尚不自动 CLOSED|
|ACK 正交|持续输入→ACK→expire→重启复用事件测试|ACK 不等于物理清除|
|事务|故障注入 outbox 后 event/transition/outbox/context_state 全回滚；重放只写一次|投影发布与事件提交仍为两个事务，失败时 health 降级，不宣称整条流水线原子|
|过期|情境定时转 UNKNOWN；查询投影 TTL 拒绝过期；water 只展示窗尾前的新鲜证据|完整关闭、升级和长期容量仍待实现|
|用户读取|ASGI HTTP 实际 assessment/events 响应包含安全信号和两类事件|尚未浏览器点击/视觉验收|

本轮修正：定时器独立启动时 B 引擎导入路径；时间过滤改用带时区 datetime，避免字符串时区格式比较；水接触信号时间不超过投影时间，包含迟到等待的年龄预算；所有现有启动调用保持 simulate=False 默认行为。

测试命令：`.venv-app/Scripts/python.exe -m pytest spikes/C-business/tests tests/contracts tests/smoke -q -p no:cacheprovider --basetemp=audit/g1-regression-03`。实跑 **116 passed in 42.59s，退出码 0**；不将历史测试数量相加。前端未修改，沿用上一批构建通过结果，不将其视作浏览器验收。

冻结清单表示 G0 当时输入，不随 G1 实现变更重写。本轮尚未提交或推送；不包含测试临时目录。G0 联合签署/资源核验和 G1 正式运行/浏览器验收仍未完成。
