import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './c.css'
import { AckIntent, ResponseOrder } from './c-state.js'

const words = { ACTIVE:'仍有物理异常', CLEARED:'物理清除候选', UNKNOWN:'未知', OPEN:'处理中', RESOLVED:'已恢复', CLOSED:'已关闭', ACKNOWLEDGED:'已确认', UNACKNOWLEDGED:'未确认', simulation:'模拟', hardware:'硬件', mixed:'混合来源', unknown:'来源未知', wet:'湿', dry:'干', active:'流水', inactive:'未流水', present:'检出人员', absent:'未检出人员', ATTENDED_FLOW:'有人用水', POSSIBLE_UNATTENDED_FLOW:'可能无人流水', IDLE:'空闲', NONE:'尚无回执', TRANSPORT:'传输确认', BUSINESS:'业务回执' }
const label = value => words[value] || value
function download(value) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value,null,2)], {type:'application/json'}))
  const link = document.createElement('a'); link.href=url; link.download='aquaguard-local-evidence.json'; link.click(); URL.revokeObjectURL(url)
}
function App() {
  const [token,setToken]=useState(''), [draft,setDraft]=useState(''), [device,setDevice]=useState('demo01')
  const [tab,setTab]=useState('实时总览'), [epoch,setEpoch]=useState(0), [data,setData]=useState({})
  const [selected,setSelected]=useState(''), [detail,setDetail]=useState(null), [notice,setNotice]=useState('')
  const [busy,setBusy]=useState(false), [trial,setTrial]=useState('demo-trial'), [experiment,setExperiment]=useState(null)
  const operation=useRef(new AckIntent())
  const closeIntent=useRef(null)
  const experimentVersion=useRef(new ResponseOrder())
  async function request(path, options={}) {
    const response=await fetch(path,{...options,headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json',...options.headers}})
    const body=await response.json()
    if(!response.ok) { const error=new Error(body.code || `HTTP ${response.status}`); error.status=response.status; error.body=body; throw error }
    return body
  }
  function message(error) {
    return error.status===401?'访问凭据无效，请重新连接':error.status===503?'不可用或证据已过期':error.status===404?'尚无对应数据':error.message
  }
  useEffect(()=>{ const id=setInterval(()=>setEpoch(x=>x+1),5000); return ()=>clearInterval(id) },[])
  useEffect(()=>{
    experimentVersion.current.next()
    closeIntent.current=null
    setData({}); setDetail(null); setExperiment(null); operation.current.reset(); setSelected(''); setNotice('')
  },[token,device])
  async function loadExperiment() {
    const version=experimentVersion.current.next()
    setExperiment(null)
    try {const value=await request(`/api/experiments/${encodeURIComponent(trial)}`);if(experimentVersion.current.current(version))setExperiment({value})}
    catch(error){if(experimentVersion.current.current(version))setExperiment({error:message(error)})}
  }
  useEffect(()=>{
    if(!token || !device) return
    const controller=new AbortController()
    const routes={live:`/api/devices/${encodeURIComponent(device)}/live`, assessment:`/api/devices/${encodeURIComponent(device)}/assessment`,sync:`/api/sync/status?device_id=${encodeURIComponent(device)}`,events:`/api/events?device_id=${encodeURIComponent(device)}&limit=100`}
    Promise.all(Object.entries(routes).map(async([key,path])=>{
      try{return [key,{value:await request(path,{signal:controller.signal})}]}catch(error){return [key,{error:message(error)}]}
    })).then(entries=>{if(!controller.signal.aborted) setData(Object.fromEntries(entries))})
    return ()=>controller.abort()
  },[token,device,epoch])
  useEffect(()=>{
    closeIntent.current=null
    operation.current.reset(); setNotice(''); setDetail(null)
  },[selected])
  useEffect(()=>{
    if(!token || !selected) return
    const controller=new AbortController()
    request(`/api/events/${encodeURIComponent(selected)}`,{signal:controller.signal}).then(value=>{if(!controller.signal.aborted)setDetail({value})}).catch(error=>{if(!controller.signal.aborted)setDetail({error:message(error)})})
    return ()=>controller.abort()
  },[token,selected,epoch])
  async function ack() {
    if(busy || !detail?.value) return
    const event=detail.value.event
    const body=operation.current.prepare(event)
    setBusy(true)
    try {
      await request(`/api/events/${encodeURIComponent(event.event_id)}/ack`,{method:'POST',body:JSON.stringify(body)})
      operation.current.reset(); setNotice('已确认；物理状态与生命周期由后端单独维护。'); setEpoch(x=>x+1)
    } catch(error) {
      if(error.status===409){operation.current.reset(); setNotice('版本或操作冲突，已重新查询；核对后再次确认。');setEpoch(x=>x+1)}
      else setNotice(`${message(error)}。网络结果不确定时，再次点击会重放原请求。`)
    } finally {setBusy(false)}
  }
  async function closeEvent() {
    if(busy || !detail?.value) return
    const event=detail.value.event
    closeIntent.current ||= {schema_version:'1.1',expected_version:event.version,idempotency_key:crypto.randomUUID()}
    setBusy(true)
    try {
      await request(`/api/events/${encodeURIComponent(event.event_id)}/close`,{method:'POST',body:JSON.stringify(closeIntent.current)})
      closeIntent.current=null;setNotice('事件已关闭；再次发生将创建新的未确认事件。');setEpoch(x=>x+1)
    } catch(error) {
      if(error.status===409 || error.status===400){closeIntent.current=null;setNotice('关闭未完成：请核对确认状态、恢复证据与版本。');setEpoch(x=>x+1)}
      else setNotice(`${message(error)}。再次点击会重放原关闭请求。`)
    } finally {setBusy(false)}
  }
  const live=data.live?.value, assessment=data.assessment?.value, sync=data.sync?.value, event=detail?.value?.event
  return <main>
    <header><div><p className="eyebrow">AQUAGUARD EDGE · 本地原型</p><h1>水知安</h1></div><span className="badge">实验环境 · 不发送真实通知</span></header>
    <form className="connection" onSubmit={e=>{e.preventDefault();setToken(draft);setDraft('')}}>
      <label>设备<input value={device} onChange={e=>setDevice(e.target.value)} disabled={busy}/></label>
      <label>实验访问凭据<input type="password" autoComplete="off" value={draft} onChange={e=>setDraft(e.target.value)} placeholder={token?'凭据已装入内存':'输入启动时保存的 token'} disabled={busy}/></label>
      <button disabled={busy || !draft}>连接</button><button type="button" disabled={busy} onClick={()=>setToken('')}>断开</button>
    </form>
    <nav>{['实时总览','事件确认','实验诊断'].map(name=><button key={name} aria-current={tab===name?'page':undefined} onClick={()=>setTab(name)}>{name}</button>)}</nav>
    {!token?<section><h2>连接本地业务服务</h2><p>请先按本地演示手册启动服务，并通过该服务地址打开工作台。凭据仅保存在当前页面内存，刷新后需重新输入。</p></section>:<>
      {tab==='实时总览'&&<>
        <div className="section-title"><h2>实时总览</h2><button onClick={()=>setEpoch(x=>x+1)}>刷新</button></div>
        <p className="muted">每5秒查询一次。缺失、过期与未知均不会显示为正常。</p>
        {data.live?.error?<p role="status" className="warning">传感快照：{data.live.error}</p>:live?<>
          <p>来源：{label(live.origin)} · 质量：{live.data_quality} · 快照：{live.captured_at}</p>
          <div className="grid">{Object.entries(live.sensor_summary).map(([name,value])=><section key={name}><h3>{{flow:'水流',water:'水接触',presence:'人员检测'}[name]}</h3><strong>{label(value.state)}</strong><p>证据年龄：{value.age_sec===null?'未知':`${(value.age_sec+Math.max(0,(Date.now()-Date.parse(live.captured_at))/1000)).toFixed(1)}秒`}</p><p>窗口覆盖：{(value.coverage_ratio*100).toFixed(0)}%</p></section>)}</div>
          <p>快照中的云连接状态：{live.cloud_status}（与传感质量分开）</p>
        </>:<p role="status">正在读取传感快照…</p>}
        <section><h3>用水情境与独立安全信号</h3>{data.assessment?.error?<p className="warning">{data.assessment.error}</p>:assessment?<><strong>{label(assessment.assessment.situation)}</strong><p>{assessment.assessment.reason_codes.join(' · ')}</p><p>来源：{label(assessment.assessment.origin)} · 模式：{assessment.assessment.inference_mode}</p><ul>{assessment.safety_signals.map(s=><li key={s.signal_id}>{s.signal_type}：{s.quality==='VALID'?(s.value?'异常存在候选':'物理清除候选'):'证据不可用'} · {s.quality} · {s.observed_at}</li>)}</ul></>:<p>正在查询…</p>}</section>
        <section><h3>云同步</h3>{data.sync?.error?<p className="warning">{data.sync.error}</p>:sync?<p>待发 {sync.pending_count} · 失败 {sync.failed_count} · {label(sync.last_ack_level)}。回执不代表联系人收到。</p>:<p>正在查询…</p>}</section>
      </>}
      {tab==='事件确认'&&<><h2>事件确认</h2><p className="muted">仅显示该设备最新100项。确认代表知晓，不代表水已干或事件已关闭。</p>
        {data.events?.error?<p className="warning">{data.events.error}</p>:<div className="event-list">{(data.events?.value?.items||[]).map(e=><button key={e.event_id} disabled={busy} onClick={()=>setSelected(e.event_id)}>{e.event_type} · {label(e.physical_status)} · v{e.version}</button>)}{data.events?.value?.items.length===0&&<p>暂无事件</p>}</div>}
        {detail?.error&&<p className="warning">{detail.error}</p>}
        {event&&<section><h3>事件详情</h3><dl>{[['事件',event.event_id],['生命周期',label(event.lifecycle)],['用户确认',label(event.ack_status)],['物理状态',label(event.physical_status)],['风险级',event.escalation_level],['来源',label(event.origin)],['版本',event.version]].map(([key,value])=><React.Fragment key={key}><dt>{key}</dt><dd>{value}</dd></React.Fragment>)}</dl>
          <button disabled={busy || (event.ack_status==='ACKNOWLEDGED' && !operation.current.body) || event.lifecycle!=='OPEN'} onClick={ack}>{busy?'提交中…':operation.current.body?'重试原确认请求':'我已知晓'}</button><button onClick={()=>download(detail.value)}>导出事件记录</button>
          <button disabled={busy || (!closeIntent.current && (event.lifecycle!=='OPEN' || event.ack_status!=='ACKNOWLEDGED' || event.physical_status!=='CLEARED'))} onClick={closeEvent}>{closeIntent.current?'重试原关闭请求':'关闭已恢复事件'}</button>
          <p className="muted">关闭需已确认且恢复证据仍新鲜；再次发生会创建新的未确认事件。</p>
          <ol>{detail.value.transitions.map(t=><li key={t.transition_id}>v{t.event_version} · {t.occurred_at} · {t.transition_type}<p className="muted">证据：{t.evidence_refs.join(', ')||'用户操作'}</p></li>)}</ol>
        </section>}<p role="status">{notice}</p>
      </>}
      {tab==='实验诊断'&&<section><h2>实验诊断</h2><p>仅查询与导出受控实验，不提供执行回放或通知入口。</p><label>实验ID<input value={trial} onChange={e=>{experimentVersion.current.next();setTrial(e.target.value);setExperiment(null)}}/></label><button onClick={loadExperiment}>查询</button>{experiment?.error&&<p className="warning">{experiment.error}</p>}{experiment?.value&&<><p>来源：{label(experiment.value.source)} · 状态：{experiment.value.status}</p><pre>{JSON.stringify(experiment.value,null,2)}</pre><button onClick={()=>download(experiment.value)}>导出实验记录</button></>}</section>}
    </>}
    <footer>本地结果、云同步与联系人送达分别验收 · 当前尚未完成真实硬件/云与独立验收</footer>
  </main>
}
createRoot(document.getElementById('root')).render(<App/> )
