import React from 'react'

export function WorkspaceNavigation({tab,onTab}) {
  return <aside className="workspace-sidebar">
    <div className="brand"><span className="brand-mark" aria-hidden="true">≈</span><div><h1>水知安 <span>AquaGuard Edge</span></h1><p>用水异常监测工作台</p></div></div>
    <div className="workspace-project"><b>水知安项目</b><span>EDGE</span></div>
    <p className="navigation-caption">监测工作区</p>
    <nav aria-label="工作台页面">{['实时总览','数据可视化','事件确认','实验诊断'].map((name,index)=><button key={name} aria-label={name} aria-current={tab===name?'page':undefined} onClick={()=>onTab(name)}><span className="nav-index" aria-hidden="true">0{index+1}</span>{name}</button>)}</nav>
    <div className="sidebar-note"><span className="connection-dot"/>本地运行 · 证据可追溯<p>实时状态、人工确认与实验记录，来自同一业务系统。</p></div>
  </aside>
}

export function DataPath() {
  return <div className="data-path" aria-label="系统数据路径"><span>系统数据路径</span><ol>{['感知','分析','告警','用户确认','云端同步'].map((name,index)=><li key={name}><span>{String(index+1).padStart(2,'0')}</span>{name}</li>)}</ol><small>各环节实际状态见下方数据</small></div>
}
