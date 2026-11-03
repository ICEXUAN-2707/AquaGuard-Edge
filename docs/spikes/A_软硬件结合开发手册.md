# A 软硬件结合开发手册

硬件购入后的下一阶段按 [实物实验设计与执行方案](A_实物实验设计与执行方案.md) 执行，包含实验矩阵、软件工作包、计量与时间对接限制；具体配置仍须匹配实物手册。

采购复核见 [A采购确认](A_采购确认.md)。真实MQTT重启验证入口见 [SP-02 README](../../spikes/SP-02/README.md)；该验证不代替持续断网恢复或实物联调。

版本0.1，2026-10-29，prototype_only。当前是软件台架部署与后续硬件联调操作框架；实际硬件参数尚未批准。

## 1. 部署拓扑与阶段

阶段一：Windows电脑上运行模拟发布器、本机Mosquitto、Python订阅器和实验SQLite。Broker监听127.0.0.1，不需要硬件或云。

阶段二：ESP32连接受控局域网Mosquitto，电脑订阅器标准化三源观测。此时必须另行配置LAN监听、认证、Topic权限和防火墙来源范围；回环配置不能供ESP32连接。硬件接入功能尚待实现，不直接运行当前固定simulation入口接收硬件数据。

阶段三：导出唯一完整DTO交B回放。IoTDA由C另行验收，本手册不部署云资源。

## 2. 软件台架部署

在仓库根目录运行，已有环境可复用：

```powershell
python -m venv .venv-app
.\.venv-app\Scripts\python.exe -m pip install -r requirements-app.lock.txt
.\.venv-app\Scripts\python.exe -m pytest spikes/SP-02/tests/unit -q
```

从Mosquitto官方获取Windows安装包：https://mosquitto.org/download/ 。安装路径及版本写入实验记录；不要同时启动服务实例与实验实例占用相同端口。安装属于环境变更，应记录安装内容。

独立终端启动本机Broker，以下路径按实际安装位置替换：

```powershell
& 'C:\Program Files\mosquitto\mosquitto.exe' -c spikes/SP-02/config/mosquitto-local.conf -v
```

生成输入并启动订阅；等待READY后在另一个终端发布：

```powershell
.\.venv-app\Scripts\python.exe spikes/SP-02/src/cli.py generate --directory spikes/SP-02/data/run01
.\.venv-app\Scripts\python.exe spikes/SP-02/src/cli.py subscribe --directory spikes/SP-02/data/run01 --seconds 30
.\.venv-app\Scripts\python.exe spikes/SP-02/src/cli.py publish --directory spikes/SP-02/data/run01
```

订阅完成后统计与导出：

```powershell
.\.venv-app\Scripts\python.exe spikes/SP-02/src/analyzer.py spikes/SP-02/data/run01
.\.venv-app\Scripts\python.exe spikes/SP-02/src/cli.py export --directory spikes/SP-02/data/run01
```

每轮用新目录。summary.json必须核对missing/unexpected及错误分类，不只看总数。当前统计PASS仅代表本轮身份集合及分类检查，不代表所有故障或硬件验收通过。

停止时Ctrl+C退出各自实验进程，不停止其他人员共享的Broker。先保留证据再清理；不在仓库记录密码或密钥。

## 3. 到货与手册核验

每个设备拍摄正反面、型号、接口和包装标签；登记实际板卡/模块版本。收集厂家用户手册、板卡原理图及雷达UART协议，记录版本、URL、SHA256和适用实物。没有匹配手册的设备暂不接线。

逐项填写下表，不允许以教程或购物标题替代：

|设备|参数项|手册版本/页码|确认值|代码配置|复核人|
|---|---|---|---|---|---|
|ESP32|供电入口、引脚限制、UART资源|待补|待确认|待实现|待指定|
|YF-S201|供电、信号电路、电平、计数关系|待补|待确认|待实现|待指定|
|FC-37|模块版本、AO/DO、电平、极性|待补|待确认|待实现|待指定|
|LD2410C|供电/逻辑电平、UART参数、帧格式|待补|待确认|待实现|待指定|

输出接线表：模块引脚→适配电路→ESP32引脚，逐项引用资料。由有经验成员复核后再上电。仅低压隔离桌面台架；水路与电子部分隔离，不接真实家用管网或改动市电。

## 4. 固件部署步骤（待手册核对后启用）

1. 确认框架/编译器/板型并固定版本，保存干净构建命令。当前没有可烧录固件，不提供猜测的引脚或串口配置。
2. 先不接传感器，验证串口日志、设备身份、重启boot_id变化和uptime。
3. 依次接入单个传感器，每次断电接线、复核后上电；记录原始脉冲/电平/字节帧。
4. UART解析严格对应所购雷达协议，先运行协议fixture，再比对实物原始帧。状态无法映射到候选DTO时记录问题，不强制改成false。
5. 单源稳定后启用三源调度和MQTT；实测周期、缓冲容量与恢复，不把框架编译成功当作实物通过。

## 5. 现场联调与验收

水流至少5次已知体积标定，另留复测，记录体积/时长/脉冲/误差/calibration_id；干湿至少10次，记录原始与消抖结果；人体测试静止/移动/无人/拔线及恢复。无法区分无脉冲和断线时明确能力限制。

每条实物观测能追溯到串口原始值、固件版本、设备身份、MQTT记录和DTO。验证设备重启后身份变化，重传不变；断网不伪造零流量、干态或无人。

故障分别注入发布器退出、订阅器退出、Broker退出、网络断开。记录开始/恢复时间、缓存/会话配置、缺失与重复，不承诺未实现的断电补发。

## 6. 排障与交付

连接失败：检查Broker进程、端口和监听地址；LAN阶段检查认证/防火墙，不关闭安全配置凑通过。
数据无效：查received.jsonl的原始报文与error，核对协议版本、来源、身份和value类型。
读数异常：回到手册、电气测量与原始串口数据，不先修改业务规则。

交付环境版本、配置脱敏副本、手册追踪表、接线复核、原始日志、summary.json、accepted.jsonl和逐场景报告。Owner不可自验收；Reviewer尚待组内指定。
