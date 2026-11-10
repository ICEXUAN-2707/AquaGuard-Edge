import React, { useState, useEffect } from 'react'
import { label, localTime } from './c-display.js'

const eventName=type=>({WATER_CONTACT:'水接触异常',POSSIBLE_UNATTENDED_FLOW:'可能无人流水'}[type]||type)
const transitionName=type=>({WATER_DETECTED:'检测到水接触',DRY_CONFIRMATION_PENDING:'开始确认干燥状态',WATER_CLEAR_CANDIDATE:'出现物理清除候选',ACKNOWLEDGED:'用户已确认知晓',CONTEXT_RISK_DETECTED:'检测到情境风险',CONTEXT_ACTIVE:'情境异常仍在',CONTEXT_CLEARED:'情境异常清除候选',CONTEXT_UNKNOWN:'情境证据变为未知',EVIDENCE_EXPIRED:'证据已过期'}[type]||type)
const filters=['全部','未确认','活动异常','已恢复']
export function Events({resource,selected,onSelect,detail,busy,retry,onAck,onDownload,notice,onRefresh}) {
  const [filter,setFilter]=useState('全部')
  const [timelineLimit,setTimelineLimit]=useState(8)
  useEffect(()=>setTimelineLimit(8),[selected])
  const items=resource?.value?.items||[], event=detail?.value?.event
  const visible=items.filter(e=>filter==='全部'||filter==='未确认'&&e.ack_status==='UNACKNOWLEDGED'||filter==='活动异常'&&e.physical_status==='ACTIVE'||filter==='已恢复'&&e.lifecycle==='RESOLVED')
  return <>
    <div className="page-heading"><div><p className="eyebrow">EVENT WORKSPACE</p><h2>事件确认</h2><p className="muted">确认代表知晓，物理状态与事件生命周期独立维护。</p></div><button onClick={onRefresh}>刷新事件</button></div>
    <div className="event-layout"><section className="event-panel"><div className="section-title"><h3>事件记录</h3><span className="small-tag">已加载 {items.length} 项</span></div><p className="muted">仅查询该设备最新 100 项，筛选作用于已加载记录。</p>
      <div className="event-filters" role="group" aria-label="筛选事件">{filters.map(name=><button key={name} aria-pressed={filter===name} onClick={()=>setFilter(name)}>{name}</button>)}</div>
      {resource?.error?<p role="status" className="warning">{resource.error}</p>:!resource?.value?<p role="status" className="empty-state">正在查询事件…</p>:visible.length===0?<div className="empty-state"><b>{items.length?'当前筛选下没有事件':'暂无事件'}</b><p>有证据触发的事件将在此显示。</p></div>:<div className="event-cards">{visible.map(e=><button className={`event-card ${selected===e.event_id?'selected':''}`} key={e.event_id} disabled={busy} onClick={()=>onSelect(e.event_id)} aria-pressed={selected===e.event_id} aria-label={`${eventName(e.event_type)} ${e.event_type} ${label(e.physical_status)}`}><span className="event-card-top"><b>{eventName(e.event_type)}</b><span className={`event-state ${e.physical_status==='ACTIVE'?'danger':'neutral'}`}>{label(e.physical_status)}</span></span><span className="event-card-meta">{label(e.ack_status)} · {label(e.lifecycle)} · v{e.version}</span><time>{localTime(e.created_at)}</time><span className="event-card-id">{e.event_id}</span></button>)}</div>}
    </section><div className="event-detail-column">
      {detail?.error?<section><h3>事件详情暂不可用</h3><p role="status" className="warning">{detail.error}</p><button onClick={onRefresh}>重新查询</button></section>:event?<>
        <section className="event-detail"><div className="section-title"><h3>事件详情</h3><span className="small-tag">版本 {event.version}</span></div><h4>{eventName(event.event_type)}</h4><p className="muted">来源：{label(event.origin)} · 风险级：{event.escalation_level}</p>
          <div className="event-status-grid">{[['物理状态',label(event.physical_status)],['用户确认',label(event.ack_status)],['生命周期',label(event.lifecycle)]].map(([key,value])=><div key={key}><span>{key}</span><b className={key==='物理状态'&&event.physical_status==='ACTIVE'?'danger-text':''}>{value}</b></div>)}</div>
          <div className="ack-zone"><div><b>{event.ack_status==='ACKNOWLEDGED'?'已记录你的确认':'请核对现场与事件信息'}</b><p>“我已知晓”不会清除水接触异常，也不会替你关闭事件。</p></div><button className="primary-button" disabled={busy||(event.ack_status==='ACKNOWLEDGED'&&!retry)||event.lifecycle!=='OPEN'} onClick={onAck}>{busy?'提交中…':retry?'重试原确认请求':'我已知晓'}</button></div>
          <p role="status" className={notice?'action-notice':''}>{notice}</p><details><summary>事件标识与原始字段</summary><dl><dt>事件 ID</dt><dd>{event.event_id}</dd><dt>事件类型</dt><dd>{event.event_type}</dd><dt>创建时间</dt><dd>{event.created_at}</dd></dl></details><button className="export-button" onClick={()=>onDownload(detail.value)}>导出事件记录</button>
        </section>
        <section><div className="section-title"><h3>事件时间轴</h3><span className="small-tag">{detail.value.transitions.length} 次变化</span></div><p className="muted">最近 {Math.min(timelineLimit,detail.value.transitions.length)} / 共 {detail.value.transitions.length} 项 · 最新在前</p><ol className="event-timeline">{detail.value.transitions.slice(-timelineLimit).reverse().map(t=><li key={t.transition_id}><span className="timeline-version">v{t.event_version}</span><div><b>{transitionName(t.transition_type)}</b><time>{localTime(t.occurred_at)}</time><details><summary>查看证据与原始记录</summary><p>{t.transition_type}</p><p>证据：{t.evidence_refs.join(', ')||'用户操作'}</p><p>原始时间：{t.occurred_at}</p></details></div></li>)}</ol>{timelineLimit<detail.value.transitions.length&&<button onClick={()=>setTimelineLimit(x=>x+8)}>查看更早记录（还有 {detail.value.transitions.length-timelineLimit} 项）</button>}</section>
      </>:<section className="detail-placeholder"><span className="placeholder-symbol" aria-hidden="true">↗</span><h3>{selected?'正在读取事件详情':'选择一条事件查看详情'}</h3><p>查看物理状态、用户确认与可追溯时间轴。</p></section>}
    </div></div>
  </>
}
