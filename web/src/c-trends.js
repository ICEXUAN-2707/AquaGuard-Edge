export function coveragePercent(value) {
  return typeof value==='number' && Number.isFinite(value) && value>=0 && value<=1 ? value*100 : null
}
export function trendRange(history,minutes) {
  const valid=history.filter(row=>Number.isFinite(row.time)).sort((a,b)=>a.time-b.time)
  const end=valid.at(-1)?.time ?? null
  const start=end===null?null:end-minutes*60000
  return {start,end,rows:valid.filter(row=>row.time>=start&&row.time<=end)}
}
export function coveragePath(rows,key,start,end) {
  if(!Number.isFinite(start)||!Number.isFinite(end)||end<=start)return ''
  let previous=null
  return rows.map(row=>{
    const value=coveragePercent(row.summary?.[key]?.coverage_ratio)
    if(value===null){previous=null;return ''}
    const command=previous!==null&&row.time-previous<=15000?'L':'M'
    previous=row.time
    return `${command}${45+(row.time-start)/(end-start)*835},${210-value*1.8}`
  }).join(' ')
}
