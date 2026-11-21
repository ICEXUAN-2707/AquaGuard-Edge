// Query availability is separate from credentials, sensor freshness and cloud ACK.
export function connectionStatus(hasToken, resources) {
  if (!hasToken) return {kind:'idle',label:'尚未连接',detail:'连接后读取本地业务数据；访问凭据仅保存在当前页面内存。'}
  const rows=['live','assessment','sync','events'].map(key=>resources[key])
  if (rows.every(row=>!row)) return {kind:'checking',label:'正在检查接口',detail:'访问凭据已装入，正在等待本地业务查询响应。'}
  const failures=rows.filter(row=>row?.error).length
  const success=rows.filter(row=>row?.value).length
  if (failures) return {kind:success?'partial':'unavailable',label:success?'部分接口不可用':'业务数据暂不可用',detail:`${failures} / 4 项查询暂不可用，请查看各页面的具体原因。未知或过期不代表正常。`}
  if (success===4) return {kind:'available',label:'业务接口可用',detail:'本地查询已响应；传感质量、新鲜度和云同步结果分别以页面数据为准。'}
  return {kind:'checking',label:'等待完整响应',detail:'部分查询尚未完成，请等待本轮响应。'}
}
