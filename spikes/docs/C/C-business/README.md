# C业务实现｜分阶段原型

范围：prototype_only。候选契约未会签，不修改公共Schema/DTO，不接硬件、云或真实联系人。正式迁移仍依契约放行门槛。

## 阶段计划

|阶段|内容|状态|
|---|---|---|
|C-R01|M6水接触策略、ACK状态隔离、DTO边界与反例|限定范围实现并测试；待独立评审|
|C-R02|完整事件投影、唯一OPEN约束、持久化ACK与三表原子事务|R02a/R02b限定范围实现并验证；待独立评审与正式迁移|
|C-R03|本地业务API、错误映射、分页和权限|R03a/b/c限定范围实现并验证；本地启动与timer已装配，正式迁移待评审|
|C-R04|三页与模拟本地闭环、B实际工件交接|R04a/b软件批次收尾；真实B检查点桥接/前端状态/回归通过，浏览器与持续调度待完成，整体PARTIAL|
|C-R05|Mock Outbox调度、退避、恢复及结果关联|待实现|
|C-R06|独立复核与正式迁移准备；硬件/云另行验收|待开展|

## C-R01 决策表

TTL和干燥确认时长由调用者显式传入，无实测默认值。当前仅处理WATER_CONTACT；不擅自定义其他事件或风险升级策略。

|输入|结果|限制|
|---|---|---|
|有效且未过期的true|ACTIVE；无当前事件则建议创建|不等待滑窗；数据库唯一性由下一阶段保证|
|有效false首次到达|UNKNOWN并记录干燥起点|不立即清除|
|连续有效false达到确认时长|CLEARED候选|生命周期不自动RESOLVED/CLOSED，策略待决议|
|干燥证据间隔超过TTL|重新累计|调用方必须持久保存并按序传入干燥链|
|INVALID/UNKNOWN/STALE或过TTL|UNKNOWN并中断干燥链|不得当成干燥|
|未来时间、错设备、错类型、非OPEN当前事件|拒绝|不静默跨设备处理|
|ACK|仅修改ack_status|版本和幂等留事务层；不改变物理状态或生命周期|

`policy.py`是无IO纯策略。`dry_since`和`previous_dry_at`必须来自可信、按序处理的同设备状态，不能由客户端任意提供。当前调用方负责来源引用核验、重复/乱序隔离和boot边界；尚未实现该入口，不声称跨路径去重或端到端集成已完成。

## 接口自检与跨组约定

- A→C：消费正式SafetySignal候选DTO。原始water观测到信号的可信转换仍待实现；不能仅凭source字段授权真实外发。
- B→C：SituationAssessment与安全信号分开；本批不消费情境，因此不存在以ATTENDED_FLOW覆盖水浸的分支。B实际工件联合校验留C-R04。
- C→存储：当前输出Decision内部对象，不伪称完整SafetyEvent/Transition。下一阶段负责身份、版本、唯一性、来源和事务。
- 公共DTO不变；关闭/复发、升级及来源变化与事件历史一致性需形成决议后实现。未知时间不能补成当前时间来延长证据。

## C-R01验证记录

日期：2026-11-02。执行：

```powershell
.\.venv-app\Scripts\python.exe -m pytest spikes/C-business/tests tests/contracts -q -p no:cacheprovider
```

结果：42 passed in 0.84s，退出码0。范围为本批策略及既有DTO/API模型测试；未运行硬件、云、HTTP或全系统验收。

自检修复：最初只传干燥起点可能跨越TTL缺口，补充previous_dry_at和间隔检查，并增加缺口反例。代码与测试由同一开发代理完成，不是独立Reviewer验收。现有SP-06未修改，其他A线在途文件未改动。

## C-R02a｜事件存储与ACK事务

日期：2026-11-02。`store.py`使用SQLite标准库；不修改正式edge服务或公共契约，不复制改动SP-06。

本批实现：完整SafetyEvent投影、EventTransition连续版本、CloudSyncRecord候选DTO校验；数据库部分唯一索引保证(device_id,event_type)仅一个OPEN。BEGIN IMMEDIATE内完成查询/创建，快慢路径即使signal_id不同也返回同一现存事件。重复报告目前不追加证据，证据合并留后续处理。

ACK请求使用正式AckRequest；必须由后端传入authorized=True，HTTP权限机制尚未实现。操作原请求和原响应与事件/transition/outbox同事务持久化；相同键和完整请求重放先返回原响应，旧版本也不会再更新；键相同但expected_version等请求内容改变则冲突。新键重复确认已确认事件为no-op，只保存操作结果，不新增业务版本或Outbox。

错误对象：NotFound、Conflict、VersionConflict（含expected/actual），后续API层映射候选错误格式，当前不宣称HTTP 409已实现。当前源变化明确拒绝，未擅自将事件改成mixed或回写历史transition；需团队决定与现有EventDetailResponse来源一致约束如何兼容。

### 自检与验证

首次联合执行：`python -m pytest spikes/C-business/tests tests/contracts -q -p no:cacheprovider`，53 passed in 1.18s，退出0。

随后补充SQL唯一索引直接反例和新键重复ACK不重复入队；独立执行：`python -m pytest spikes/C-business/tests/test_store.py -q -p no:cacheprovider`，13 passed in 1.82s，退出0。两次范围重叠，不相加；最后新增测试未重跑联合范围。

覆盖创建三写点回滚、ACK三写点与操作记录写入失败回滚、重开后的原响应重放、两个连接并发不同路径创建、并发同键ACK、过期版本、未授权、来源冲突、过TTL信号和完整历史DTO。测试使用临时SQLite数据库；非断电、文件损坏、HTTP或云验收。

自检修正：存储入口补显式有限正TTL校验，防止仅靠调用者承诺；测试补独立导入路径，防止依赖先前测试修改sys.path。均为同开发代理自检，未替代独立Reviewer。

### 下一批R02b（API前完成）

- 将R01策略与持久化入口接通，保存dry_since、previous_dry_at及策略版本。
- 绑定可信观测引用、设备/boot与有序输入；处理重复、乱序、沉默后的UNKNOWN和策略切换。
- 保存ACTIVE/UNKNOWN/CLEARED变化及对应transition/outbox；仍不自动关闭或擅自增加风险升级。
- 当前open_water只负责有效湿信号建事件；TTL之外的时间顺序、引用真实性及boot隔离尚由调用者负责，不能直接作为公共HTTP输入。
- escalation_level必须显式传入，不提供未经实测的默认风险级；关闭/复发与来源变化策略待联合决议。

R02b完成后再开展C-R03 API，避免前端绕过状态机直接操作数据库。

## C-R02b｜水接触持久化入口与超时

日期：2026-11-02。新增`water.py`，WaterService复用R02a事务层，接通R01纯策略。以下为本批结果，替代上节R02b待办中的已实现项。

- 输入先调用正式validate_raw_observation；仅water、原始质量、配置匹配的device/source可进入。SafetySignal由后端生成，引用输入observation_id并从原始source导出origin。当前仅支持RECEIVED_FALLBACK；DEVICE_SYNCED/EDGE_MAPPED缺时钟证据接口时明确拒绝。
- 持久化boot/seq/uptime、最后观测/评估时间、策略版本及参数、干燥起点与上一条干燥时间。重开数据库后可续接。新boot、配置变化、未知、TTL缺口中断干燥链；旧boot回流拒绝。
- 原始身份与内容冲突拒绝；同身份同测量内容重复不延长TTL、不累计干燥时长。接收时间不参与重投内容相等比较；重复返回当前事件，不承诺原响应重放（ACK仍返回原响应）。
- 新输入必须按保守顺序处理：received_at不得早于上次评估时间，seq/uptime不得回退。迟到历史输入拒绝，不回写已经推进的状态；需要A负责未来接入的迟到旁路日志。不同source在事件创建前也不能混用干燥证据。
- ACTIVE/UNKNOWN/CLEARED变化与完整transition/outbox、输入登记、water_state和boot登记同事务。有效干燥不自动关闭，复湿仍在同一OPEN内恢复ACTIVE，保持已有ACK。正式关闭/复发新建及风险升级策略仍待决议。
- expire()显式注入时钟；超TTL后转UNKNOWN并中断干燥链，多次调用不重复追加转换。尚无后台定时循环，调用者必须按时调度。配置变化需由新观测建立，不允许仅靠timer切换。

### 交叉自检记录

1. 决策→存储：校验输出完整SafetyEvent、连续EventTransition与CloudSyncRecord，物理变化不触碰ACK或生命周期。
2. 重启→证据：测试重开后干燥续接、配置/boot/未知/缺口重置、重复干燥不能充当新证据。
3. 时钟→历史：自检补拒绝timer推进后迟到的历史观测；存储层补拒绝transition时间倒退，避免ACK时间落在已提交变化之前。
4. 来源→入口：自检补创建事件前的来源隔离；添加A的真实core.sample/normalize函数输出到C入口测试，验证引用与simulation贯穿。该测试使用模拟数据和直接函数调用，非真实MQTT/硬件验证。
5. 故障→事务：创建/更新的event、transition、outbox与water state写入故障均回滚；timer状态写入失败也不留下半成品。

### 执行记录

先独立运行water专项：14 passed in 1.91s。修复顺序与来源边界后执行：

```powershell
.\.venv-app\Scripts\python.exe -m pytest spikes/C-business/tests spikes/SP-06/tests tests/contracts tests/smoke -q -p no:cacheprovider
```

结果88 passed in 10.82s，退出0。随后新增A实际标准化接口场景，独立执行`spikes/C-business/tests/test_water.py`：17 passed in 2.38s，退出0。数量重叠不相加；新增接口测试后未重复全范围。当前为同开发代理从规则、接口、故障三方面交叉自检，不是独立Reviewer验收。

### 保留边界与下阶段

- trusted_device/source来自受信后端配置；本模块不认证设备，不凭调用者提供的source授权真实通知。引用真实性仍依赖A的受信接入，未实现签名或跨服务原始工件解析。
- fallback接收时间不能重建离线补发的真实测量时间；当前无法凭DTO识别所有补发，应由A输入链禁止其作为当前物理清除证据。
- water_inputs/boot历史无容量与保留策略，适用于受控原型。尚未覆盖并发boot竞争、压力、掉电/损坏或多worker。
- open_water()保留R02a低层实验入口；R02b集成统一走WaterService.ingest，不混用绕过water_state。已存在低层实验事件的数据库应使用独立新实验库，不宣称提供迁移。
- 事件origin变化明确拒绝，未决定合并语义；TTL/clear/risk必须显式配置，不宣称实测最优。
- B情境工件接入留C-R04；公共契约、edge服务和SP-06代码未修改。下一批C-R03实现查询、ACK错误映射、分页与受控权限，不暴露原始存储变更接口。

## C-R03a｜本地事件API

日期：2026-11-02。新增api.py独立应用工厂，未合入edge/app.py，不部署、不启动公网服务。

已实现GET /api/events、GET /api/events/{event_id}、POST /api/events/{event_id}/ack，均使用公共候选响应模型；ACK请求使用AckRequest，变更仍由存储事务核准。全部路由要求后端注入Bearer token；token无默认值，至少24字符，分页签名key至少32字节，禁止写入真实密钥。当前是单角色实验权限，不是账号系统或设备级授权。

列表支持device_id/lifecycle/limit及带HMAC的opaque cursor，绑定过滤条件，按解析后的时间瞬间与event_id倒序；同时间戳不漏项、跨时区不按字符串误排序。当前受控原型在内存中排序，不提供大数据量性能承诺或跨多页快照隔离；签名key变化后旧cursor失效。

错误按候选ApiError返回：400 BAD_REQUEST、401 UNAUTHORIZED、404 NOT_FOUND、409 VERSION_CONFLICT/IDEMPOTENCY_CONFLICT、SQLite异常503 SERVICE_UNAVAILABLE；错误不暴露SQL和内部异常。版本冲突包含expected/actual，request_id由后端生成。存储新增IdempotencyConflict子类，避免把所有业务冲突都错误命名为幂等冲突。

自检覆盖：权限先于写入、ACK原响应重放、两类409、请求校验、缺失事件、同时间分页、cursor篡改/过滤条件错配、时区排序、实际SQLite表缺失后的503脱敏和事务不变。测试通过ASGI请求/响应调用真实FastAPI应用及临时SQLite，无额外HTTP客户端依赖；未验证真实网络监听、TLS、浏览器或线上部署。

执行命令：

```powershell
.\.venv-app\Scripts\python.exe -m pytest spikes/C-business/tests spikes/SP-06/tests tests/contracts tests/smoke -q -p no:cacheprovider
```

结果95 passed in 12.54s，退出0。包含API六个测试及此前回归，不与历史数量累加。仍为同代理交叉自检，非独立验收。

下一批R03b：补实时/情境查询投影与同步统计、受控实验查询；先定义可信投影写入边界，缺数据明确不可用，不生成虚假三源状态。然后提供可重复的本地启动/演示入口，再做C-R04三页与B工件交接。

## C-R03b｜查询投影与产品后续路线

执行跨日：2026-11-02至11-03。新增projections.py及四条路由：live、assessment、sync/status、experiments/{trial_id}；现在隔离应用的OpenAPI包含七条候选路径。正式edge/app.py和web仍未接入本批代码。

实时与情境投影仅由受信后端publish，入口校验公共模型、身份、来源及部分时间关系；没有公开写HTTP接口。发布时显式提供TTL，数据库保存captured_at/TTL；查询不刷新证据时间。无记录404，过期或未来投影503，不伪造三源读数。实验记录同样持久化且需Bearer权限，当前共享单角色实验token，并未实现多角色admin权限体系。

同步统计从事件/transition关联的实际Outbox读取，区分待发、失败与记录中的确认层级；无回执保持NONE。ACCEPTED缺传输回执等持久化损坏数据返回503，不以空列表或正常状态掩盖异常。统计不代表当前云在线，Mock回执也不等于真实IoTDA或联系人收到。

### 自检与验证

- 首轮投影专项2失败1通过：测试比较等价UTC写法Z与+00:00而误报，改为统一预期格式；业务实现未为此放宽时间校验。
- 相关回归命令同R03a（C业务、SP-06、contracts、smoke）：98 passed in 11.16s，退出0。
- 随后补齐四路权限、过期情境、损坏回执503及七路由OpenAPI检查，专项`python -m pytest spikes/C-business/tests/test_projections.py -q -p no:cacheprovider`：9 passed in 5.80s，退出0。范围重叠不累加；最后修订后未再次执行全范围。
- 读投影不改业务事件；临时SQLite重开仍保留投影；device信号错配与相同时间冲突拒绝。均为同代理接口/持久化/故障交叉自检，未替代独立Reviewer或真实网络验收。

### 后续与限制

产品范围、终端与IoTDA关系统一见[C业务、终端与云协同路线](../C_PRODUCT_ROADMAP.md)。下一批R03c补可重复启动/演示与timer装配，再开展R04三页。远程云后台与联系人通知为后续范围，不能因IoTDA连接成功就记完成。

publish的captured_at、TTL与引用真实性仍依赖受信后端，尚未接B实际窗口工件核验；禁止用当前发布时刻给旧情境重新续命。实时DTO中的age是captured_at时刻的快照年龄，前端需结合captured_at表达陈旧程度。系统不自动生成实时投影、实验结果或云连接状态，尚无查询性能、通知、真实硬件/云或浏览器完成声明。

## C-R03c｜本地启动、演示与timer装配

日期：2026-11-03。新增run.py（seed/serve）与[本地演示手册](LOCAL_DEMO.md)。服务仅127.0.0.1，默认8010；token/key显式环境注入，启动不自动seed，不改edge服务。演示库独立且已加入局部.gitignore。

seed仅新建文件，生成simulation水接触与降级三源快照、明确未执行B推断的UNKNOWN情境、PLANNED实验；不覆盖已有库或宣称真实采样。初始化参数显式给定。serve每0.25秒推进water timer，启动先检查过期，退出等待当前timer结束；不会给旧投影续命。/health显示timer健康，故障返回503 degraded，不暴露内部异常。

自检重点：输入证据→timer→事务→HTTP与ACK版本一致性；恢复后不重复创建事件或刷新旧证据；配置缺失不改库。自检补单设备失败不阻塞其他设备尝试、整体健康仍降级。补测试时曾发现重启断言位置被插入新测试，读回文件后立即恢复到原用例，最终回归包含重启检查。

执行：`python -m pytest spikes/C-business/tests spikes/SP-06/tests tests/contracts tests/smoke -q -p no:cacheprovider`，109 passed in 37.71s，退出0。包含5项运行专项：seed防覆盖、启动即时过期与lifespan退出、真实HTTP timer/ACK/重启、缺凭据、timer故障可见；全范围与历史重叠，不累计。真实网络进程停止采用terminate，不声称实际Ctrl+C或断电验证。

仍未独立Reviewer验收；真实IoTDA/硬件、页面、B实际推断工件及正式部署均未完成。下一阶段C-R04：业务三页、API交互与受控B工件联合，继续按每批自检/实跑/限制更新记录。

## C-R04a｜本地业务三页与B历史工件边界

日期：2026-11-03。新增web/c.html、src/c-main.jsx、src/c.css；保留原index.html/main.jsx连接检查入口。Vite双入口构建；开发模式/api代理8010（可用AQUAGUARD_C_PORT调整），原/health代理8000不变。run.py在启动时若检测到dist/c.html与assets，就提供/c.html及根路径页面，API与页面同源；无构建产物仍可只运行API。

三页已编写：实时总览（来源/质量/快照时间/三源年龄/覆盖、情境与独立安全信号、同步）；事件确认（独立生命周期/确认/物理状态、历史、ACK、JSON导出）；实验诊断（受控查询/导出，无执行回放/通知入口）。每5秒轮询；401/404/503明确提示，旧响应中止；凭据仅内存保存，不入URL或storage。ACK锁定提交、使用expected_version和随机幂等键；网络结果不确定时保留原请求，409后刷新并要求用户重新核对。

自检修复实验查询响应竞争：设备/token/trial变化或新查询后忽略旧响应，避免显示错实验。事件列表当前仅最新100项，未增加前端翻页。未实现复杂账号、联系人、关闭事件或回放执行功能。

B接口：新增import_b.py，以新独立数据库导入SP-03窗口、SP-03-features特征和SP-04情境的实际历史JSON。先检查三组window_id集合一致、无重复、device一致和simulation来源，再写查询投影。保留window_end/published_at，不刷新成当前时刻，不创建安全事件，不从情境猜安全信号。此为DTO与引用匹配验证，不重算B算法、不恢复绝对路径checkpoint、不证明原始观测来源真实性；历史数据在当前时钟下查询503是正确行为。导入不提供历史交互回放；写入中断可能留不完整新实验库，换新路径重试，不宣称跨工件原子迁移。

### 验证与边界

- npm run build最终通过，baseline和business双入口均产出。
- 首轮B专项受系统临时盘空间不足影响，出现SQLite disk full与临时目录失败；换用工作区忽略目录并创建父目录后执行相关回归。
- `python -m pytest spikes/C-business/tests spikes/SP-06/tests tests/contracts tests/smoke -q -p no:cacheprovider --basetemp spikes/C-business/local/check-r04-all01`：112 passed in 20.61s，退出0，包含3项B实际历史工件测试。
- 补HTTP页面/脚本交付检查后，runtime专项使用新的check-r04-runtime01临时目录：5 passed in 8.69s，退出0。检查时dist存在，实际读取c.html及构建JS成功；与全回归范围重叠，不累计。
- 浏览器验证工具连接启动失败，未能开展实际点击、视觉与移动端检查；构建和静态HTTP成功不替代浏览器E2E。当前R04整体PARTIAL，不宣布三页验收通过。

下一批R04b：恢复浏览器验证，检查登录/切设备/过期、ACK重放与409、实验导出及移动布局；补受控连续B输出的可信工件桥接。之后R05完善Outbox运行。仍为同代理交叉自检，独立Reviewer待指定。

## C-R04b软件收尾

2026-11-03：[阶段收尾报告](../C_R04_STAGE_REVIEW.md)汇总本阶段交付、自检修复、实跑和未完成项。新增b_bridge.py，直接调用B真实gate/classify与本机生成的检查点；校验受控根、摘要/重算、版本、身份、模拟来源和窗口时效。实时/情境投影同事务发布，重复调用不延长有效期；不从情境生成或清除安全事件。

前端提取AckIntent/ResponseOrder，修正“ACK响应丢失但轮询已确认”时重试按钮被禁用的边界。3项Node状态测试与最终双入口构建通过。C及相邻回归115 passed in 25.14s，退出0；B专项3项通过，范围重叠不累计。

系统盘为0，浏览器工具重试失败；未清理用户文件。改用工作区独立临时目录测试。真实浏览器点击/视觉、移动布局与完整E2E未验收；桥接为后端逐窗口调用函数，尚无自动输入调度。R04软件批次收尾，但整体维持PARTIAL。下一批可推进R05本地Mock worker，同时保留R04浏览器清单与独立Reviewer待办。
