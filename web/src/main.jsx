import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'

function App() {
  const [health, setHealth] = useState({ state: 'checking' })

  useEffect(() => {
    const controller = new AbortController()
    fetch('/health', { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const body = await response.json()
        if (body.status !== 'ok') throw new Error('Unexpected health response')
        setHealth({ state: 'connected', deviceId: body.device_id })
      })
      .catch((error) => {
        if (error.name !== 'AbortError') setHealth({ state: 'unavailable' })
      })
    return () => controller.abort()
  }, [])

  return (
    <main className="shell">
      <div className="brand"><span className="brand-mark">◉</span> 水知安 <span className="brand-en">AQUAGUARD EDGE</span></div>
      <section className="card">
        <p className="eyebrow">I-001 · 本地运行基线</p>
        <h1>服务连接状态</h1>
        <p className="lead">此页面仅验证浏览器与本地 API 的连接。传感数据、事件和实验视图会在相应模块验收后接入。</p>
        <div className={`status status-${health.state}`} role="status">
          <span className="status-dot" aria-hidden="true" />
          {health.state === 'checking' && '正在检查本地 API…'}
          {health.state === 'connected' && `已连接 · 设备 ${health.deviceId}`}
          {health.state === 'unavailable' && '本地 API 未连接，请先启动 python -m edge'}
        </div>
      </section>
      <p className="footer">当前仅包含健康检查 · 不代表传感或告警功能已验收</p>
    </main>
  )
}

createRoot(document.getElementById('root')).render(<App />)
