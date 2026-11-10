import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './c.css'
import './c-workbench.css'
import { AckIntent, ResponseOrder } from './c-state.js'
import { Overview } from './c-overview.jsx'
import { Events } from './c-events.jsx'
import { Experiment } from './c-experiment.jsx'
import { label } from './c-display.js'
import { requestJSON } from './c-request.js'

function download(value) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value,null,2)], {type:'application/json'}))
  const identity=String(value.event?.event_id||value.trial_id||'local-evidence').replace(/[^a-zA-Z0-9_-]/g,'_')
  const link = document.createElement('a'); link.href=url; link.download=`aquaguard-${identity}.json`; link.click(); URL.revokeObjectURL(url)
}
function App() {
  const [token,setToken]=useState(''), [draft,setDraft]=useState(''), [device,setDevice]=useState('demo01')
  const [tab,setTab]=useState('实时总览'), [epoch,setEpoch]=useState(0), [data,setData]=useState({})
  const [selected,setSelected]=useState(''), [detail,setDetail]=useState(null), [notice,setNotice]=useState('')
  const [busy,setBusy]=useState(false), [trial,setTrial]=useState('demo-trial'), [experiment,setExperiment]=useState(null)
  const operation=useRef(new AckIntent())
  const [settingsOpen,setSettingsOpen]=useState(false)
  const experimentVersion=useRef(new ResponseOrder())
  async function request(path, options={}) {
    return requestJSON(path,token,options)
  }
  function message(error) {
    if(error instanceof TypeError)return '无法连接本地服务，请检查服务是否运行'
    if(error instanceof SyntaxError)return '服务响应无法解析，请重试'
    return error.status===401?'访问凭据无效，请重新连接':error.status===503?'不可用或证据已过期':error.status===404?'尚无对应数据':error.message
  }
  useEffect(()=>{ const id=setInterval(()=>setEpoch(x=>x+1),5000); return ()=>clearInterval(id) },[])
  useEffect(()=>{
    experimentVersion.current.next()
    setData({}); setDetail(null); setExperiment(null); operation.current.reset(); setSelected(''); setNotice('')
  },[token,device])
  async function loadExperiment() {
    const version=experimentVersion.current.next()
    setExperiment({loading:true})
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
    let body
    try {body=operation.current.prepare(event)}
    catch(error){setNotice(error.message);return}
    setBusy(true)
    try {
      await request(`/api/events/${encodeURIComponent(event.event_id)}/ack`,{method:'POST',body:JSON.stringify(body)})
      operation.current.reset(); setNotice('已确认；物理状态与生命周期由后端单独维护。'); setEpoch(x=>x+1)
    } catch(error) {
      if(error.status===409){operation.current.reset(); setNotice('版本或操作冲突，已重新查询；核对后再次确认。');setEpoch(x=>x+1)}
      else setNotice(`${message(error)}。网络结果不确定时，再次点击会重放原请求。`)
    } finally {setBusy(false)}
  }
  return <main>
    <header><div className="brand"><span className="brand-mark" aria-hidden="true">≈</span><div><h1>水知安 <span>AquaGuard Edge</span></h1><p>多源感知 · 用水异常监测工作台</p></div></div><span className="badge">实验环境 · 不发送真实通知</span></header>
    <div className="workspace-bar"><div><span className={`connection-dot ${token?'loaded':''}`}/><b>{token?'已装入访问凭据':'尚未连接'}</b><span className="bar-divider">/</span><span>设备 {device || '未选择'}</span><span className="source-chip">{data.live?.value?`${label(data.live.value.origin)}数据`:'来源待确认'}</span></div><button type="button" onClick={()=>setSettingsOpen(x=>!x)} aria-expanded={!token||settingsOpen}>{settingsOpen?'收起设置':'连接设置'}</button></div>
    <form hidden={Boolean(token)&&!settingsOpen} className="connection" onSubmit={e=>{e.preventDefault();setToken(draft);setDraft('');setSettingsOpen(false)}}>
      <label>设备<input value={device} onChange={e=>setDevice(e.target.value)} disabled={busy}/></label>
      <label>实验访问凭据<input type="password" autoComplete="off" value={draft} onChange={e=>setDraft(e.target.value)} placeholder={token?'凭据已装入内存':'输入启动时保存的 token'} disabled={busy}/></label>
      <button disabled={busy || !draft}>连接</button><button type="button" disabled={busy} onClick={()=>setToken('')}>断开</button>
    </form>
    <nav aria-label="工作台页面">{['实时总览','事件确认','实验诊断'].map((name,index)=><button key={name} aria-label={name} aria-current={tab===name?'page':undefined} onClick={()=>setTab(name)}><span className="nav-index" aria-hidden="true">0{index+1}</span>{name}</button>)}</nav>
    {!token?<section><h2>连接本地业务服务</h2><p>请先按本地演示手册启动服务，并通过该服务地址打开工作台。凭据仅保存在当前页面内存，刷新后需重新输入。</p></section>:<>
      {tab==='实时总览'&&<Overview data={data} onRefresh={()=>setEpoch(x=>x+1)} onEvents={()=>setTab('事件确认')}/>}
      {tab==='事件确认'&&<Events key={device} resource={data.events} selected={selected} onSelect={setSelected} detail={detail} busy={busy} retry={Boolean(operation.current.body)} onAck={ack} onDownload={download} notice={notice} onRefresh={()=>setEpoch(x=>x+1)}/>}
      {tab==='实验诊断'&&<Experiment trial={trial} onTrial={value=>{experimentVersion.current.next();setTrial(value);setExperiment(null)}} onQuery={loadExperiment} result={experiment} onDownload={download}/>}

    </>}
    <footer>本地结果、云同步与联系人送达分别验收 · 当前尚未完成真实硬件/云与独立验收</footer>
  </main>
}
createRoot(document.getElementById('root')).render(<App/> )
