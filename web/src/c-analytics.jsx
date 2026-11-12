import React, { useState } from 'react'
import { label, localTime } from './c-display.js'
import './c-analytics.css'

const sources=[['flow','水流','#27704f'],['water','水接触','#b47733'],['presence','人员检测','#6082ad']]
export function Analytics({data,history,device}) {
  const [minutes,setMinutes]=useState(5)
  const available=Boolean(data.live?.value)
  const end=history.at(-1)?.time || Date.now(), start=end-minutes*60000
  const rows=available?history.filter(row=>row.time>=start):[]
  const events=data.events?.value?.items||[]
  const groups=[['OPEN','处理中'],['CLOSED','已关闭']].map(([key,name])=>({name,count:events.filter(e=>e.lifecycle===key).length}))
  const coverage=rows.flatMap(row=>sources.map(([key])=>row.summary[key]?.coverage_ratio)).filter(Number.isFinite)
  function exportData(){
    const url=URL.createObjectURL(new Blob([JSON.stringify({device,scope:'browser_session',minutes,snapshots:rows},null,2)],{type:'application/json'}))
    const link=document.createElement('a');link.href=url;link.download='aquaguard-session-trends.json';link.click();URL.revokeObjectURL(url)
  }
  return <div className="analytics-page">
    <div className="page-heading"><div><p className="eyebrow">DATA OBSERVATORY</p><h2>数据可视化</h2><p className="muted">把感知质量、状态变化与事件处理放在同一视野。</p></div><button onClick={exportData} disabled={!rows.length}>导出趋势数据</button></div>
    <div className="analytics-toolbar"><span className="source-chip">{available?`${label(data.live.value.origin)}数据`:'数据暂不可用'}</span><span>本次会话 · 每 5 秒查询</span><div role="group" aria-label="趋势时间范围">{[5,15,30].map(n=><button key={n} aria-pressed={minutes===n} onClick={()=>setMinutes(n)}>{n} 分钟</button>)}</div></div>
    <div className="analytics-kpis">{[['已采集快照',rows.length,'条 / 当前范围'],['平均窗口覆盖',coverage.length?`${(coverage.reduce((a,b)=>a+b,0)/coverage.length*100).toFixed(1)}%`:'—','三源有效覆盖值均值'],['待确认事件',data.events?.value?events.filter(e=>e.lifecycle==='OPEN'&&e.ack_status==='UNACKNOWLEDGED').length:'—','最新返回记录内'],['待同步消息',data.sync?.value?.pending_count??'—','本地 Outbox']].map(([name,value,note])=><section key={name}><span>{name}</span><strong>{value}</strong><small>{note}</small></section>)}</div>
    <section><div className="section-title"><div><p className="eyebrow">SIGNAL COVERAGE</p><h3>三源窗口覆盖趋势</h3></div><div className="chart-legend">{sources.map(([key,name,color])=><span key={key}><i style={{background:color}}/>{name}</span>)}</div></div>
      {rows.length>1?<><svg className="coverage-chart" viewBox="0 0 900 240" role="img" aria-label="三源覆盖率时间趋势，纵轴 0 到 100 百分比"><title>三源窗口覆盖率；缺失证据以断线展示</title>{[0,25,50,75,100].map(v=><g key={v}><line x1="45" x2="880" y1={210-v*1.8} y2={210-v*1.8}/><text x="4" y={214-v*1.8}>{v}%</text></g>)}{sources.map(([key,name,color])=>{let active=false;const path=rows.map(row=>{const v=row.summary[key]?.coverage_ratio;if(!Number.isFinite(v)){active=false;return ''}const command=active?'L':'M';active=true;return `${command}${45+(row.time-start)/(end-start)*835},${210-Math.max(0,Math.min(1,v))*180}`}).join(' ');return <path key={key} d={path} fill="none" stroke={color} strokeWidth="3"><title>{name}</title></path>})}</svg><div className="chart-time"><span>{localTime(new Date(start).toISOString())}</span><span>{localTime(new Date(end).toISOString())}</span></div></>:<div className="chart-empty" role="status">{data.live?.error||'等待至少两个有效快照，约 5–10 秒后显示趋势。'}</div>}
      <p className="muted">覆盖率表示窗口内证据完整程度，不代表检测准确率；曲线重合时可结合下方各源状态查看。</p></section>
    <div className="analytics-bottom"><section><div className="section-title"><h3>感知状态轨迹</h3><span className="muted">从左到右 · 时间推进</span></div>{sources.map(([key,name])=><div className="state-track" key={key}><b>{name}</b><div>{rows.map(row=><span key={row.time} className={`track-${row.summary[key]?.state||'unknown'}`} title={`${localTime(new Date(row.time).toISOString())} · ${label(row.summary[key]?.state||'unknown')}`}/>)}</div><small>{available?label(data.live.value.sensor_summary[key]?.state||'unknown'):'不可用'}</small></div>)}<p className="muted">悬停查看快照时间与状态；灰色表示未知，未知不等于正常。</p></section>
    <section><div className="section-title"><h3>事件处理分布</h3><span className="small-tag">最新 100 项内</span></div>{data.events?.error?<p role="status">{data.events.error}</p>:groups.map(group=><div className="event-bar" key={group.name}><span>{group.name}</span><div><i style={{width:`${events.length?group.count/events.length*100:0}%`}}/></div><b>{group.count}</b></div>)}<p className="muted">按当前接口返回记录统计，非全量历史。{data.events?.value?.next_cursor?'存在更多记录。':''}</p></section></div>
    <p className="analytics-footnote">趋势仅在页面打开期间累积，最多保留 30 分钟；刷新、切换设备或断开连接后清空。服务不可用时隐藏旧趋势，恢复后继续会话采集。</p>
  </div>
}
