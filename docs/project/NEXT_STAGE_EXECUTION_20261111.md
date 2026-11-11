# 下一阶段执行计划与统一演示入口

2026-11-11；B复验期间的非B增量。当前PR #10为Draft，人工验收和真实硬件/云端验收仍未完成。

## 推进顺序与退出条件

| 批次 | 任务 | 责任建议 | 依赖 | 退出条件 |
|---|---|---|---|---|
| N1（本轮） | 统一本地预检/启动与操作指引 | 集成 | 现有edge与前端构建 | 检查只读、目录不覆盖、端口冲突可见、凭据不归档 |
| N2 | 三页人工评审与定点修复 | 用户评审+前端 | 当前候选版本 | 记录页面问题、逐项处理，复测受影响交互；B数值不签收 |
| N3 | 演示排练与证据打包复核 | C+集成 | N1/N2、现有MQTT lifecycle/recovery | 同版本可复现，进程退出、证据索引完整、无凭据；可用性不等于云验收 |
| N4 | 技术报告非B章节与初版视频 | 集成统稿、A/C供证据 | 稳定页面和已选演示路径 | 架构/状态/操作/限制与录像一致；B效果留待复验，视频未录制不算完成 |
| N5（并行） | 真实硬件/IoTDA条件与联调 | A/C及账号持有人 | 真实设备/账号/接入参数 | 真实来源、实际云接收与本地事件关联；云条件不具备就保持未验收 |
| B恢复后 | B复验结论接回报告与页面 | B+交叉复核 | 复验说明及版本化工件 | 明确哪些结论变化、更新证据后再签收，不覆盖历史基线 |

不增加复杂ML、通用连接器或目录迁移；继续复用edge、现有Journal和三页面。当前先完成N1，再依据人工反馈推进N2/N3，不等待B结果即可进行。

## 新入口

先按现有安装手册安装 requirements-app.lock.txt 及前端依赖并构建。仓库根目录、已有虚拟环境中执行；当前工作树可将python替换为父目录.venv-app的解释器。

```powershell
python scripts/demo.py --run-dir audit/manual-demo-01 --port 8030
python scripts/demo.py --run-dir audit/manual-demo-01 --port 8030 --start
```

第一条只检查，不创建目录或启动服务；PASS后第二条启动。若路径存在，换一个新目录名，不删除旧证据。窗口保持前台，Ctrl+C退出；打开 http://127.0.0.1:8030/c.html 并输入终端显示的临时token。token不写入launch.json，不要将终端凭据录入视频。实验ID为demo-trial。

MQTT模式复用已运行的外部Broker/订阅器，并指向其现有Journal：

```powershell
python scripts/demo.py --mode mqtt --journal audit/mqtt-input/journal.sqlite --run-dir audit/manual-mqtt-01 --port 8030
python scripts/demo.py --mode mqtt --journal audit/mqtt-input/journal.sqlite --run-dir audit/manual-mqtt-01 --port 8030 --start
```

本入口不生成MQTT输入、不启动或停止外部Broker/订阅器，实验ID为mqtt-trial。当前仅demo01/simulation，不是硬件接入适配器，不运行B报告导入。真实云验收不由此入口完成。

launch.json包含提交、已跟踪修改标志、模式/来源/端口、B待验与云未验状态。预检是必要条件，不证明运行时健康：依赖版本兼容、Journal内容、SQLite可写、浏览器和数据推进仍需启动后验证；启动失败查看前台错误，不据预检PASS签收。保留完整仓库，前端必须先构建。

## 本轮验证和边界

实际预检PASS；3项自动测试通过（占用端口、目录保护/MQTT缺失及非法端口、启动配置与凭据不落盘）。测试对启动调用使用替身，未声称本轮重新执行完整浏览器/云端验收；现有联合验收保留历史版本信息。新增入口不修改B算法、数据或业务处理路径。

进度：D1仍待真实装置/视频；D2等待人工评审；D3新增本地交付操作入口但真实云未验；D4规划/架构/脚本已有文档，最终报告与录像待完成，B结论暂停。
