# M4 技术验证交付入口

截至2026-10-29：离线模拟原型开发收尾；正式M4验收仍PARTIAL。
已实现十二特征统一计算、内容寻址回放快照、恢复重算、完整候选FeatureWindow与演示。独立Reviewer、正式契约和实物验证尚未通过。

## 一次运行
在仓库根目录：
```powershell
.\.venv-app\Scripts\python.exe spikes/SP-03-features/demo.py
.\.venv-app\Scripts\python.exe -m pytest spikes/SP-03-features/tests spikes/SP-03/tests tests/contracts tests/smoke -q -p no:cacheprovider
```
演示结果：evidence/r07_feature_windows.json；实际检查点：evidence/checkpoints/。

## 开发报告
- [计划与M3技术总结](PLAN.md)
- [R01 字典与手算](REPORT_R01.md)
- [R02 流量与多路核对](REPORT_R02.md)
- [R03 状态特征](REPORT_R03.md)
- [R04 连续时长参考](REPORT_R04.md)
- [R05 转换计数](REPORT_R05.md)
- [R06 统一入口](REPORT_R06.md)
- [R07 收尾报告与限制](REPORT_R07.md)
- [内部输入设计](INPUT_DESIGN.md)

技术解释：checkpoint为完整历史回放快照，尚非有界实时检查点。模拟数据、实验配置、未确认语义与真实硬件结论严格区分。旧报告记录当时状态，以R07了解最新进度。
