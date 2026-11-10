import React from 'react'
import { label, localTime, ageText } from './c-display.js'
import { DataPath } from './c-navigation.jsx'

function Pending({error,children}) {
  return <p role="status" className={error?'warning':'muted'}>{error || children || '正在查询…'}</p>
}

export function Overview({data,onRefresh,onEvents}) {
  const live=data.live?.value, assessment=data.assessment?.value, sync=data.sync?.value
  const events=data.events?.value?.items || []
  const safety=assessment?.safety_signals || []
  const alarm=safety.some(s=>s.quality==='VALID' && s.value)
  const attention=events.filter(e=>e.lifecycle==='OPEN' && e.ack_status==='UNACKNOWLEDGED')
  return <>
    <div className="page-heading"><div><p className="eyebrow">LIVE MONITORING</p><h2>实时总览</h2><p className="muted">了解当前用水情况，关注异常与数据新鲜度。</p></div><button onClick={onRefresh}>刷新</button></div>
    <section className={`situation-banner ${alarm?'is-alert':!assessment||assessment.assessment.situation==='UNKNOWN'?'is-unknown':''}`}>
      <div><p className="eyebrow">当前用水情境</p><h3>{assessment?label(assessment.assessment.situation):'等待有效分析'}</h3><p>{data.assessment?.error || '情境判断与水接触安全信号分别展示。'}</p></div>
      <div className="safety-summary"><span className={`status-pill ${alarm?'alert':'neutral'}`}>{alarm?'水接触异常候选':'独立安全信号'}</span><p>{alarm?'请查看现场情况，并在事件页确认知晓。':safety.length?'查看下方有效信号与证据。':'暂无可用安全信号'}</p>{alarm&&<button onClick={onEvents}>查看事件 →</button>}</div>
    </section>
    <DataPath/>
    <div className="section-title"><h3>三源感知</h3><span className="muted">每 5 秒查询 · 未知不代表正常</span></div>
    {data.live?.error?<Pending error={`传感快照：${data.live.error}`}/>:live?<>
      <p className="snapshot-meta">来源：{label(live.origin)} · 质量：{label(live.data_quality)} · 快照：{localTime(live.captured_at)}</p>
      <div className="grid sensor-grid">{Object.entries(live.sensor_summary).map(([name,value],index)=><section key={name} className="sensor-card"><div className="sensor-heading"><span className="sensor-number">0{index+1}</span><h3>{{flow:'水流',water:'水接触',presence:'人员检测'}[name]}</h3></div><strong className={value.state==='wet'?'danger-text':value.state==='unknown'?'neutral-text':''}>{label(value.state)}</strong><div className="sensor-metadata"><span>证据年龄<b>{ageText(value.age_sec,live.captured_at)}</b></span><span>窗口覆盖<b>{typeof value.coverage_ratio==='number'?`${(value.coverage_ratio*100).toFixed(0)}%`:'未知'}</b></span></div>{name==='presence'&&<p className="sensor-note">未检出人员，不代表已证明无人。</p>}</section>)}</div>
    </>:<Pending>正在读取传感快照…</Pending>}
    <div className="overview-bottom"><section><div className="section-title"><h3>判断依据</h3><span className="small-tag">可追溯分析</span></div>{data.assessment?.error?<Pending error={data.assessment.error}/>:assessment?<>
      <ul className="reason-list">{assessment.assessment.reason_codes.map(code=><li key={code}>{label(code)}</li>)}</ul>
      <p className="muted">来源：{label(assessment.assessment.origin)} · 模式：{label(assessment.assessment.inference_mode)}</p>
      <div className="signal-list">{safety.map(s=><div key={s.signal_id}><span className={`signal-dot ${s.quality==='VALID'&&s.value?'alert':''}`}/><div><b>{label(s.signal_type)}</b><p>{s.quality==='VALID'?(s.value?'异常存在候选':'物理清除候选'):'证据不可用'} · {label(s.quality)}</p><time>{localTime(s.observed_at)}</time></div></div>)}</div>
      <details><summary>技术详情与原始原因码</summary><p>模型版本：{assessment.assessment.model_version}</p><p>{assessment.assessment.reason_codes.join(' · ')}</p></details>
    </>:<Pending/>}</section>
    <section><div className="section-title"><h3>云同步</h3><span className="small-tag">独立于本地感知</span></div>{data.sync?.error?<Pending error={data.sync.error}/>:sync?<><div className="sync-counts"><div><strong>{sync.pending_count}</strong><span>待同步</span></div><div><strong>{sync.failed_count}</strong><span>同步失败</span></div></div><p className="receipt">回执级别：{label(sync.last_ack_level)}</p><p className="muted">{live?`快照中的云连接状态：${label(live.cloud_status)}。`:''}回执不代表联系人收到。</p></>:<Pending/>}
    <div className="event-shortcut"><p>{data.events?.error?'事件查询暂不可用':`当前返回记录中 ${attention.length} 项待确认`}</p><button onClick={onEvents}>进入事件确认 →</button><small>查询范围为该设备最新 100 项</small></div></section></div>
  </>
}
