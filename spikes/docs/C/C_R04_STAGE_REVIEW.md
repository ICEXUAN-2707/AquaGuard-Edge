# C-R04阶段收尾报告

日期：2026-11-03。结论：**本轮软件开发与可执行检查收尾；R04整体PARTIAL，浏览器E2E/视觉、持续在线装配及独立评审尚未完成。** 不以环境阻塞代替通过，不修改候选合同或扩大真实安全承诺。

## 1. 本阶段交付与全局作用

|交付|文件|作用|
|---|---|---|
|用户三页|web/c.html、src/c-main.jsx、c.css|把C事件、查询与ACK呈现给本地用户；不替代IoTDA、不增加真实通知|
|前端状态保护|web/src/c-state.js|ACK不确定重试保留键/版本，切事件隔离；旧实验响应不覆盖新上下文|
|页面运行交付|spikes/C-business/run.py|构建后通过C服务同源提供页面和API，保留原连接检查入口|
|历史B接口|import_b.py|匹配实际窗口/特征/情境工件，保留原时刻；只导入模拟历史，不伪装实时|
|检查点支撑的B桥接|b_bridge.py|调用现有B gate/classify重算与校验，单个新窗口产生可信根目录内的查询投影|
|双投影原子发布|projections.py|实时/情境同事务更新，任一冲突整体回滚，避免页面读到半批新数据|

全局链路现在有：A标准化输出→C快速湿事件的接口测试；B实际检查点/规则→C查询投影；C事件/Outbox→API→已编写的页面。页面点击链路尚待浏览器验收，不能宣布完整端到端产品已验收。

## 2. 交叉自检与修复

1. **业务与页面**：生命周期、ACK、物理状态分别显示；过期503不当正常；云同步与传感健康分开。
2. **ACK与轮询竞争**：原实现网络结果不确定后可能被轮询到的ACKNOWLEDGED禁用按钮。现保留原操作并显示“重试原确认请求”，同事件即使版本已推进仍重放原键/原版本；409后清除操作并要求重新核对。
3. **上下文与异步响应**：实验token/device/trial变化或新请求使旧响应失效；提取ResponseOrder并测试。重构后逐处检查调用，修正残留旧计数写法。
4. **B引用与时效**：校验DTO、受控checkpoint根、内容摘要及重算一致性；投影有效期锚定window_end，不使用本次调用时间续命。WINDOW_STALE拒绝发布。
5. **安全与情境**：ATTENDED_FLOW与有效湿事件可以并存；B桥接不生成/清除安全事件、不伪造SafetySignal。实际来源授权与设备时钟仍依赖A可信入口。
6. **查询一致性**：实时和情境原子发布；人为构造第二投影冲突后，第一投影写入也回滚。

## 3. 实跑证据

|检查|命令/范围|最终结果|
|---|---|---|
|B检查点桥接专项|pytest spikes/C-business/tests/test_b_bridge.py，工作区check-r04b-bridge01|3 passed in 0.99s|
|C及相邻回归|pytest spikes/C-business/tests spikes/SP-06/tests tests/contracts tests/smoke -q -p no:cacheprovider --basetemp spikes/C-business/local/check-r04b-all01|115 passed in 25.14s，退出0|
|前端状态|web目录：node --test tests/c-state.test.js|3通过，0失败|
|最终前端构建|web目录：npm.cmd run build|成功，baseline/business双入口|

所有数量与历史存在重叠，不相加计算项目完成率。真实HTTP资源、timer/ACK/重启测试包含在相关回归中；不是浏览器点击测试。

环境：C盘剩余0，沙箱无法写启动日志；浏览器工具重试仍启动失败。命令在获准的沙箱外运行，测试临时库放在D工作区忽略目录，没有删除系统或用户文件。独立Reviewer尚未指定；这里的交叉自检为同开发代理从不同接口/故障角度复核。

## 4. B桥接接入方式与限制

内部调用入口为`b_bridge.publish_window(queries, feature_window, now=带时区时间字符串, checkpoint_root=受控目录, config=可选规则配置)`。每个新FeatureWindow由后端调度调用；桥接自身不是MQTT订阅器、目录watcher或完整在线调度器。

桥接先调用B gate核对根目录、摘要、特征版本、window和时效，再调用B classify；仅允许simulation，保留window_end作为投影证据时间。测试在当前机器新生成真实M4检查点并执行B规则，覆盖有人用水与独立湿事件并存；并非只加载历史情境JSON。测试复用B的合成fixture，不是真实传感trial。

当前不接硬件origin、不从慢窗口生成快信号，不修改事件物理状态；fast水接触仍走WaterService.ingest。实际运行中的源授权、配置注册、版本升级、boot/迟到策略、容量与持续输入生命周期须正式集成补齐。

## 5. 当前进度与下一步

|部分|状态|
|---|---|
|R01水接触策略、R02事务/证据、R03七路API与本地运行|限定原型范围已实现并回归；独立评审未完成|
|R04页面与B接口软件|本批收尾，构建/接口/状态/故障测试通过|
|R04浏览器视觉、点击、移动布局、完整E2E|未完成；环境阻塞，R04整体仍PARTIAL|
|自动持续B生产→桥接调度、完整正式M6策略|待完成；不能因桥接函数存在就记在线集成完成|
|R05业务Outbox退避/调度/结果关联|待开发；目前Outbox待发可见，SP-06仅Mock技术原型|
|真实IoTDA、实物联合与独立交付验收|待完成|

下一批可并行推进R05的本地Mock worker，另保留R04浏览器待办；系统盘环境恢复后优先补页面连接、切设备、过期、ACK丢响应重试、409、导出及手机窄屏检查。远程后台与联系人通知仍按[C产品路线](C_PRODUCT_ROADMAP.md)单独管理，不计入已完成成果。
