# B部分复现手册｜Windows从零操作

日期：2026-11-03。范围：SP-03时间对齐、SP-03-features十二特征、SP-04规则；离线synthetic/prototype_only。无需传感器、云账号、MQTT Broker、Node.js或前端服务。不代表完整系统部署。

## 1. 软件与版本
|软件/依赖|本机已核实版本|用途|
|---|---|---|
|Windows + PowerShell|本次验证为Windows PowerShell命令|执行步骤；其他系统未验收|
|Python|3.12.10，建议64位|运行算法与创建环境|
|Git|支持clone/switch的Git for Windows即可，未锁定具体版本|下载代码；也可下载分支ZIP|
|pytest|9.1.1|测试|
|Pydantic|2.14.1|候选DTO校验|
|FastAPI|0.162.0|完整回归中的API/启动依赖|
|全部Python依赖|仓库requirements-app.lock.txt逐项锁定|不要只安装表中三项|

版本来自当前pyvenv.cfg、pip元数据和锁文件，并非最新版本推荐。Python请通过官方发行渠道安装，勾选Python Launcher；安装后重开PowerShell。私有仓库访问需已获仓库权限；不要把令牌写进代码或命令示例。

## 2. 获取正确分支
选择自己的项目目录。下面以C:\work为示例，实际路径可自行替换：
```powershell
New-Item -ItemType Directory -Force C:\work | Out-Null
Set-Location C:\work
git clone --branch spike/b-m3-m4-m5-validation https://github.com/ICEXUAN-2707/AquaGuard-Edge.git
Set-Location .\AquaGuard-Edge
git branch --show-current
```
预期分支spike/b-m3-m4-m5-validation。已有代码且有未提交改动时，不要执行reset/clean；先确认工作区再拉取。ZIP下载必须选对应分支，解压后进入包含requirements-app.lock.txt、edge、spikes的根目录。不要在spikes子目录运行后续命令。

## 3. 创建独立环境
```powershell
py -0p
py -3.12 --version
```
建议输出Python 3.12.10；若有多个3.12，使用目标python.exe绝对路径代替py -3.12。随后：
```powershell
py -3.12 -m venv .venv-app
.\.venv-app\Scripts\python.exe --version
.\.venv-app\Scripts\python.exe -m pip install -r requirements-app.lock.txt
.\.venv-app\Scripts\python.exe -m pip check
```
预期pip check为No broken requirements found。本手册直接调用环境内解释器，不需要Activate.ps1，因此不用修改PowerShell执行策略。不要拷贝别人的.venv-app目录；它不可移植。若已有正常环境，先pip check，不必重建。
安装依赖需要联网；若锁定包不可从当前软件源获得，保存报错、核对代理/镜像，不要私自去掉版本号后宣称同环境复现。

## 4. 可选：先看M3窗口
```powershell
.\.venv-app\Scripts\python.exe spikes/SP-03/src/replay.py spikes/SP-03/data/synthetic.jsonl --output spikes/SP-03/evidence/replay.jsonl
.\.venv-app\Scripts\python.exe spikes/SP-03/src/alignment.py spikes/SP-03/data/r06_three_source.json --output spikes/SP-03/evidence/r06_windows.json
```
预期回放4条观测，发布2个窗口。打开r06_windows.json，检查三个源的state、coverage_ratio、引用和origin；人工预期在data/r06_three_source.json。这个回放不会真的等待30秒。

## 5. 按顺序运行特征与规则
```powershell
.\.venv-app\Scripts\python.exe spikes/SP-03-features/demo.py
.\.venv-app\Scripts\python.exe spikes/SP-04/demo.py
```
第一条应显示2份候选FeatureWindow保存且恢复一致。输出spikes/SP-03-features/evidence/r07_feature_windows.json，每窗有十二特征、missing_mask、origin和真实快照引用。
第二条预期打印['ATTENDED_FLOW', 'UNKNOWN']，输出spikes/SP-04/evidence/r03_assessments.json。第二窗UNKNOWN是因为flow区间没有恰好终止于窗尾，遵循当前保守口径，不是脚本失败。
必须先运行特征demo：已提交证据保留原机器绝对路径，重新生成会建立当前机器可解析引用。不要手工编辑SHA256命名的checkpoint内容或把state_checkpoint_ref改成随意路径。

## 6. 运行对照实验
```powershell
.\.venv-app\Scripts\python.exe spikes/SP-04/evaluate.py
```
结果在spikes/SP-04/evidence/r05/comparison.json，包括8个合成trial、每种方案预测和二元候选指标。
当前预期：B1即时规则误触发3、拒判1；B2 10秒误触发1、拒判3。两例减少的误触发是变为拒判，不是正确识别正常。人在场但未检出的反例仍会误触发。默认10秒来自用户决定，其他阈值是对照，不覆盖默认配置。

## 7. 自动化验证
先分模块，再整体；时间数字随机器变化：
```powershell
.\.venv-app\Scripts\python.exe -m pytest spikes/SP-03/tests -q -p no:cacheprovider
.\.venv-app\Scripts\python.exe -m pytest spikes/SP-03-features/tests -q -p no:cacheprovider
.\.venv-app\Scripts\python.exe -m pytest spikes/SP-04/tests -q -p no:cacheprovider
.\.venv-app\Scripts\python.exe -m pytest spikes/SP-04/tests spikes/SP-03-features/tests spikes/SP-03/tests tests/contracts tests/smoke -q -p no:cacheprovider
```
当前已记录完整范围171 passed，退出码0；含既有契约与启动检查，不是171个独立真实场景。代码后续版本若新增测试，数量可能变化，应以对应提交说明为准。不要用pytest全仓命令替代本范围，其他线依赖与验收不同。
若需保存自己的记录：
```powershell
.\.venv-app\Scripts\python.exe -m pytest spikes/SP-04/tests spikes/SP-03-features/tests spikes/SP-03/tests tests/contracts tests/smoke -q -p no:cacheprovider *> b-reproduce-tests.txt
$LASTEXITCODE
Get-Content b-reproduce-tests.txt
```
本地生成日志先自留，不要无差别git add所有生成结果。

## 8. 看哪些输出算复现成功
|检查|预期|
|---|---|
|环境|Python版本明确，pip check通过|
|窗口|三源双窗输出与手写预期一致|
|特征|十二字段存在；快照文件实际可读取|
|情境|两个演示结果为ATTENDED_FLOW、UNKNOWN，rules分数null|
|阈值|测试覆盖9.9拒判、10与10.1秒命中|
|恢复|测试覆盖新进程、继续输入、重复评估与故障拒绝|
|回归|对应提交的全部指定测试通过且退出码0|

## 9. 常见问题
|现象|处理|
|---|---|
|py命令不存在|重新打开终端或使用安装好的Python绝对路径|
|缺pydantic/pytest|确认使用.venv-app解释器，按锁文件安装；.venv是另一套审计环境|
|找不到requirements或spikes|回到仓库根目录，用Get-Location核对|
|找不到spikes/M4或M5|是旧命名；使用SP-03-features和SP-04|
|检查点不存在或outside trusted root|先重跑特征demo，再规则demo；不要手改快照|
|digest mismatch|工件被改写/损坏；重新生成演示，不去掉校验|
|规则UNKNOWN|先看reason_codes、各源终态、覆盖和时效，不把它强改成正常|
|中文显示异常|PowerShell可用Get-Content -Encoding UTF8查看，文件用UTF-8编辑器打开|
|pip下载失败|核对网络、镜像与包版本；记录实际错误，不把未安装当验证成功|
|测试失败|保留首个错误、命令、Python/pip版本与git提交；不要先改期望值|

## 10. 复现留痕清单与限制
记录操作者/日期、git rev-parse HEAD、Python版本、pip check、执行命令/退出码、预期与实际、异常和下一步。快照为完整历史回算；无实物/MQTT/云/真实事故概率/独立验收结论。本手册版本依据现有环境核实；新机器新建环境仍需逐项执行，不代表已经验证全部Windows配置。

阅读顺序：[文档总入口](B部分_文档总入口.md)→[代码地图](B部分_代码地图.md)→本手册→模块最新收尾报告→逐轮细节。

## 11. 本次操作验证与临时目录排障
2026-11-03已验证Python3.12.10、锁定包版本、pip check及两条演示。首次默认临时目录因C盘可用空间为0失败；尝试旧.pytest_cache又遇WinError5。改用D盘工作区全新独立目录后完整171 passed in 14.28s，日志见../../spikes/SP-04/evidence/reproduction_20261103.txt。未在空白机器重新联网安装，不能把已有环境验证说成全新安装实测。

遇相同问题先检查磁盘，不删除别人的临时文件；在有空间且可写的当前工作区创建唯一目录：
```powershell
Get-PSDrive C,D | Select-Object Name,Free
$reproTemp=Join-Path (Get-Location) ('b-repro-temp-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $reproTemp | Out-Null
.\.venv-app\Scripts\python.exe -m pytest spikes/SP-04/tests spikes/SP-03-features/tests spikes/SP-03/tests tests/contracts tests/smoke -q -p no:cacheprovider --basetemp (Join-Path $reproTemp 'pytest')
```
必须用新目录，pytest会清理指定basetemp，不要指向项目根目录、已有资料或共享目录。b-repro-temp-*是本地临时工件，Git忽略，不提交。
