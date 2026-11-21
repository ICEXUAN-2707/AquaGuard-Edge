import React, { useState } from 'react'
import { label, localTime } from './c-display.js'
import './c-analytics.css'
import { coveragePercent, trendRange, coveragePath } from './c-trends.js'

const sources=[['flow','水流','#27704f'],['water','水接触','#b47733'],['presence','人员检测','#6082ad']]
export function Analytics({data,history,device}) {
  const [minutes,setMinutes]=useState(5)
  const available=Boolean(data.live?.value)
  const {start,end,rows:sessionRows}=trendRange(history,minutes)
  const rows=available?sessionRows:[]
  const events=data.events?.value?.items||[]
  const groups=[['OPEN','处理中'],['CLOSED','已关闭']].map(([key,name])=>({name,count:events.filter(e=>e.lifecycle===key).length}))
  const coverage=rows.flatMap(row=>sources.map(([key])=>coveragePercent(row.summary?.[key]?.coverage_ratio))).filter(value=>value!==null)
  function exportData(){
    const url=URL.createObjectURL(new Blob([JSON.stringify({device,scope:'browser_session',minutes,time_basis:'snapshot_captured_at',range_start:start,range_end:end,snapshots:rows},null,2)],{type:'application/json'}))
    const link=document.createElement('a');link.href=url;link.download='aquaguard-session-trends.json';link.click();URL.revokeObjectURL(url)
  }
  return <div className="analytics-page">
    <div className="page-heading"><div><p className="eyebrow">DATA OBSERVATORY</p><h2>数据可视化</h2><p className="muted">把感知质量、状态变化与事件处理放在同一视野。</p></div><button onClick={exportData} disabled={!rows.length}>导出趋势数据</button></div>
    <div className="analytics-toolbar"><span className="source-chip">{available?`${label(data.live.value.origin)}数据`:'数据暂不可用'}</span><span>本次会话 · 每 5 秒查询</span><div role="group" aria-label="趋势时间范围">{[5,15,30].map(n=><button key={n} aria-pressed={minutes===n} onClick={()=>setMinutes(n)}>{n} 分钟</button>)}</div></div>
    <p className="trend-scope">{rows.length?`已采集 ${rows.length} 个不同时间的快照 · 实际样本：${localTime(new Date(rows[0].time).toISOString())} 至 ${localTime(new Date(rows.at(-1).time).toISOString())}`:'尚无可展示快照。'}<br/>范围以最新快照时间为终点；选择 5 / 15 / 30 分钟不会查询服务端历史。相同快照不会重复累计。</p>
    <div className="analytics-kpis">{[['已采集快照',rows.length,'条 / 当前范围'],['平均窗口覆盖',coverage.length?`${(coverage.reduce((a,b)=>a+b,0)/coverage.length).toFixed(1)}%`:'—',`${coverage.length} 个有效源覆盖值 · 等权平均`],['待确认事件',data.events?.value?events.filter(e=>e.lifecycle==='OPEN'&&e.ack_status==='UNACKNOWLEDGED').length:'—',data.events?.error||'项 / 最新返回记录内'],['待同步消息',data.sync?.value?.pending_count??'—',data.sync?.error||'条 / 本地 Outbox']].map(([name,value,note])=><section key={name}><span>{name}</span><strong>{value}</strong><small>{note}</small></section>)}</div>
    <section><div className="section-title"><div><p className="eyebrow">SIGNAL COVERAGE</p><h3>三源窗口覆盖趋势</h3></div><div className="chart-legend">{sources.map(([key,name,color])=><span key={key}><i style={{background:color}}/>{name}</span>)}</div></div>
      {rows.length>1?<><svg className="coverage-chart" viewBox="0 0 900 240" role="img" aria-label="三源覆盖率时间趋势，纵轴 0 到 100 百分比"><title>三源窗口覆盖率；缺失证据以断线展示</title>{[0,25,50,75,100].map(v=><g key={v}><line x1="45" x2="880" y1={210-v*1.8} y2={210-v*1.8}/><text x="4" y={214-v*1.8}>{v}%</text></g>)}{sources.map(([key,name,color])=>{const path=coveragePath(rows,key,start,end);return <path key={key} d={path} fill="none" stroke={color} strokeWidth="3"><title>{name}</title></path>})}</svg><div className="chart-time"><span>{localTime(new Date(start).toISOString())}</span><span>{localTime(new Date(end).toISOString())}</span></div></>:<div className="chart-empty" role="status">{data.live?.error||'等待至少两个有效快照，约 5–10 秒后显示趋势。'}</div>}
      <p className="muted">纵轴：覆盖率（%）；横轴：快照时间。缺失或无效覆盖值、超过 15 秒的采集间隔以断线表示。覆盖率不是检测准确率。</p></section>
    <section className="latest-evidence"><h3>最新快照明细</h3><p className="muted">{available?`来源：${label(data.live.value.origin)} · 快照时间：${localTime(data.live.value.captured_at)}`:data.live?.error||'正在查询最新快照…'}</p>{available&&<div className="evidence-table-wrap"><table><caption>三源最新状态与覆盖率（可与趋势曲线对照）</caption><thead><tr><th scope="col">感知源</th><th scope="col">状态</th><th scope="col">窗口覆盖</th></tr></thead><tbody>{sources.map(([key,name])=>{const item=data.live.value.sensor_summary?.[key];const percent=coveragePercent(item?.coverage_ratio);return <tr key={key}><th scope="row">{name}</th><td>{label(item?.state)}</td><td>{percent===null?'未知':`${percent.toFixed(1)}%`}</td></tr>})}</tbody></table></div>}</section>
    <div className="analytics-bottom"><section><div className="section-title"><h3>感知状态轨迹</h3><span className="muted">从左到右 · 时间推进</span></div>{sources.map(([key,name])=><div className="state-track" key={key}><b>{name}</b><div>{rows.map(row=><span key={row.time} className={`track-${row.summary[key]?.state||'unknown'}`} title={`${localTime(new Date(row.time).toISOString())} · ${label(row.summary[key]?.state||'unknown')}`}/>)}</div><small>{available?label(data.live.value.sensor_summary[key]?.state||'unknown'):'不可用'}</small></div>)}<p className="muted">悬停查看快照时间与状态；灰色表示未知，未知不等于正常。</p></section>
    <section><div className="section-title"><h3>事件处理分布</h3><span className="small-tag">最新 100 项内</span></div>{data.events?.error?<p role="status">{data.events.error}</p>:!data.events?.value?<p role="status">正在查询事件记录…</p>:groups.map(group=><div className="event-bar" key={group.name}><span>{group.name}</span><div><i style={{width:`${events.length?group.count/events.length*100:0}%`}}/></div><b>{group.count}</b></div>)}<p className="muted">按当前接口返回记录统计，非全量历史。{data.events?.value?.next_cursor?'存在更多记录。':''}</p></section></div>
    <p className="analytics-footnote">趋势仅在页面打开期间累积，最多保留 30 分钟；刷新、切换设备或断开连接后清空。服务不可用时隐藏旧趋势，恢复后继续会话采集。</p>
  </div>
}
