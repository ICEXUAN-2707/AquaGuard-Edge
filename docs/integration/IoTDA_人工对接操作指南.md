# IoTDA 人工对接操作指南（SP-05）

**用途：** 由 C 在华为云控制台人工准备测试产品/设备，验证 IoTDA MQTT 接入、属性/消息上报和平台可见证据。本文针对技术 Spike；测试设备和数据标注为 `prototype_only`，结果不等于真实家庭部署或业务联系人送达验收。

## 0. 先确认本次要走的设备路径

仓库当前方案是 ESP32/传感器先通过局域网 MQTT 到边缘 Python 服务，再由边缘侧负责 IoTDA 上报。SP-05 的目标是验证边缘到 IoTDA 的接入与回执。

华为官方 Python IoT Device SDK 面向有一定运算和存储能力的设备；本项目是否把边缘盒子作为 IoTDA“逻辑设备”连接，需要在 Spike 报告中明确。**不要同时让 ESP32 与边缘盒子使用同一个 IoTDA deviceId 建立连接**：官方限制单个 MQTT 直连设备同一时间只有一个连接。建议测试时为边缘服务单独注册测试设备，与物理 MCU 的设备身份区分。

本次先做单设备、单产品、MQTTS 8883 的验证；暂不创建规则引擎、数据转发、应用侧 AK/SK 或联系人通知。

## 1. 准备控制台资源

1. 登录华为云，进入“设备接入 IoTDA”控制台，选择已有且获准使用的实例。确认区域、实例版本/规格和可能产生的费用；未获授权时先停在这里，不创建付费资源。
2. 在实例“总览”页进入“接入信息”，记录 MQTT/MQTTS 接入域名、端口和区域。域名必须来自所选实例，不能从示例代码照抄。
3. 左侧进入“产品”并创建一个仅供 Spike 的 MQTT 产品：数据格式选 JSON，行业/设备类型按页面要求填写。名称可用 `AquaGuardSpike`。
4. 进入产品功能定义，为测试产品建立一个简单服务，例如 `SpikeProbe`，添加只读属性 `probe_counter`（整数）和 `source_tag`（字符串）。属性名、类型和 `service_id` 后续必须与上报 JSON 完全一致。这是临时测试模型，不是最终 AquaGuard 物模型。
5. 进入“设备 > 所有设备 > 注册设备”，选择刚建的产品。标识码和名称用清晰的测试值，例如 `aquaguard-spike-edge-01`；选择密钥鉴权。密钥可由平台生成。保存 Node ID、设备 ID、密钥和所属产品；密钥只保存在个人安全位置或本地环境变量，不写入 Issue、截图、日志或 Git。
6. 在设备详情页打开 MQTT 连接参数，确认生成参数对应当前实例和设备。

官方控制台步骤见[注册设备快速入门](https://support.huaweicloud.com/qs-iothub/iot_05_0009.html)。设备连接域名从实例“总览 > 接入信息”获取，见[MQTT 接入常见问题](https://support.huaweicloud.com/iothub_faq/iot_faq_01006.html)。

## 2. 配置安全连接信息

把下列值记录在本机私密配置中，不要提交到仓库：

```text
IOTDA_ENDPOINT=<控制台接入信息中的设备侧域名>
IOTDA_PORT=8883
IOTDA_DEVICE_ID=<平台生成的 deviceId>
IOTDA_DEVICE_SECRET=<注册设备时生成/设置的 secret>
IOTDA_CA_CERT=<华为云 IoTDA 对应接入域名的服务端 CA 证书路径>
```

优先使用 MQTTS 8883 并校验 CA 证书。华为文档说明 MQTT 明文链路不加密；MQTTS 需要设备侧加载服务端 CA。证书必须与当前区域和接入域名匹配，不能通过关闭证书校验来排查问题。[MQTT 使用指导](https://support.huaweicloud.com/devg-iothub/iot_02_2200.html) · [密钥鉴权](https://support.huaweicloud.com/devg-iothub/iot_02_0203.html)

## 3. 先手工核对设备接入

可先用控制台设备详情提供的 MQTT 连接参数或华为官方 Python MQTT Demo 进行连通性核查：

1. 准备一个**独立虚拟环境**，下载官方 Demo/SDK，并记录仓库 URL、固定 tag 或 commit SHA、依赖锁和许可证文件。
2. 当前官方 Python SDK 中文 README 写明 Python 3.11.4、`paho-mqtt` 2.0.0、`schedule` 1.2.2、`apscheduler` 3.10.4；本仓库应用基线是 Python 3.12。先在独立环境验证兼容性，不把 SDK 及其依赖直接装进主应用环境。版本来源：[官方 Python SDK](https://github.com/huaweicloud/huaweicloud-iot-device-sdk-python)。
3. SDK 示例中 MQTTS 使用端口 8883、设备 ID/密钥及预置 CA；API 名称和配置结构以固定版本的 README/示例为准，避免混用不同版本的示例代码。
4. 启动后在控制台设备列表确认设备在线；保存脱敏后的启动日志和时间戳。
5. 连接失败时依次核对实例域名/区域、端口、设备 ID、密钥、系统时间、CA 证书和网络出口；到设备详情的消息跟踪或运行日志查平台侧拒绝原因。

**SDK 采用门槛：** 上游仓库 README 的许可证描述与仓库展示的 LICENSE 标识曾不一致，且 SDK 声明的 Python 版本和本项目基线不同。把 SDK 接入主工程前，先固定具体 SHA，核对该 SHA 内的 LICENSE/NOTICE、依赖及 Python 3.12 兼容性，并在依赖风险记录中留证。若未完成，SP-05 可以报告协议手工验证结果和阻塞项，不能默认 SDK 已获准采用。

## 4. 属性上报与消息上报分开验证

### 属性上报（依赖物模型）

华为 IoTDA 属性上报 Topic：

```text
$oc/devices/{device_id}/sys/properties/report
```

本指南的测试 payload：

```json
{
  "services": [
    {
      "service_id": "SpikeProbe",
      "properties": {
        "probe_counter": 1,
        "source_tag": "prototype_only"
      }
    }
  ]
}
```

用测试设备实际 `device_id` 替换 Topic 中的占位符。确认服务名、属性名、数据类型与第 1 节创建的模型一致；官方资料说明属性数据需要匹配物模型，符合模型的数据会更新平台设备数据快照。[属性上报说明](https://support.huaweicloud.com/intl/zh-cn/usermanual-iothub/iot_01_0326.html) · [MQTT Topic 定义](https://support.huaweicloud.com/intl/zh-cn/api-iothub/iot_06_v5_3004.html)

### 设备消息上报（自定义数据）

```text
$oc/devices/{device_id}/sys/messages/up
```

消息上报用于自定义格式，平台按消息通道转发/处理；它与按物模型校验并更新属性快照的属性上报不是同一接口。仅在 SP-05 需要验证事件载荷通道时再测消息上报，不要把 EventTransition 直接塞进属性字段。[数据上报类型说明](https://support.huaweicloud.com/usermanual-Iothub/iot_01_0045_2.html) · [MQTT 使用指导](https://support.huaweicloud.com/devg-iothub/iot_02_2200.html)

每次至少记录：发送时间、脱敏 payload、Topic、SDK/MQTT 返回或发布回调、控制台在线状态、消息跟踪记录、设备属性最新快照。不要把“publish 调用没有抛错”单独当作平台业务持久化回执。

## 5. 控制台核验与证据留存

1. 打开设备详情，确认在线状态和最新 `SpikeProbe` 属性快照。
2. 打开“监控运维 > 在线调试”或设备消息跟踪，选择测试设备，核对属性/消息上下行时间和结果。官方 Python Demo 指引也将在线调试与消息跟踪作为验证手段。[Python Demo](https://support.huaweicloud.com/devg-iothub/iot_02_2129.html)
3. 将脱敏截图、脱敏日志、产品模型字段、区域/实例规格、SDK SHA、依赖版本和操作步骤放入 `spikes/SP-05/evidence/`。
4. 另外记下哪些证据只代表设备已连接、哪些代表平台已看到属性/消息、哪些代表平台对外部业务系统的转发成功。后两者不能由设备在线状态推导。
5. 实验结束后停止客户端；确认无需保留时再按团队/账号规定清理测试设备和产品。删除前先保存必要证据。

## 6. 回执与本项目 Outbox 的边界

SP-06 的 Mock Cloud 应先定义传输成功/暂时失败/永久失败及单独的 business receipt 场景。真实 IoTDA 验证时按 SDK 固定版本确认其 publish callback 或协议确认能证明到哪一层；记录原始确认类型和关联 ID。设备在线、属性快照更新、消息跟踪可见、应用侧/业务侧持久接收是不同证据层级。只有经验证的传输回执才可映射到候选 `transport_receipt`；没有独立业务确认时，`business_receipt` 留空。

不要让 IoTDA Worker 修改本地 Event/Transition 事实；本地 SQLite 是事件事实源，Worker 只推进同步状态和回执记录。模拟数据、混合来源或未知来源禁止走真实联系人通知路径。

## 7. SP-05 完成判定

| 检查项 | 结果记录 |
|---|---|
| IoTDA 区域、实例、接入域名、端口已确认 |  |
| 测试产品/模型/设备创建并记录必要字段（密钥脱敏） |  |
| MQTTS CA 校验通过，设备在线 |  |
| 属性上报与消息上报分别验证，控制台可观察 |  |
| SDK 固定 SHA、许可证、依赖及 Python 兼容性已审查 |  |
| 回执层级及与 Outbox 的映射有证据 |  |
| 真实环境缺口、限制、清理状态写入 `REPORT.md` |  |

账号/实例/权限缺失时状态写 `BLOCKED`；协议样例通过但 SDK 或回执未核实写 `PARTIAL`。只有报告明确说明通过的真实范围，不把局部连通说成完整 IoTDA 验收。
