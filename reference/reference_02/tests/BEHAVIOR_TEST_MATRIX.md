# 需要各模块开发后落实的行为契约测试（优先级 P0）

|ID|输入/操作|必须保证的断言|负责人|
|---|---|---|---|
|CT01|人体传感数据缺失|presence=unknown，绝不转为false|A+B|
|CT02|同 `(device,boot,sensor,seq)` 重放|同一观测只处理一次；不同boot不冲突|A|
|CT03|按到达时间乱序（有效事件时间）|窗口结果按事件时间，既有事件不悄悄回写|B|
|CT04|长时间某路沉默|窗口以处理时间截止发布，质量DEGRADED|B|
|CT05|有效水浸+ATTENDED_FLOW|水浸本地提醒仍出现|B+C|
|CT06|快速水浸和周期水浸同发|只一个活动event_id|C|
|CT07|用户确认、探头仍为wet|ACKNOWLEDGED+ACTIVE+OPEN|C|
|CT08|重复确认同幂等键|仅一个transition；同键不同payload报409|C|
|CT09|提交事务中途抛错|event/transition/outbox全部回滚|A+C|
|CT10|WAN断连期间发生异常|本地事件和页面提醒成功，Outbox待发|A+C|
|CT11|恢复后发送同transition多次|message_id稳定，确认层级明确|A|
|CT12|同trial相邻窗口|不可跨train/test分组|B|
|CT13|未知设备时钟|event_time=null或低质量映射；不会谎报精准时间|A+B|
|CT14|浏览器重复/陈旧版本ACK|expected_version冲突返回409|C|
|CT15|simulation试验|不得调用真实联系人通知|C|
|CT16|在线和离线相同回放与时间配置|相同 FeatureWindow 数值和缺失标记|B|

上述是**行为测试契约**，配套初始JSON Schema烟雾测试。每位主责人必须在对应Issue实施pytest/集成测试，不能把未编写的行为测试声称已自动通过。
