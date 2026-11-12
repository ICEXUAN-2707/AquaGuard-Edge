// Complete before the five-second poll interval so a stalled endpoint cannot
// leave an old snapshot visible indefinitely. ACK retries keep their intent.
export async function requestJSON(path, token, options={}) {
  const controller=new AbortController()
  const parent=options.signal
  const cancel=()=>controller.abort()
  if(parent?.aborted)cancel()
  else parent?.addEventListener('abort',cancel,{once:true})
  let timedOut=false
  const timer=setTimeout(()=>{timedOut=true;controller.abort()},4000)
  try {
    const response=await fetch(path,{...options,signal:controller.signal,headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json',...options.headers}})
    const body=await response.json()
    if(!response.ok){const error=new Error(body.code||`HTTP ${response.status}`);error.status=response.status;error.body=body;throw error}
    return body
  } catch(error) {
    if(timedOut)throw new Error('请求超时，请检查本地服务后重试')
    throw error
  } finally {
    clearTimeout(timer)
    parent?.removeEventListener('abort',cancel)
  }
}
