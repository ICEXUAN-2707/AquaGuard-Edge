# 264秒推进停顿排查

## 已有证据

a66e65e独立小时实验实际3602.907秒，215个稳态样本中210次200、4次503、1次请求失败；最大采样空档279.25秒，故结果FAIL。数据库完整性、无重复OPEN及退出端口检查通过。

慢周期分别含tick约5.593秒、step约16.297/20.985/263.688秒；最长周期整个服务进程CPU约0.406秒。只能提示等待或调度停顿，不能据此指认具体磁盘、锁或算法。

观察器超时堆栈同时落在process_tree枚举和pathlib相对路径遍历等位置，且睡眠差值没有显著增加。说明采样器本身也受到停顿影响，不能把279秒全部视作业务计算耗时。

## 明确发现的环境配置

原计划任务Settings.Priority=7。Windows官方文档将其映射到Below Normal CPU、Low I/O和Low memory优先级。实际执行期间同机有其他工作，资源调度是需要验证的共同因素；现有记录不能证明这是全部503唯一根因。

后续任务显式使用Priority=4（Normal CPU、Normal I/O、Normal memory），不使用高/实时优先级，不修改其他软件或全局电源策略。新任务已核实Settings.Priority=4、观测进程PriorityClass=Normal、业务进程PriorityClass=32（Normal）。

官方依据：https://learn.microsoft.com/en-us/windows/win32/taskschd/taskschedulerschema-priority-settingstype-element

## 新增诊断

- runtime_diagnostics.phase：发布当前阶段并记录墙钟/线程CPU、最大耗时及对应CPU；保存慢阶段日志。返回阶段字典采用替换而非原地扩容，避免API序列化期间并发修改。
- online.py分别计时raw_water_ingest、alignment、checkpoint_compute_write_fsync、experiment_projection、context_verify_event_transaction、water_event_transaction、live_assessment_verify_publish。
- store.py及水/情境/投影事务：单列sqlite_connect、sqlite_begin_immediate、sqlite_commit、sqlite_close；保留原5秒SQLite连接超时、事务边界和异常行为。
- run.py在推进期间注册30秒重复服务线程堆栈转储，正常推进后取消；堆栈仅本地保存，无变量/凭据，不把业务时间改成完成时间。
- 观测器分别记录采样开始UTC、采集结束UTC、collection_seconds；错误HTTP也保留耗时及安全异常类型，避免把采样结束时间误当开始时间。

## 验证

初轮诊断函数名phase与仿真局部阶段数值同名导致测试TypeError，已改用timed_phase别名，未通过改业务策略绕过。生命周期/在线相关13项通过；水/投影/在线/暂停及真实锁等待35项通过；新增慢检查点与锁等待诊断5项通过，范围重叠不相加。

真实SQLite测试用另一连接持有BEGIN IMMEDIATE，工作线程等待后释放，确认等待归属sqlite_begin_immediate且嵌套阶段恢复；慢检查点测试注入150ms，确认归属检查点阶段，不把它误写为SQL等待。

7c582f3以普通优先级、新目录/8056端口运行180秒短程，最终数据见docs/audit/step-stall-20261113/pilot/。阶段耗时和当前阶段已通过认证诊断接口实际采到。后续补充的慢阶段日志/CPU配对字段另有专项测试，不冒充该进程已加载更新代码。

## 结论与下一步

当前已确认并修正计划任务后台优先级这一实验配置问题，补齐定位所需阶段与服务堆栈。不能声称历史264秒停顿已经被最终归因或彻底修复。

下一轮固定新诊断提交、普通优先级完整小时，在无显著睡眠/采样空档的环境验证；若再现，按服务线程堆栈及慢阶段paired CPU直接区分SQL锁等待、检查点计算/写入、提交/fsync或调度空档。保持原失败标准，不提高TTL、不裁掉失败样本。暂不做数据库清理、算法重写或云接入。
