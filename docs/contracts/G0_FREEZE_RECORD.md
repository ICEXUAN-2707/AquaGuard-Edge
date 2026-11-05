# G0 软件契约冻结记录

日期：2026-11-05。审查基线：origin/main@b304174；本地工作树保留未提交内容。

## 授权与放行范围

项目负责人本轮授权“根据目前已有的代码文件完成 G0 以及相关 contract 的冻结”。据此冻结下述软件集成基线，供 G1 开发使用。授权不等同于 A/B/C 三方签字；不代签、不声明独立评审完成。原 C0 三方会签门槛仍保留，G0 整体状态为软件基线已锁定、联合签署及外部资源登记待完成。

权威顺序：最终交付基线 V1.0 > 本记录的明确增量决议 > Contracts V1.2 修订候选 > V1.1 无冲突条款。历史文件名保留，避免断开引用；其中“候选”描述原评审状态，本记录仅批准软件集成使用，不抹去历史。

## D1–D5 软件决议

|包|冻结内容|证据/消费者|
|---|---|---|
|D1|三源判别 value、未知不可补 false/0；原始 quality 为 valid/invalid/unknown；状态心跳不伪装观测；seq 身份为 device/sensor/boot/seq；补发不改测量时间|SensorObservation Schema、edge/contracts/models.py；A→B/C|
|D2|窗口 (start,end]；三源摘要、缺失 mask、十二特征和引用字段遵循 V1.2；flow 时间为统计区间终点；终态仅端点等于窗尾时已知；water/presence TTL age>=TTL 过期（flow 按统计区间处理）；同接收时间批次先全部输入再 advance|SP-03 alignment.py/stream.py；SP-03-features engine.py/checkpoint.py|
|D3|每设备单支路/单水浸点；活动事件按 device/event_type 唯一；快慢路径汇入同一事件；来源由后端引用推导；ACK 不清除湿态；无新证据不可判干；不实现真实联系人通知|V1.2 §4；C-business water.py/store.py/policy.py|
|D4|七 API 模型、错误码、持久幂等 ACK 与连续版本沿用 V1.2；单目的地 huawei_iotda；event/transition/outbox 同事务；传输与业务回执分离|edge/contracts/api_models.py；C-business api.py/outbox.py|
|D5|文档版本 V1.2，业务 DTO schema_version=1.1，ApiError 无版本字段；1.0 在线入口明确拒绝；历史原件只读保留，不提供隐式升级或兼容期；统一验证包 edge/contracts|Schema、DTO/API 正反例与版本拒绝测试|

### D2 的运行边界

上述 flow/TTL/boot 口径批准用于现有模拟软件基线，未证明适合真实硬件。跨 boot 保守清空旧缓存；未知新 boot 的可信性须接入层证明；拒绝退休 boot，不能把任意未见 boot 视为真实最新启动。真实接入前由 A 提供固件/时间映射证据，B 复核。

现有 published_at=end+lateness 是虚拟逻辑截止，不是实测发送时间。G1 必须另存实际处理/发布时间用于延迟统计，不得拿虚拟值计算实测响应。30 秒窗、5 秒步长、2 秒迟到、10 秒 TTL 和 0.1 L/min 阈值仅为显式模拟配置；实测参数单独版本化，不能冒充硬件标定结果。

M4 需要完整引用观测及 alignment_config，摘要不够；检查点须保留历史、窗口身份、feature_version 和内容校验。状态容量、长期运行和调度为 G1 实现/验收项，不由冻结文档宣称完成。

## 本轮验证

从仓库根目录执行，2026-11-05：

- `.venv/Scripts/python.exe -m pytest reference/reference_02/tests -q -p no:cacheprovider`：45 passed。
- `.venv-app/Scripts/python.exe -m pytest tests/contracts tests/smoke -q -p no:cacheprovider`：32 passed。
- SP-03 独立测试：42 passed；SP-03-features：43 passed；SP-04：54 passed。
- 原型测试按目录独立进程运行；一次合并使用 importlib 导入模式导致收集失败，未作为有效结果。随后系统临时盘空间不足，改用项目盘唯一 basetemp 后完成上述回归。C 原型 82 passed，结果见 [验证记录](evidence/G0_VALIDATION.json)。

通过结构和原型回归不表示 C3–C5、G1、实物或云验收通过。

## 尚待完成的 G0 项

|事项|负责角色|可观察完成条件|
|---|---|---|
|联合会签|项目负责人组织 A/B/C|三方对 D1–D5 逐项署名、日期、保留意见；引用本次 manifest 的 SHA256|
|Reviewer 与正式 Owner|项目负责人|登记实际人员，不能以角色或 Codex 冒充独立 Reviewer|
|真实资源与赛题核验|C，A/B提供依赖|登记账号/配额/预算负责人、硬件型号资料、官方赛题原件核验及 CodeArts 任务；不要求此时设备/云已成功|

G1 可按本软件基线准备实现；正式联合放行仍须关闭以上项。不得将本文件用作三方已会签或云资源已批准开通的证明。

## 变更和回滚

冻结输入及 SHA256 见 [哈希清单](evidence/G0_MANIFEST.json)。输入包括规范、九 Schema、联合样例、统一 DTO/API 模型及契约测试。修改公共字段/时间或缺失语义须记录差异、影响消费者、迁移 fixture，并重跑对应层测试后由负责人批准；不得只改某一消费者。回滚本次文档增量即可恢复候选流程；未修改 wire schema、生产服务、数据库或云资源。硬件新语义若与本基线不一致，必须通过显式适配或升级决议解决。
