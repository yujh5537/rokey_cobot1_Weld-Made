import { useEffect, useReducer, useState } from 'react'
import Scene from './Scene'
import './App.css'

const labels = { IDLE: '대기', TARE: '기준값 측정', TOP_SEARCH: '윗면 탐색', EDGE_SEARCH: '모서리 탐색', GEOMETRY: '형상 생성', COMPLETED: '완료', DONE: '완료', ERROR: '오류', STOPPING: '중지 진행', STOPPED: '중단', HOMING: '안전복귀 진행', RESUMING: '재시작 진행' }
const commandLabels = { pending: '접수 대기', accepted: '접수됨 · 실행 완료 대기', rejected: '거절', completed: '완료', failed: '실패', unknown: '미확정 · 상태 확인 필요' }
const initial = { online: false, mqtt: false, state: null, sample: null, points: [], trail: [], logs: [], commands: {}, lastReceived: null }
function reduce(state, event) {
  const p = event.payload
  if (event.topic === 'web/snapshot') {
    let next = { ...state, online: true, mqtt: p.mqtt_connected }
    for (const entry of p.latest) next = reduce(next, entry)
    for (const command of p.commands) next = reduce(next, { topic: 'web/command', payload: command })
    return next
  }
  if (event.topic === 'web/offline') return { ...state, online: false, mqtt: false }
  if (event.topic === 'web/connection') return { ...state, mqtt: p.mqtt_connected }
  if (event.topic === 'web/command') {
    // A late HTTP 202 response must not overwrite a faster MQTT ACK/result.
    if (p.status === 'pending' && state.commands[p.request_id]) return state
    return { ...state, commands: { ...state.commands, [p.request_id]: p } }
  }
  if (event.topic === 'scan/state') {
    const changed = state.state?.scan_id && state.state.scan_id !== p.scan_id
    return { ...state, state: p, lastReceived: event.received_at_ms,
      points: changed ? [] : state.points, trail: changed ? [] : state.trail }
  }
  if (event.topic === 'robot/sample') {
    const trail = p.valid ? [...state.trail.filter(v => v.frame_id === p.frame_id), { ...p.pose, frame_id: p.frame_id }].slice(-1000) : state.trail
    return { ...state, sample: p, trail }
  }
  if (event.topic === 'contact/event') {
    if (state.points.some(v => v.scan_id === p.scan_id && v.event_id === p.event_id)) return state
    return { ...state, points: [...state.points, p].slice(-200) }
  }
  if (event.topic === 'scan/log') return { ...state, logs: [...state.logs, p].sort((a,b) => a.stamp_ms-b.stamp_ms).slice(-200) }
  return state
}

export default function App() {
  const [data, dispatch] = useReducer(reduce, initial)
  const [error, setError] = useState('')
  const [sending, setSending] = useState({})
  const [clock, setClock] = useState(Date.now)
  useEffect(() => {
    let socket, retry, stopped = false
    function connect() {
      socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/live`)
      socket.onmessage = e => { try { dispatch(JSON.parse(e.data)) } catch { setError('수신 메시지를 해석할 수 없습니다.') } }
      socket.onclose = () => { dispatch({ topic: 'web/offline' }); if (!stopped) retry = setTimeout(connect, 1500) }
      socket.onerror = () => socket.close()
    }
    connect()
    const timer = setInterval(() => setClock(Date.now()), 1000)
    return () => { stopped = true; clearTimeout(retry); clearInterval(timer); socket?.close() }
  }, [])

  async function send(action) {
    setError(''); setSending(v => ({ ...v, [action]: true }))
    try {
      const response = await fetch(`/api/scan/${action}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scan_id: action === 'resume' ? data.state?.scan_id ?? '' : '' }) })
      const payload = await response.json()
      if (!response.ok) throw new Error(JSON.stringify(payload.detail))
      dispatch({ topic: 'web/command', payload })
    } catch (e) { setError(`명령 전송 결과 확인 필요: ${e.message}. 자동 재전송하지 않습니다.`) }
    finally { setSending(v => ({ ...v, [action]: false })) }
  }
  const state = data.state
  const sample = data.sample
  const pose = sample?.valid ? sample.pose : null
  return <main>
    <header><p>WELD-MADE / CONTACT SCAN</p><h1>접촉 탐색 관제</h1><p>외곽 엣지·경로 후보 생성 시스템</p></header>
    <section className="status-panel" aria-live="polite">
      <strong>{state ? labels[state.phase] ?? state.phase : '상태 수신 대기'}</strong>
      <span>{state?.direction ?? '—'} · {state?.progress ?? '—'} / {state?.progress_total ?? 4}</span>
      <span>화면 {data.online ? '연결' : '단절'} / MQTT {data.mqtt ? '연결' : '단절'}</span>
      <small>상태 취득 후 {state ? `${Math.max(0, (clock-state.stamp_ms)/1000).toFixed(0)}초` : '—'} · 연결 전 수신값은 현재 상태를 보장하지 않습니다.</small>
    </section>
    <section className="control-panel">
      {[['start','작업 시작'],['stop','작업 중지'],['home','안전복귀'],['resume','재시작']].map(([action,label]) => <button key={action} className={action} disabled={!data.online || !data.mqtt || sending[action]} onClick={() => send(action)}>{label}</button>)}
    </section>
    {error && <p role="alert" className="error">{error}</p>}
    <div className="workspace"><section className="scene-panel"><h2>팁 위치 · 궤적 · 접촉점</h2>
      <Scene sample={sample} trail={data.trail} points={data.points} />
      <p>좌표계: {sample?.frame_id ?? '미수신'} / mm · 파랑: 궤적 · 주황: 접촉점</p>
      <small>작업대는 표시용 기준 평면입니다. 실제 작업대 위치는 T03 좌표 확정 후 반영합니다.</small>
    </section><aside><h2>현재 TCP</h2>{['x','y','z'].map(axis => <p key={axis}>{axis.toUpperCase()} <strong>{Number.isFinite(pose?.[`${axis}_mm`]) ? pose[`${axis}_mm`].toFixed(2) : '—'}</strong> mm</p>)}
      <p>샘플 시각: {sample ? new Date(sample.pose_stamp_ms).toLocaleTimeString() : '—'}</p>
      <h2>명령 처리</h2><p>접수와 실행 완료를 별도로 표시합니다.</p>
      {Object.values(data.commands).slice(-12).reverse().map(c => <article key={c.request_id}><strong>{c.action} · {commandLabels[c.status]}</strong><small>{c.request_id}</small>{(c.result?.reason || c.ack?.reason) && <p>{c.result?.reason ?? c.ack?.reason}</p>}</article>)}
    </aside></div>
    <section className="log-panel"><h2>시간순 로그</h2>{!data.logs.length && <p>로그 수신 대기</p>}{data.logs.map((l,i) => <p key={`${l.stamp_ms}-${i}`}><time>{new Date(l.stamp_ms).toLocaleTimeString()}</time> [{l.level}] {l.phase} · {l.message}</p>)}</section>
  </main>
}
