# 前端优化第二阶段：总览与趋势解释

承接第一阶段提交 `38ac466`，继续在 `feat/workbench-polish-20261119` 独立分支开发。

## 文件与作用

- `web/src/c-overview.jsx`：增加当前证据范围卡，集中说明来源、快照时间、证据年龄与覆盖率的含义；事件接口等待响应时显示查询中，避免显示为零项待确认。
- `web/src/c-analytics.jsx`：区分选择范围与实际样本时间；说明范围以最新快照为终点、不会请求服务端历史；平均覆盖展示有效值数量和等权口径；消息与事件指标补充单位及接口异常原因；增加可读取的最新三源状态/覆盖率表格；事件分布等待响应时不显示零；导出补充时间基准与范围元数据。
- `web/src/c-trends.js`：统一覆盖值校验与范围选择，拒绝缺失、非有限、超出 0–1 的覆盖率；缺失值或超过 15 秒的采集间隔中断曲线，避免错误连线。15 秒是界面连续绘图阈值，不是业务新鲜度阈值。
- `web/src/c-analytics.css`：补充范围说明、明细表格与总览证据卡的布局，兼容窄屏。
- `web/tests/c-trends.test.js`：覆盖无效值、范围边界、缺失证据和采集中断。
- `web/tests/trends-acceptance.cjs`：通过隔离夹具和只读请求拦截，验证缺失值、两快照曲线、范围切换、JSON 导出、三种宽度和 503 后清理显示。

## 验证

- `node --test web/tests/c-trends.test.js web/tests/c-connection.test.js web/tests/c-display.test.js web/tests/c-state.test.js`：14/14 通过。
- 在 `web` 运行 `node node_modules/vite/bin/vite.js build`：通过。
- 浏览器第二阶段检查 7 项通过，页面脚本错误为零；覆盖 1280、768、390 像素宽度。
- 四页三种宽度的截图与溢出检查保存在 `audit/frontend-stage2-20261121/after-stage2/`；交互验收结果为同目录上级的 `trends-result.json`。

浏览器脚本环境变量与第一阶段一致：`PLAYWRIGHT_MODULE`、`CHROME_PATH`、`UI_BASE_URL`、`UI_TOKEN`、`UI_RESULT`。运行 `node web/tests/trends-acceptance.cjs`；默认设备 demo01 的本地隔离服务需要正常响应四项查询。脚本会注入缺失覆盖值、模拟快照时间推进和 503，不调用写入接口。

这些是界面验收数据，不证明真实传感、MQTT、云端或长时运行结果。未改动业务 API、数据库结构、B 算法及事件确认/关闭条件。

## 下一阶段

细化事件确认与实验诊断的信息层级、操作条件、时间线和证据入口；然后进行整体验收与集成。第一、二阶段目前仍在独立分支，尚未合入 main。
