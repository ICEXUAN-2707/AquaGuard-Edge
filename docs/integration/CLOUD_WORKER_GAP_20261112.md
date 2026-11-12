# 云worker装配审查（静态，非真实云验收）

main集成后存在IoTDA适配与进程隔离原型，但spikes/C-business/run.py的worker入口仍明确为Mock-only，并仅装配MockAdapter；不能据适配器文件存在宣称真实云闭环完成。

spikes/C-business/delivery.py::step在claim完成后才调用adapter，维持数据库事务与网络IO隔离，但仍有simulation-only校验，且finish使用调用开始传入的now。后续真实接入必须独立审查发送完成时间、持久策略/来源授权、租约、超时、旧库兼容与异常退出，而不是只替换MockAdapter。

建议下一批：

1. 明确现有进程通道与Paho资源生命周期的放行证据，选择正式装配路径；不以实验probe替代正式连接器。
2. 实现独立显式云worker配置入口，默认离线；区分simulation_test与test_hardware绑定，保持凭据去敏与稳定消息身份。
3. 在本机broker与故障桩验证发送完成时间、断连重试、租约过期、重复/迟到结果、旧策略数据和自有进程退出；PUBACK仅为传输确认。
4. 账号/设备与权限齐备后，用隔离测试设备验证真实云接收及本地消息ID关联，再做断WAN补传。另行验收云上只读应用，不把IoTDA控制台当作已部署业务应用。

本批只完成装配差距分析，未创建资源、读取密钥、改worker或接入真实云。该路径可在实物制作期间推进simulation_test准备，硬件来源放行另批完成。
