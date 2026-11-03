# B线模拟算法闭环｜分批交付说明

日期：2026-10-30。范围：M3/SP-03、M4、M5独立技术验证。交付分支：spike/b-m3-m4-m5-validation。

## 四个依赖顺序提交
1. M3：统一观测回放、固定截止滑窗、分源TTL、有效区间并集、身份/boot隔离、迟到审计、原子容量恢复和有界窗口追赶。包含人工黄金输入、六轮报告、审查与修复记录。
2. M4：十二特征字典、时间加权流量、状态比例/转换、历史连续时长、配置/引用核验、统一入口、内容寻址快照与候选FeatureWindow。包含七轮报告、恢复与故障测试。
3. M5：10秒时序规则、质量/时效门控、UNKNOWN、原因码和稳定身份、实际管线边界测试、合成trial基线比较、新进程恢复及故障拒绝。包含六轮报告、演示、指标和推送前回归。
4. 文档：导航、SP-03/SP-04 PARTIAL状态与本交付说明。修正docs导航相对链接。

这些是对已完成多轮开发成果的按模块归档提交，不伪造每轮历史提交时间。A线与SP-02本地改动不属于本次提交。

## 验证
推送前重跑171项通过，包含既有契约/启动检查；日志spikes/SP-04/evidence/prepush_tests.txt。源码、手写预期、实际输出和历史修复报告共同保留。Python缓存与虚拟环境由现有.gitignore排除；未修改正式公共契约。

## 新环境重跑
使用项目requirements-app.lock.txt提供的依赖环境。仓库根目录：
```powershell
.\.venv-app\Scripts\python.exe spikes/SP-03-features/demo.py
.\.venv-app\Scripts\python.exe spikes/SP-04/demo.py
.\.venv-app\Scripts\python.exe spikes/SP-04/evaluate.py
.\.venv-app\Scripts\python.exe -m pytest spikes/SP-04/tests spikes/SP-03-features/tests spikes/SP-03/tests tests/contracts tests/smoke -q -p no:cacheprovider
```
已提交演示证据中的state_checkpoint_ref包含原机器绝对路径，这是历史输出；迁移目录后先重跑M4/demo.py，再运行M5/demo.py以重新生成路径。检查点JSON摘要依赖原始字节，勿手工改写。早期stage_review_reproduce.py记录修复前缺陷，不是当前可成功重跑的验收脚本；以当前tests和最终日志为准。

## 交付边界
仅离线模拟闭环已跑通，全部synthetic/prototype_only。完整历史回算不是有界实时检查点；无硬件、真实MQTT/IoTDA、M6全链路、真实家庭性能、ML或独立Reviewer验收结论。10秒由用户批准，模拟基线减少误触发的部分变为拒判，不能写成准确识别正常。静止人员未检出仍是不可区分反例。

## 审阅入口
- [M3](../../spikes/SP-03/开发报告索引.md)
- [M4](../../spikes/SP-03-features/阅读入口.md)
- [M5](../../spikes/SP-04/阅读入口.md)

优先审查M3待裁决语义、M4历史/配置绑定及M5拒判与时序身份；正式放行仍走会签和独立复核。
