# 调度与进程监督独立批次

基线 main=5f5bc94。提取 PR #12=abe27a7 的原子收据和 Windows Job Object 能力，解除 runtime_endurance.py、在线诊断和 checkpoint 的依赖。本批不改 B 冻结源，不包含也不执行原一小时实验脚本。

## 代码文件

|文件|行为与限制|
|---|---|
|scripts/supervise_endurance.py|必须显式提供 Python 脚本；默认子进程超时 30 秒，超过 60 秒须 --allow-long-run。支持 --args-file JSON 字符串数组或 -- 后逐项参数。不拼接 shell 命令。输出目录独占预留，收据原子替换并 fsync；退出码为 0 仅表示子进程执行完成，acceptance_passed 始终 false|
|同上：进程归属与清理|Windows Job Object 绑定 supervisor 和后代，父进程异常退出时由 OS 清理。超时尝试 taskkill /PID /T /F；taskkill 无法启动时回退到持有句柄的子进程 kill，并保留 cleanup_error_type 和 child_exit_confirmed。其他平台没有 Windows 树清理保证|
|同上：资源记录|通过 Windows Popen 保留的句柄读取直属子进程 RSS、峰值 RSS、CPU、优先级、创建 FILETIME，避免 PID 被重用。每个心跳写入 supervisor.samples.jsonl 并 fsync。不可用明确记录 available=false，不当作零。不包含孙进程总资源，不提供 OS 睡眠诊断|
|scripts/start_endurance_task.ps1|默认仅输出计划，不创建目录、不注册、不启动任务。-Register 仅注册，启动另需 -Start；超过 60 秒另需 -AllowLongRun。使用 pythonw.exe、当前交互用户、普通优先级、唯一任务名；注册失败保留收据。不自动删除任务|
|tests/delivery/test_endurance_supervisor.py|验证失败不误报成功、真实短子进程参数边界、长时默认拒绝、taskkill 启动失败、PowerShell 默认预览无副作用、Windows 原生句柄指标与 Job Object|

脚本参数若需输出目录，应使用预留目录下的子目录，例如 `<output>/run`，不可要求创建 supervisor 已预留的顶层目录。

```powershell
# 前台短子进程监督；示例脚本需由调用者明确选择。
python scripts/supervise_endurance.py --directory <新目录> --script <脚本.py> --seconds 30 -- <脚本参数>
# 默认仅预览；暂停实验期间不添加 -Register、-Start 或 -AllowLongRun。
powershell -File scripts/start_endurance_task.ps1 -Directory <新目录> -Pythonw <pythonw.exe> -Script <脚本.py>
```

本机短测 8/8 通过，包含真实 Windows Job/句柄检查和数秒内空白子进程；证据 docs/audit/supervisor-tools-20261114/tests.xml。没有注册/启动计划任务、MQTT broker、长时实验或真实云连接。该批与只读工具 PR #14 独立，均可单独审查；没有合并 main。
