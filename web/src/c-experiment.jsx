import React from 'react'
import { label, localTime } from './c-display.js'

export function Experiment({trial,onTrial,onQuery,result,onDownload}) {
  const value=result?.value
  return <>
    <div className="page-heading"><div><p className="eyebrow">EXPERIMENT & EVIDENCE</p><h2>实验诊断</h2><p className="muted">查询实验运行与证据引用，明确区分模拟数据和真实采集。</p></div></div>
    <section className="trial-search"><form onSubmit={e=>{e.preventDefault();if(trial.trim())onQuery()}}><label>实验ID<input value={trial} onChange={e=>onTrial(e.target.value)} placeholder="输入 trial ID" autoComplete="off"/></label><button className="primary-button" disabled={!trial.trim()}>查询</button></form><div className="trial-examples"><span>已支持的实验示例</span><button onClick={()=>onTrial('demo-trial')}>内置模拟 · demo-trial</button><button onClick={()=>onTrial('mqtt-trial')}>MQTT 输入 · mqtt-trial</button></div><p className="muted">示例是否存在取决于当前服务运行模式。查询不会启动实验或发送通知。</p></section>
    {result?.loading&&<p className="empty-state" role="status">正在查询实验记录…</p>}
    {result?.error&&<p role="status" className="warning">实验查询：{result.error}。请核对实验 ID 与当前运行模式。</p>}
    {value?<>
      <section><div className="section-title"><h3>实验概况</h3><span className="small-tag">{label(value.status)}</span></div><h4 className="trial-name">{value.trial_id}</h4><p className="trial-source">来源：{label(value.source)} · 状态：{label(value.status)}</p><div className="experiment-facts"><div><span>开始时间</span><b>{localTime(value.started_at)}</b></div><div><span>结束时间</span><b>{value.ended_at?localTime(value.ended_at):'尚无结束时间'}</b></div><div><span>证据引用</span><b>{value.asset_refs.length} 项</b></div></div><p className="muted">运行记录和检查点用于追溯，不等于算法评估已完成。</p></section>
      <div className="experiment-layout"><section><div className="section-title"><h3>证据清单</h3><span className="small-tag">后端原始引用</span></div>{value.asset_refs.length?<ol className="asset-list">{value.asset_refs.map((ref,index)=><li key={`${index}:${ref}`}><span className="asset-number">{String(index+1).padStart(2,'0')}</span><div><b>实验资产引用</b><code>{ref.split(/[\\/]/).pop()}</code><details><summary>完整引用路径</summary><code>{ref}</code></details></div></li>)}</ol>:<p className="empty-state">暂无证据引用。服务发布检查点后可重新查询。</p>}<button className="export-button" onClick={()=>onDownload(value)}>导出实验记录</button></section>
      <section><div className="section-title"><h3>算法对照与评估</h3><span className="small-tag">待提供结果</span></div><p className="muted">当前接口未提供 C0–C3 的评估指标，暂不展示准确率或提升幅度。</p><ul className="comparison-plan"><li><b>C0</b><span>水流阈值</span></li><li><b>C1</b><span>即时多源规则</span></li><li><b>C2</b><span>时序 / 上下文规则</span></li><li><b>C3</b><span>轻量 ML 对照</span></li></ul><p className="muted">后续结果需附数据来源、样本规模、trial 划分、模型版本与限制说明。</p></section></div>
      <section className="raw-experiment"><details><summary>查看原始实验记录</summary><pre>{JSON.stringify(value,null,2)}</pre></details></section>
    </>:!result?<section className="detail-placeholder"><span className="placeholder-symbol" aria-hidden="true">⌕</span><h3>查询一个实验，查看运行证据</h3><p>可以使用上方示例填入 ID，再点击查询。</p></section>:null}
  </>
}
