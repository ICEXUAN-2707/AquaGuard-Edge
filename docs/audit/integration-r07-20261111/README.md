# R07 集成收束与交叉验收（2026-11-11）

## 集成基线

- 分支：feat/integration-r07-20261110，基于 a3f1279。
- B：ce2ee6526f639f37409700058c18b03eacaf25b0；C：48de234beb5f1e2bad2936d4fdc3a129e4925941。
- 合并基线 179bc688b3c82bf3ecc3e4f8f85d7d984b46fc93；本目录 run.json 如实记录验收时该 HEAD 及 tracked_changes=true。验收覆盖的是该基线加本次提交的工作树修复，不冒称已在干净 HEAD 上测试。

## 修复与复核

1. 模型与归档统一写 UTF-8 字节，避免 Windows CRLF 改变模型文件 SHA256；R07 证据目录禁止 Git 文本换行转换。重新生成报告，算法结论未改变。
2. 原报告接口增加 v2 R07 只读适配，重算聚合、指标及失败案例；校验模型字节摘要、训练来源与分区。保留 v1 与 ExperimentResult 1.1。
3. 新实验页提供四方法、分区、明确分母、失败案例、模型摘要与完整报告导出；关联仅为 reference。
4. 新版事件页接入恢复后关闭，保留不确定请求的原幂等键及版本；“已恢复”筛选使用物理 CLEARED 状态。
5. 端到端交叉自检发现并修复本地导入 CLI 模块路径问题。第一次失败保留于本地 audit/integrated-mqtt-r07；归档的是修复后独立重跑。

## 验收证据

- B 测试集合：237 passed；C 测试集合：303 passed。集合包含重叠契约/冒烟测试，不作不重复总数。
- 最终定向回归：31 passed（报告/API、模型、完整归档哈希）。
- 前端状态/展示测试：6 passed；生产构建通过。
- integrated-mqtt-r07-v2：13 项浏览器检查通过，无页面 JS 错误；真实本地 Mosquitto + 合成输入，ACK 冲突、确认、恢复关闭、复发、R07 分区与导出、390px 布局、过期清值及断连清值。
- integrated-recovery：3 项浏览器检查通过；实际停止发布后过期，边缘进程重启并使用新 boot，页面恢复；恢复前后水事件身份保持一致。
- 两个运行的 cleanup.json 均记录自有进程退出。未归档 token、数据库或服务日志。
- 目视复核 experiment.png：四方法、17/10/7 分母、案例和摘要可见。移动页截图一并保存。

## 复现

先按现有项目环境安装依赖并执行 npm.cmd --prefix web run build。设置 AQUAGUARD_PLAYWRIGHT 为已安装的 Playwright 模块路径，AQUAGUARD_CHROMIUM 为本地 Chromium 可执行文件路径。使用空的输出目录与空闲端口：

```powershell
python spikes/SP-02/src/verify_workbench.py --directory audit/recheck-r07 --broker 'C:\Program Files\mosquitto\mosquitto.exe' --mqtt-port 18889 --http-port 8027 --lifecycle --evaluation-report spikes/SP-04/evidence/r07/report.json
python spikes/SP-02/src/verify_workbench.py --directory audit/recheck-recovery --broker 'C:\Program Files\mosquitto\mosquitto.exe' --mqtt-port 18890 --http-port 8028 --recovery
node --test web/tests/c-state.test.js web/tests/c-display.test.js
```

## 阶段边界与剩余交付

- G1：当前集成版受控本地闭环已有联合浏览器证据；仍需人工正式验收及交付环境版本固化。
- G2 / D1、D3：真实硬件实验、真实 IoTDA 接收与云端同步证据待补。本轮 cloud_connected=false，pending_count 不代表云端接收。
- G3 / D4：R07 共34 trial，评估17（可判定10，应拒判7）。C2/C3 在可判定评估集均 TP4 FP0 TN6 FN0；正确拒判分别6/7、5/7。C3 不证明优于 C2，维持影子用途。
- D2：三页面主体与本轮扩展已开发和自动验收，等待人工页面评审。
- G4 / D4：统一技术报告、演示视频和答辩材料仍需收束。本轮不合并 main、不替代真实装置或云端正式验收。
