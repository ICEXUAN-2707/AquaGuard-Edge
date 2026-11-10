const words = {
  ACTIVE:'物理异常仍在', CLEARED:'物理清除候选', UNKNOWN:'未知', OPEN:'处理中', RESOLVED:'已恢复', CLOSED:'已关闭',
  ACKNOWLEDGED:'已确认', UNACKNOWLEDGED:'未确认', simulation:'模拟', hardware:'硬件', mixed:'混合来源', unknown:'未知',
  wet:'湿', dry:'干', active:'流水', inactive:'未流水', present:'检出人员', absent:'未检出人员',
  ATTENDED_FLOW:'有人用水', POSSIBLE_UNATTENDED_FLOW:'可能无人流水', IDLE:'空闲',
  NONE:'尚无回执', TRANSPORT:'传输确认', BUSINESS:'业务回执', WATER_CONTACT:'水接触信号',
  VALID:'有效', DEGRADED:'部分证据不足', UNAVAILABLE:'不可用', valid:'有效', invalid:'无效',
  rules:'规则分析', fallback:'保守回退', ml:'模型分析', RUNNING:'运行中', PLANNED:'待开始',
  DURATION_NOT_REACHED:'持续时间尚未达到判定条件', PRESENCE_DETECTED:'检测到人员在场',
  WINDOW_STALE:'分析窗口已过期', WATER_DETECTED:'检测到水接触', ACKNOWLEDGED_EVENT:'用户已确认',
}
export const label = value => words[value] || value || '未知'
export function localTime(value) {
  const date=new Date(value)
  return value && Number.isFinite(date.getTime()) ? date.toLocaleString('zh-CN',{hour12:false}) : '暂无时间记录'
}
export function ageText(age,captured,now=Date.now()) {
  const date=Date.parse(captured)
  if(typeof age!=='number' || !Number.isFinite(age) || age<0 || !Number.isFinite(date) || now<date) return '未知'
  return `${(age+(now-date)/1000).toFixed(1)} 秒`
}
