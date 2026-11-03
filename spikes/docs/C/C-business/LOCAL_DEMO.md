# C本地原型启动与演示

更新：2026-11-03。prototype_only，使用模拟水接触，不连接硬件、IoTDA或联系人。仅监听127.0.0.1；手机LAN访问与远程部署尚不支持。正式edge服务仍独立，默认8000；本原型默认8010。

## 1. 初始化新实验库

从仓库根目录运行，使用已安装requirements-app.lock.txt的.venv-app。TTL/clear为演示参数，不代表实物推荐值。

```powershell
.\.venv-app\Scripts\python.exe spikes/C-business/run.py seed --db spikes/C-business/local/demo01.sqlite --ttl 30 --clear 2
```

只允许新文件；已存在则报错，不清库、不覆盖事件。需要重做演示时换新文件名。输出仅包含prototype标记、device_id与event_id，记下事件ID。

初始化一次模拟湿观测与事件，并发布一个三源降级快照：仅water有瞬时湿证据，flow/presence未知，覆盖时长未计算所以均为0。情境为UNKNOWN/UNAVAILABLE，标记DEMO_NO_B_INFERENCE；不是B算法计算结果。实验查询返回PLANNED，不伪称实验已完成。

## 2. 启动服务

生成并在本机妥善保存实验token；另一查询终端需输入同一token。不要把凭据写入仓库或聊天记录。重启需要保留分页key才能继续使用旧cursor。

```powershell
$env:AQUAGUARD_C_TOKEN = [guid]::NewGuid().ToString('N')
$env:AQUAGUARD_C_CURSOR_KEY = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
.\.venv-app\Scripts\python.exe spikes/C-business/run.py serve --db spikes/C-business/local/demo01.sqlite --port 8010
```

初始化后尽快启动。数据超过30秒会正常过期，服务不会刷新演示证据。健康检查http://127.0.0.1:8010/health不含业务数据，其他七条查询/ACK路由都需Bearer token。当前根路径没有业务页面。

## 3. 查询与确认

另开PowerShell终端，输入启动前保存的token：

```powershell
$demoToken = Read-Host '输入本机实验token'
$demoHeaders = @{ Authorization = "Bearer $demoToken" }
$demoBase = 'http://127.0.0.1:8010'
Invoke-RestMethod "$demoBase/health"
$demoPage = Invoke-RestMethod "$demoBase/api/events" -Headers $demoHeaders
$demoPage.items
$demoEventId = $demoPage.items[0].event_id
$demoDetail = Invoke-RestMethod "$demoBase/api/events/$demoEventId" -Headers $demoHeaders
$demoAckBody = @{ schema_version='1.1'; expected_version=$demoDetail.event.version; idempotency_key='manual-ack-01'; ack_type='ACKNOWLEDGE' } | ConvertTo-Json
Invoke-RestMethod "$demoBase/api/events/$demoEventId/ack" -Method Post -Headers $demoHeaders -ContentType 'application/json' -Body $demoAckBody
Invoke-RestMethod "$demoBase/api/sync/status" -Headers $demoHeaders
Invoke-RestMethod "$demoBase/api/experiments/demo-trial" -Headers $demoHeaders
```

ACK与timer可能竞争版本，若返回VERSION_CONFLICT，重新查询后用新幂等键及新expected_version提交。同键原请求重放返回原操作结果；同键更改请求内容返回IDEMPOTENCY_CONFLICT。

在TTL内查询`/api/devices/demo01/live`和`/api/devices/demo01/assessment`可见模拟投影；过期返回503，不伪造成正常。超时后事件physical_status为UNKNOWN，ACK状态、生命周期与云同步分开；本地Outbox仍PENDING，last_ack_level为NONE。

## 4. 停止、重启与故障

服务终端Ctrl+C停止；使用相同数据库与环境变量重启。应用启动先推进持久化证据的超时判断，再接收请求；不重复seed。生命周期退出会通知timer停止并等待当前处理结束。

|现象|含义与处理|
|---|---|
|缺token/key，退出2|按步骤配置；凭据校验先于数据库打开|
|数据库不存在|先seed新库或指定已有C水接触库；不自动生成演示数据|
|seed文件已存在|换实验文件名，保留历史库|
|端口占用|另选端口，不终止其他服务|
|查询401|token缺失/不一致；实验token不是华为云凭据|
|实时/情境503|可能是投影正常过期；不要刷新captured_at凑实时|
|health为503 degraded|timer处理失败；排查库、配置、时钟；不等于传感器一定损坏|
|同步NONE/PENDING|尚无worker/云回执，符合当前阶段|

仅单进程单实例使用一个库。尚未实现多服务互斥、数据保留/容量、运行日志轮转及迁移；不要把SP-06库或R02a低层库混作本演示库。环境变量和本地SQLite不随Git交付。

## 5. 已验证边界

R03c测试包含真实loopback HTTP、timer过期、ACK、终止并重启后的幂等恢复，以及缺凭据不创建数据库。真实进程测试使用terminate模拟进程停止；正常生命周期收尾另通过lifespan测试验证，不声称已测试操作系统掉电或实际Ctrl+C信号。

健康接口返回ok只代表本原型timer最近推进成功，不代表三源、B算法、IoTDA或整个项目验收。

## 6. 业务三页入口（R04a）

先构建，再启动/重启C服务，使其装配构建产物：

```powershell
Push-Location web
npm.cmd run build
Pop-Location
```

之后按第2节启动serve，浏览器打开http://127.0.0.1:8010/c.html，输入实验token与demo01。凭据不保存到浏览器storage，刷新后重新输入。页面包含实时总览、事件确认、实验诊断；根路径同样提供该页面。若服务启动时还没有dist，构建后需重启服务。

开发模式可在web执行npm.cmd run dev后访问Vite显示地址的/c.html；/api默认转发8010，原index.html的/health仍转发8000。Vite预览不配置业务代理，优先用C服务提供构建页面。

TTL过期时实时/情境不可用是预期；事件历史、ACK与同步查询仍可使用。前端每5秒读取，不自动生成新观测；需要新鲜演示时用新文件名seed，不篡改旧库时间。列表仅最新100项。当前页面尚未实际浏览器验收，网络资源验证与构建已通过。

## 7. B实际历史工件接口实验

必须使用独立新库，不能覆盖demo01：

```powershell
.\.venv-app\Scripts\python.exe spikes/C-business/import_b.py --db spikes/C-business/local/b-history01.sqlite --windows spikes/SP-03/evidence/r06_windows.json --features spikes/SP-03-features/evidence/r07_feature_windows.json --assessments spikes/SP-04/evidence/r03_assessments.json --ttl 30
```

只校验并导入simulation历史查询投影，保留2026-10-29原时间；不刷新旧工件、不创建事件。该库serve后设备是demo，当前时钟查询会返回503过期。测试在工件原时钟验证内容一致；这不是实时B推断或交互回放演示，不能用它证明当前情境准确率。

## 8. 临时盘不足时运行测试

使用工作区local下从未使用过的独立目录，并先创建local父目录。pytest可能清理指定basetemp，禁止指向有价值的数据目录或演示库目录本身。

```powershell
New-Item -ItemType Directory -Force spikes/C-business/local | Out-Null
.\.venv-app\Scripts\python.exe -m pytest spikes/C-business/tests -q -p no:cacheprovider --basetemp spikes/C-business/local/review-new-01
```
