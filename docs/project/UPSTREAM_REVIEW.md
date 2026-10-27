# I-001 上游核查与运行栈决策

核查日期：2026-10-26。此文件记录开发阶段的新证据；D0 报告保留当时的审计结论。

## Smart Hydro Alert 候选源

- VERIFIED：公开仓库 [momo840505/smart-hydro-alert](https://github.com/momo840505/smart-hydro-alert) 的 README 描述 ESP32、YF-S201、FC-37、LD2410C、MQTT、FastAPI、React，和项目资料所述技术组合高度吻合。该仓库自称从 [hnguyen-debug/IoT-group4](https://github.com/hnguyen-debug/IoT-group4) 分叉。
- VERIFIED：2026-10-26 浅克隆候选仓库并固定所检提交 `59c94ccc0c4066564bf74eb2147b67ba8dfd4157`；`git ls-files` 未列出 LICENSE、NOTICE 或 COPYING。候选源的 `app/`、`frontend-react/`、`simulator/`、`tests/` 等目录存在。
- UNVERIFIED：原资料只有项目名称，未给 URL，因此不能证明该仓库就是资料所指的唯一上游；也未取得作者的额外授权。没有许可文件不能推断为允许复制。
- 决策：本仓库采用自建本地运行基线，不导入候选仓库代码或资源。后续若需复用，先核实确切来源、完整历史、各贡献者授权和依赖许可。候选仓库代码只作为许可与技术现状的只读核查材料。

## 本地运行栈

|组件|选型与证据|当前状态|
|---|---|
|Python|本机 3.12.10；`audit/evidence/environment.json`|VERIFIED 可运行|
|API|FastAPI 0.162.0、Uvicorn 0.53.0、Pydantic 2.14.1；`requirements-app.lock.txt`|VERIFIED 本地安装、健康端点启动|
|MQTT 客户端|paho-mqtt 2.1.0；`requirements-app.lock.txt`|VERIFIED 安装；broker 接入 UNVERIFIED，I-003 实施|
|持久化|Python 内置 sqlite3，当前审计环境 SQLite 3.49.1|业务迁移与事务 UNVERIFIED，I-008 实施|
|前端基线|React 19.3.1、Vite 8.3.5、@vitejs/plugin-react 6.1.2；`web/package.json`、`web/package-lock.json`，官方 npm [React](https://www.npmjs.com/package/react)、[Vite](https://www.npmjs.com/package/vite)|VERIFIED `npm ci` 与 `npm run build`；当前只有连接检查页|

Python 直接依赖固定于 `requirements-app.in`，解析后的传递依赖固定于 `requirements-app.lock.txt`；前端传递依赖固定于 `web/package-lock.json`。审计环境与业务环境分开，避免将只供审计使用的 `jsonschema` 误认为业务依赖。I-001 的当前运行服务只提供 `/health`，页面只检查该端点，不代表 M1–M8 功能已实现。

已安装包元数据核查：FastAPI 0.162.0、Pydantic 2.14.1、pytest 9.1.1 为 MIT；Uvicorn 0.53.0、Starlette 1.10.0 为 BSD-3-Clause；paho-mqtt 2.1.0 标注 `EPL-2.0 OR BSD-3-Clause`。`web/node_modules` 中 React 19.3.1 与 Vite 8.3.5 的 `package.json` 均标注 MIT。命令为 `pip show fastapi uvicorn paho-mqtt pytest pydantic starlette` 及读取包内 `package.json`。这是顶层及关键传递包的元数据核查；发布前仍需对完整锁文件逐包汇总许可证和 NOTICE。

## I-001 验收记录

在仓库根目录执行：

```powershell
python -m venv .venv-app
.\.venv-app\Scripts\python.exe -m pip install -r requirements-app.lock.txt
.\.venv-app\Scripts\python.exe -m pip check
.\.venv-app\Scripts\python.exe -m pytest tests/smoke/test_startup.py -q -p no:cacheprovider
```

2026-10-26 本机结果：`pip check` 无损坏依赖；3 项进程级启动测试通过，覆盖缺配置、端口占用、健康请求与停止。第一次 pytest 因原有 `.pytest_cache` 写权限提示 1 个缓存警告，测试仍 3 passed；复验时关闭缓存插件即可避免无关提示。

前端复验命令：

```powershell
cd web
npm ci
npm run build
```

2026-10-26 本机结果：19 个 npm 包安装，审计显示 0 个漏洞；Vite 8.3.5 构建通过。该检查不构成浏览器端到端或业务页面验收。

启动与停止：

```powershell
$env:AQUAGUARD_DEVICE_ID = 'home01'
$env:AQUAGUARD_HOST = '127.0.0.1'
$env:AQUAGUARD_PORT = '8000'
.\.venv-app\Scripts\python.exe -m edge
# 在同一终端按 Ctrl+C 停止
```

健康检查：`http://127.0.0.1:8000/health`。`.env.example` 是配置样本；当前入口读取环境变量，不自动加载 `.env`。设备 ID 缺失或端口被占用时启动明确报错并以退出码 2 结束。

在另一个 PowerShell 终端执行 `cd web; npm run dev`，打开终端显示的本地网址即可查看连接检查页。若 API 端口不是 8000，前端启动前设置相同的 `AQUAGUARD_PORT`。

回滚：移除新增 `edge/`、`web/`、`tests/smoke/`、业务依赖文件和配置样本即可恢复 D0；`reference/` 未改变。
