# B 复验后的软件闭环（2026-11-12）

## 结论

固定 e063734 的本地 MQTT 仿真、B 报告导入、API 和工作台生命周期自动验收 PASS。B 合成软件复验暂停可在已测范围解除；原 11 月 11 日文档中的“B 待复验”为历史状态，当前以本记录及 B_INDEPENDENT_REVIEW_20261112.md 为准。未新增人员签字、真实硬件、真实云或 G3 整体验收。

## 实际验证

锁文件安装前端依赖成功，npm run build 通过。使用既有 Playwright 与 Chromium 1248，在新目录 audit/b-closure-20261112 执行：

```text
python spikes/SP-02/src/verify_workbench.py --directory audit/b-closure-20261112 --broker "C:/Program Files/mosquitto/mosquitto.exe" --mqtt-port 18889 --http-port 8034 --lifecycle --evaluation-report audit/b-independent-20261112/r07/report.json
```

结果：75.125 秒，PASS。报告 rules-r07 作为 reference 导入，不将离线实验视为在线 trial 的实时结果。13 项浏览器检查通过，包含凭据错误、连续更新、ACK 冲突后重查、确认持久化、事件导出与筛选、恢复后关闭及复发、运行 trial 查询、缺失 trial 清空、R07 分母/分区/案例筛选/报告导出、390px 布局、过期值移除与断连清空。

产生两个 WATER_CONTACT 事件，Outbox pending_count=6；cloud_connected=false，来源 simulation。cleanup.json 确认四个自有进程均已退出；部分 terminate 返回码为 1，不据此宣称优雅关闭。此场景没有重跑重启恢复专项，也不是人工视觉评审。

公开归档只选 result.json、cleanup.json、浏览器 result.json；数据库、日志与检查点保留本地，不提交运行凭据。新增 .gitattributes 规则保留独立 R07 工件字节，防止换行转换破坏摘要。

## 后续顺序

1. 人工评审三页工作台及同版本演示；根据反馈修复，再整理集成 PR。
2. B Owner 确认 B-SIM 标签/分区后独立训练评估；C3 继续影子运行，不宣称超越规则。
3. A 完成实体制作与逐源标定；A/C 对齐硬件来源、单位、时间与 boot 后接入。
4. C 核实真实 IoTDA 条件后验证关联回执与断网补传；继续技术报告与视频准备。
