import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { buildM0609Model, disposeObject3D } from './robotModel.js'
import { parseRobotJoints } from './robotJoints.js'
import { createWeldEffect } from './weldEffect.js'
import { appendWeldSample, applyWeldResult, updateWeldState } from './weldLive.js'
import { TABLE_HEIGHT_MM, basePointWorldMm, fixturePointWorldMm, fixtureRelativeToBaseMm, robotBaseWorldMm, threePointWorldM } from './sceneFrames.js'
import './App.css'

function getPhaseLabel(
  phase,
  progress,
  progressTotal
) {
  switch (phase) {
    case 'IDLE':
      return '대기'

    case 'PREPARING':
      return '시작 준비'

    case 'TOP_SEARCH':
      return '윗면 탐색'

    case 'EDGE_SEARCH':
      return `모서리 탐색 ${progress}/${progressTotal}`

    case 'GEOMETRY':
      return '형상 생성'

    case 'DONE':
      return '완료'

    case 'ERROR':
      return '오류'

    case 'STOPPING':
      return '중지 진행'

    case 'STOPPED':
      return '중단됨'

    case 'HOMING':
      return '홈 복귀 진행'

    case 'RESUMING':
      return '재시작 진행'

    default:
      return phase
  }
}

function getCommandLabel(commandTopic) {
  switch (commandTopic) {
    case 'cmd/scan/start':
      return '시작'

    case 'cmd/scan/stop':
      return '중지'

    case 'cmd/scan/home':
      return '안전복귀'

    case 'cmd/scan/resume':
      return '재시작'

    case 'cmd/safety/reset':
      return '안전 해제'

    default:
      return commandTopic ?? '-'
  }
}

function formatLogTime(timestampMs) {
  if (!timestampMs) {
    return '-'
  }

  return new Date(timestampMs).toLocaleTimeString()
}

function formatNumber(value) {
  return Number.isFinite(value)
    ? value.toFixed(2)
    : '-'
}

const DISPLAY_SCALE = 0.01
function toThreePosition(
  xMm,
  yMm,
  zMm
) {
  return new THREE.Vector3(
    xMm * DISPLAY_SCALE,
    zMm * DISPLAY_SCALE,
    -yMm * DISPLAY_SCALE
  )
}

function getFixtureOriginWorldMm() {
  const raw =
    import.meta.env
      .VITE_FIXTURE_ORIGIN_WORLD_MM ?? import.meta.env.VITE_BASE_TO_FIXTURE_MM ?? ''

  const values = raw
    .split(',')
    .map((value) =>
      Number(value.trim())
    )

  if (
    values.length !== 3 ||
    values.some(
      (value) =>
        !Number.isFinite(value)
    )
  ) {
    return null
  }

  return {
    x: values[0],
    y: values[1],
    z: values[2],
  }
}

const FIXTURE_ORIGIN_WORLD_MM = getFixtureOriginWorldMm()

// 실물 부재는 작업대에서 약 4 mm 떠 있다. 측정된 윗면은 그대로 두고
// 화면의 아랫면과 그에 연결된 모서리만 지지 높이에 맞춘다.
const WORKPIECE_CLEARANCE_MM = 4

function workpieceDisplayZ(point, result) {
  if (!FIXTURE_ORIGIN_WORLD_MM || !Number.isFinite(point?.z_mm) ||
      !Array.isArray(result?.vertices) || result.vertices.length !== 8) {
    return point?.z_mm
  }
  const isBottom = result.vertices.slice(4).some((bottom) =>
    bottom && Math.abs(bottom.x_mm - point.x_mm) < 1e-6 &&
    Math.abs(bottom.y_mm - point.y_mm) < 1e-6 &&
    Math.abs(bottom.z_mm - point.z_mm) < 1e-6)
  return isBottom
    ? TABLE_ORIGIN_MM.z + WORKPIECE_CLEARANCE_MM - FIXTURE_ORIGIN_WORLD_MM.z
    : point.z_mm
}

// 작업대 상판의 화면/world 좌표. ROS base_link는 별도 원점이다.
const DEFAULT_TABLE_ORIGIN_MM = {
  x: 420.255,
  y: -156.675,
  z: 95.006,
}

function getTableOriginMm() {
  const raw =
    import.meta.env
      .VITE_TABLE_ORIGIN_MM ?? ''

  if (!raw.trim()) {
    return DEFAULT_TABLE_ORIGIN_MM
  }

  const values = raw
    .split(',')
    .map((value) =>
      Number(value.trim())
    )

  if (
    values.length !== 3 ||
    values.some(
      (value) =>
        !Number.isFinite(value)
    )
  ) {
    return DEFAULT_TABLE_ORIGIN_MM
  }

  return {
    x: values[0],
    y: values[1],
    z: values[2],
  }
}

const TABLE_ORIGIN_MM = getTableOriginMm()
const ROBOT_BASE_WORLD_MM = robotBaseWorldMm(TABLE_ORIGIN_MM)

function toThreeBasePosition(xMm, yMm, zMm) {
  const world = basePointWorldMm({ x: xMm, y: yMm, z: zMm }, ROBOT_BASE_WORLD_MM)
  return toThreePosition(world.x, world.y, world.z)
}

function formatScanLogMessage(payload) {
  const parts = []

  const level =
    payload.level ?? 'INFO'

  const phase =
    payload.phase ?? 'UNKNOWN'

  parts.push(`[${level}]`)
  parts.push(`[${phase}]`)

  if (
    payload.direction &&
    payload.direction !== 'NONE'
  ) {
    parts.push(
      `[${payload.direction}]`
    )
  }

  if (payload.code_name) {
    parts.push(
      `[${payload.code_name}:${payload.code ?? 0}]`
    )
  }

  parts.push(
    payload.message ?? 'scan log'
  )

  if (
    payload.pose_valid === true &&
    payload.pose
  ) {
    const x =
      payload.pose.x_mm

    const y =
      payload.pose.y_mm

    const z =
      payload.pose.z_mm

    parts.push(
      `좌표 X ${formatNumber(x)} mm / ` +
      `Y ${formatNumber(y)} mm / ` +
      `Z ${formatNumber(z)} mm`
    )

    if (payload.frame_id) {
      parts.push(
        `frame=${payload.frame_id}`
      )
    }
  }

  return parts.join(' ')
}

function App() {
  const weldRef = useRef(null)
  const tipSampleRef = useRef(null)
  const appliedJointsAtRef = useRef(null)
  const renderedScanRef = useRef(null)
  const scanResultRef = useRef(null)
  const [weld, setWeld] = useState(null)
  const [weldError, setWeldError] = useState('')
  const [weldPending, setWeldPending] = useState(false)
  async function commandWeld(command, line) {
    setWeldPending(true)
    setWeldError('')
    try {
      const payload = command === 'start'
        ? { scan_id: scanResult?.scan_id, start_line: line, end_line: line }
        : {}
      if (command === 'start' && (!Number.isInteger(line) || line < 0 || line > 7)) throw new Error('L0~L7 중 용접할 선을 선택하세요')
      if (command === 'start' && !payload.scan_id) throw new Error('성공한 스캔 결과가 필요합니다')
      if (command === 'start' && fixtureFrameMismatch) throw new Error('부재·로봇 좌표계가 다릅니다')
      const response = await fetch(`/commands/weld/${command}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ payload }),
      })
      const result = await response.json()
      if (!response.ok) throw new Error(result.detail || `HTTP ${response.status}`)
      addLog(`용접 ${command === 'start' ? `L${line} 시작` : command} 요청: ${result.request_id}`)
    } catch (error) { setWeldError(error.message) }
    finally { setWeldPending(false) }
  }
  // Three.js canvas
  const canvasRef = useRef(null)

  // 실제 M0609 모델과 joint_1~joint_6 회전 Group.
  const robotModelRef = useRef(null)
  const robotJointRefs = useRef({})

  // Three.js에서 현재 TCP 팁 Mesh를 참조한다.
  const tipMeshRef = useRef(null)

  // Three.js에서 TCP 이동 궤적 Line을 참조한다.
  const trajectoryLineRef = useRef(null)

  // Three.js 접촉점들을 담는 Group
  const contactGroupRef = useRef(null)

  // Three.js scan/result 직육면체를 담는 Group
  const workpieceGroupRef = useRef(null)

  // Three.js 스캔 결과의 일반 모서리를 담는 Group
  const edgeGroupRef = useRef(null)

  // Three.js 외곽 엣지·경로 후보를 담는 Group
  const pathCandidateGroupRef = useRef(null)

  // 화면에 표시할 현재 상태
  const [phase, setPhase] = useState('IDLE')
  const [direction, setDirection] = useState('-')
  const [progress, setProgress] = useState(0)
  const [progressTotal, setProgressTotal] = useState(4)

  // 현재 진행 중인 scan ID
  const [scanId, setScanId] = useState(null)

  const [commandStatus, setCommandStatus] =
    useState('-')

  const [lastRequestId, setLastRequestId] =
    useState(null)

  // request_id별 명령 상태 이력
  const [commandHistory, setCommandHistory] = useState([])

  // FastAPI WebSocket 연결 상태
  const [wsConnected, setWsConnected] = useState(false)

  // M0609 joint state. /dsr01/joint_states -> MQTT robot/joints.
  const [jointPositions, setJointPositions] = useState({})
  const [jointStatus, setJointStatus] = useState('수신 대기')
  const [robotModelStatus, setRobotModelStatus] = useState('LOADING')
  // safety/status 수신 여부와 래치 상태.
  // 상태를 아직 모를 때는 안전 해제 버튼을 막지 않는다.
  const [safetyStatusSeen, setSafetyStatusSeen] = useState(false)
  const [safetyLatched, setSafetyLatched] = useState(false)

  // 현재 로봇 TCP 팁 위치
  // robot/sample의 pose는 base_link 기준, 단위는 mm
  const [tipPose, setTipPose] = useState(null)

  // robot/sample로 받은 TCP 이동 기록
  const [tipTrajectory, setTipTrajectory] = useState([])

  // contact/event로 받은 접촉점 목록
  const [contactPoints, setContactPoints] = useState([])

  // scan/result로 받은 최종 형상 결과
  const [scanResult, setScanResult] = useState(null)
  useEffect(() => {
    const url = import.meta.env.VITE_SIM_FIXTURE_URL
    if (!url) return
    const controller = new AbortController()
    fetch(url, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`fixture HTTP ${response.status}`)
        return response.json()
      })
      .then((fixture) => setScanResult(fixture))
      .catch((error) => {
        if (error.name !== 'AbortError') console.error('fixture load:', error)
      })
    return () => controller.abort()
  }, [])

  // 시간순 로그
  const [logs, setLogs] = useState([])


  // =========================
  // 로그 추가 함수
  // =========================
  function addLog(
    message,
    timestampMs = Date.now()
  ) {
    const newLog = {
      timestampMs,
      message,
    }

    setLogs((prevLogs) => {
      const nextLogs = [
        ...prevLogs,
        newLog,
      ]

      nextLogs.sort(
        (a, b) =>
          a.timestampMs - b.timestampMs
      )

      return nextLogs.slice(-100)
    })
  }


  // =========================
  // 명령 상태 이력 갱신 함수
  // =========================
  function updateCommandHistory(payload) {
    const requestId =
      payload.request_id

    if (!requestId) {
      return
    }

    setCommandHistory((prevHistory) => {
      const existingIndex =
        prevHistory.findIndex(
          (command) =>
            command.requestId === requestId
        )

      const newCommand = {
        requestId,
        commandTopic:
          payload.command_topic ?? '-',
        status:
          payload.status ?? 'UNKNOWN',
        createdAtMs:
          payload.created_at_ms ?? null,
        updatedAtMs:
          payload.updated_at_ms ?? Date.now(),
        ack:
          payload.ack ?? null,
        result:
          payload.result ?? null,
      }

      // 처음 보는 request_id
      if (existingIndex === -1) {
        return [
          ...prevHistory,
          newCommand,
        ]
      }

      // 이미 있는 request_id면
      // 기존 항목만 최신 상태로 교체한다.
      return prevHistory.map(
        (command, index) =>
          index === existingIndex
            ? newCommand
            : command
      )
    })
  }


  // =========================
  // 버튼 함수
  // =========================

  async function sendScanCommand(action) {
    const requestBody = {
      payload: {},
    }

    // resume 명령은 기존 scan_id를 같이 보낸다.
    if (action === 'resume') {
      requestBody.scan_id = scanId ?? ''
    }

    try {
      const response = await fetch(
        `/commands/scan/${action}`,
        {
          method: 'POST',

          headers: {
            'Content-Type': 'application/json',
          },

          body: JSON.stringify(
            requestBody
          ),
        }
      )

      const result =
        await response.json()

      if (!response.ok) {
        throw new Error(
          `HTTP ${response.status}`
        )
      }

      console.log(
        '[COMMAND]',
        action,
        result
      )

      addLog(
        `${action} 명령 전송: ${result.status}`
      )

    } catch (error) {
      console.error(
        '[COMMAND] error:',
        error
      )

      addLog(
        `${action} 명령 전송 실패`
      )
    }
  }


  function handleStart() {
    sendScanCommand('start')
  }


  function handleStop() {
    sendScanCommand('stop')
  }


  function handleHome() {
    if (weldRef.current?.run_id && ['STOPPED', 'ERROR'].includes(weldRef.current.phase)) {
      commandWeld('home')
    } else {
      sendScanCommand('home')
    }
  }


  function handleResume() {
    sendScanCommand('resume')
  }


  async function handleSafetyReset() {
    // 래치가 아님을 확인한 경우에만 요청을 막는다.
    // 아직 safety/status를 못 받은 상태에서는 reset 요청을 허용한다.
    if (safetyStatusSeen && !safetyLatched) {
      return
    }

    try {
      const response = await fetch(
        '/commands/safety/reset',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ payload: {} }),
        }
      )

      const result = await response.json()

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      console.log('[COMMAND]', 'safety/reset', result)
      addLog(`안전 해제 명령 전송: ${result.status}`)
    } catch (error) {
      console.error('[COMMAND] safety/reset error:', error)
      addLog('안전 해제 명령 전송 실패')
    }
  }


  // =========================
  // FastAPI WebSocket
  // =========================

  useEffect(() => {
    const wsProtocol =
      window.location.protocol === 'https:'
        ? 'wss'
        : 'ws'

    const wsUrl =
      `${wsProtocol}://${window.location.host}/ws`

    const websocket = new WebSocket(wsUrl)
    let jointTimeout
    let displayedScanId = null


    // WebSocket 연결 성공
    websocket.onopen = () => {
      console.log('[WS] connected')

      setWsConnected(true)
      addLog('FastAPI WebSocket 연결')
    }


    // FastAPI에서 메시지 수신
    websocket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)

        console.log('[WS] message:', message)

        const { topic, payload } = message

        if (topic === 'weld/state') {
          const next = updateWeldState(weldRef.current, payload, scanResultRef.current,
            FIXTURE_ORIGIN_WORLD_MM, TABLE_ORIGIN_MM.z + WORKPIECE_CLEARANCE_MM)
          weldRef.current = next
          setWeld({ phase: next.phase, line: next.line,
            line_total: next.line_total, active: next.active, scan_id: next.scan_id })
        }
        if (topic === 'weld/result') {
          weldRef.current = applyWeldResult(weldRef.current, payload, scanResultRef.current,
            FIXTURE_ORIGIN_WORLD_MM, TABLE_ORIGIN_MM.z + WORKPIECE_CLEARANCE_MM)
        }
        if (topic === 'weld/command_result' && payload.success === false) {
          setWeldError(`${payload.reason ?? 'ERROR'}: ${payload.detail ?? ''}`)
        }

        // scan/state
        if (topic === 'scan/state') {
          const nextPhase =
            payload.phase ?? 'UNKNOWN'

          const nextScanId =
            payload.scan_id ?? null


          if (nextScanId && nextScanId !== displayedScanId) {
            displayedScanId = nextScanId
            setContactPoints([])
            setTipTrajectory([])
            setScanResult(null)
          }

          setScanResult((previousResult) => {
            const scanIdChanged =
              previousResult?.scan_id &&
              nextScanId &&
              previousResult.scan_id !== nextScanId

            if (
              nextPhase === 'PREPARING' ||
              scanIdChanged
            ) {
              return null
            }

            return previousResult
          })

          setPhase(nextPhase)

          setDirection(
            payload.direction ?? '-'
          )

          setProgress(
            payload.progress ?? 0
          )

          setProgressTotal(
            payload.progress_total ?? 4
          )

          setScanId(nextScanId)
        }

        // Apply only complete, finite J1~J6 snapshots, mapped by name.
        if (topic === 'robot/joints') {
          const nextPositions = parseRobotJoints(payload)
          if (nextPositions) {
            setJointPositions(nextPositions)
            setJointStatus('실시간 수신 중')
            window.clearTimeout(jointTimeout)
            jointTimeout = window.setTimeout(() => {
              setJointStatus('수신 지연 — 마지막 자세 표시')
            }, 3000)
          }
        }

        // RG2는 탐침 고정 파지용이므로 웹에서는 항상 닫힌 자세로 표시한다.
        // robot/gripper_joints가 들어와도 시각 자세를 덮어쓰지 않는다.

        // robot/sample
        if (
          topic === 'robot/sample' &&
          payload.valid === true &&
          payload.pose
        ) {
          const newTipPose = {
            frameId: payload.frame_id,
            x: payload.pose.x_mm,
            y: payload.pose.y_mm,
            z: payload.pose.z_mm,
          }

          // 샘플의 motion ID와 실제 화면 탐침 위치를 렌더 시점에 함께 확인한다.
          setTipPose(newTipPose)
          tipSampleRef.current = {
            ...newTipPose,
            motionId: payload.motion_id,
            operation: payload.operation,
            receivedAt: performance.now(),
          }

          // TCP 이동 궤적
          setTipTrajectory((prevTrajectory) => {
            const nextTrajectory = [
              ...prevTrajectory,
              newTipPose,
            ]

            // 너무 오래 실행해도 브라우저 메모리가
            // 계속 늘어나지 않도록 최근 1000점만 유지한다.
            return nextTrajectory.slice(-1000)
          })
        }

        // contact/event
        if (
          topic === 'contact/event' &&
          payload.pose &&
          (!payload.scan_id || !displayedScanId || payload.scan_id === displayedScanId)
        ) {
          // contact/event pose는 판정 순간의 탐침 TCP 좌표(base_link)다.
          // scan/result도 이 접촉점들로 계산되므로 노란 접촉점은 이 원본 좌표를 쓴다.
          // 이벤트 수신 시점의 현재 로봇 자세를 다시 읽으면 통신 지연만큼 어긋난다.
          const newContactPoint = {
            eventId: payload.event_id,
            frameId: payload.frame_id,
            x: payload.pose.x_mm,
            y: payload.pose.y_mm,
            z: payload.pose.z_mm,
          }

          setContactPoints((prevPoints) => {
            // 같은 event_id가 다시 들어오면 중복 저장하지 않는다.
            const alreadyExists =
              prevPoints.some(
                (point) =>
                  point.eventId === newContactPoint.eventId
              )

            if (alreadyExists) {
              return prevPoints
            }

            return [
              ...prevPoints,
              newContactPoint,
            ]
          })
        }

        // scan/log
        if (topic === 'scan/log') {
          addLog(
            formatScanLogMessage(payload),
            payload.stamp_ms
          )
        }

        // scan/result
        if (topic === 'scan/result') {
          scanResultRef.current = payload
          setScanResult(payload)

          addLog(
            payload.success === true
              ? '스캔 형상 결과 수신'
              : `스캔 결과 실패: ${payload.reason ?? 'UNKNOWN'}`,
            payload.stamp_ms
          )
        }

        // safety/status
        if (topic === 'safety/status') {
          setSafetyStatusSeen(true)
          setSafetyLatched(payload.latched === true)
        }

        // command/status
        if (topic === 'command/status') {
          setCommandStatus(
            payload.status ?? 'UNKNOWN'
          )

          setLastRequestId(
            payload.request_id ?? null
          )

          updateCommandHistory(payload)
        }

      } catch (error) {
        console.error(
          '[WS] invalid message:',
          error
        )
      }
    }


    // WebSocket 연결 종료
    websocket.onclose = () => {
      console.log('[WS] disconnected')

      setWsConnected(false)
      window.clearTimeout(jointTimeout)
      setJointStatus('연결 끊김 — 마지막 자세 표시')
      addLog('FastAPI WebSocket 연결 종료')
    }


    // WebSocket 오류
    websocket.onerror = (error) => {
      console.error(
        '[WS] error:',
        error
      )
    }


    // React 컴포넌트 종료 시 연결 정리
    return () => {
      window.clearTimeout(jointTimeout)
      websocket.onopen = null
      websocket.onmessage = null
      websocket.onclose = null
      websocket.onerror = null
      websocket.close()
    }
  }, [])


  // =========================
  // Three.js 화면
  // =========================

  useEffect(() => {
    let disposed = false
    // 1. 3D 공간
    const scene = new THREE.Scene()

    // 2. 카메라
    const camera = new THREE.PerspectiveCamera(
      60,
      900 / 500,
      0.1,
      1000
    )

    camera.position.set(4, 3, 5)
    camera.lookAt(0, 0, 0)


    // 3. Renderer
    const renderer = new THREE.WebGLRenderer({
      canvas: canvasRef.current,
      antialias: true,
    })

    const resizeRenderer = () => {
      const canvas = canvasRef.current
      if (!canvas) return

      const width = Math.max(canvas.clientWidth, 320)
      const height = Math.max(canvas.clientHeight, 360)
      const pixelRatio = Math.min(window.devicePixelRatio, 2)

      renderer.setPixelRatio(pixelRatio)
      renderer.setSize(width, height, false)
      camera.aspect = width / height
      camera.updateProjectionMatrix()
    }

    resizeRenderer()

    const resizeObserver = new ResizeObserver(resizeRenderer)
    resizeObserver.observe(canvasRef.current)


    // 4. 조명
    const ambientLight = new THREE.AmbientLight(
      0xffffff,
      1
    )

    scene.add(ambientLight)


    const directionalLight =
      new THREE.DirectionalLight(
        0xffffff,
        2
      )

    directionalLight.position.set(3, 5, 4)

    scene.add(directionalLight)


    // 5. 작업대
    // 웹 3D 기준:
    // - 작업대 상판 = workpiece_fixture Z = 0
    // - 작업대 바닥 = 상판보다 94 mm 아래
    // - 화면 축척 = 100 mm -> Three.js 1 unit
    const worktable = new THREE.Group()

    const tableWidth = 4.0
    const tableDepth = 3.0
    const tableHeight = TABLE_HEIGHT_MM * DISPLAY_SCALE
    const topThickness = 0.12
    const floorY = -tableHeight

    // 장면은 화면/world 기준이다. table origin은 상판 좌표다.
    // 작업대 형상과 부재 위치는 표준 fixture 값을 유지한다.
    const tableOriginThree =
      toThreePosition(
        TABLE_ORIGIN_MM.x,
        TABLE_ORIGIN_MM.y,
        TABLE_ORIGIN_MM.z
      )

    worktable.position.copy(
      tableOriginThree
    )

    const topMaterial =
      new THREE.MeshStandardMaterial({
        color: 0x4f5963,
        metalness: 0.55,
        roughness: 0.38,
      })

    const frameMaterial =
      new THREE.MeshStandardMaterial({
        color: 0xaab2b9,
        metalness: 0.7,
        roughness: 0.32,
      })

    const footMaterial =
      new THREE.MeshStandardMaterial({
        color: 0x30363b,
        metalness: 0.25,
        roughness: 0.55,
      })

    // 상판 윗면을 정확히 Y=0에 둔다.
    const tableTop =
      new THREE.Mesh(
        new THREE.BoxGeometry(
          tableWidth,
          topThickness,
          tableDepth
        ),
        topMaterial
      )

    tableTop.position.y =
      -topThickness / 2

    worktable.add(tableTop)

    const tableTopEdges =
      new THREE.LineSegments(
        new THREE.EdgesGeometry(
          tableTop.geometry
        ),
        new THREE.LineBasicMaterial({
          color: 0xd9dde1,
        })
      )

    tableTopEdges.position.copy(
      tableTop.position
    )

    worktable.add(tableTopEdges)

    // 상판 fixture hole은 시각화용이다.
    const holeGeometry =
      new THREE.CircleGeometry(
        0.035,
        16
      )

    const holeMaterial =
      new THREE.MeshBasicMaterial({
        color: 0x20262b,
        side: THREE.DoubleSide,
      })

    for (
      let x = -1.5;
      x <= 1.5;
      x += 0.5
    ) {
      for (
        let z = -1.0;
        z <= 1.0;
        z += 0.5
      ) {
        const hole =
          new THREE.Mesh(
            holeGeometry,
            holeMaterial
          )

        hole.rotation.x =
          -Math.PI / 2

        hole.position.set(
          x,
          0.002,
          z
        )

        worktable.add(hole)
      }
    }

    // 실제 높이 94 mm를 반영한 프레임/다리.
    const legSize = 0.14

    const legHeight =
      tableHeight -
      topThickness

    const legCenterY =
      -topThickness -
      legHeight / 2

    const legPositions = [
      [-1.7, -1.2],
      [1.7, -1.2],
      [-1.7, 1.2],
      [1.7, 1.2],
    ]

    legPositions.forEach(
      ([x, z]) => {
        const leg =
          new THREE.Mesh(
            new THREE.BoxGeometry(
              legSize,
              legHeight,
              legSize
            ),
            frameMaterial
          )

        leg.position.set(
          x,
          legCenterY,
          z
        )

        worktable.add(leg)

        const foot =
          new THREE.Mesh(
            new THREE.CylinderGeometry(
              0.12,
              0.12,
              0.05,
              24
            ),
            footMaterial
          )

        foot.position.set(
          x,
          floorY + 0.025,
          z
        )

        worktable.add(foot)
      }
    )

    // 하부 프레임.
    const railHeight = 0.12
    const railY = floorY + 0.22

    const frontRail =
      new THREE.Mesh(
        new THREE.BoxGeometry(
          3.54,
          railHeight,
          0.12
        ),
        frameMaterial
      )

    frontRail.position.set(
      0,
      railY,
      1.2
    )

    const backRail =
      frontRail.clone()

    backRail.position.z = -1.2

    const leftRail =
      new THREE.Mesh(
        new THREE.BoxGeometry(
          0.12,
          railHeight,
          2.54
        ),
        frameMaterial
      )

    leftRail.position.set(
      -1.7,
      railY,
      0
    )

    const rightRail =
      leftRail.clone()

    rightRail.position.x = 1.7

    worktable.add(
      frontRail,
      backRail,
      leftRail,
      rightRail
    )

    scene.add(worktable)

    // 바닥 격자는 상판보다 94 mm 아래에 있다.
    const floorGrid =
      new THREE.GridHelper(
        8,
        16,
        0x7f8a93,
        0xc4c9ce
      )

    floorGrid.position.set(
      tableOriginThree.x,
      tableOriginThree.y + floorY,
      tableOriginThree.z
    )

    floorGrid.material.transparent =
      true

    floorGrid.material.opacity =
      0.32

    scene.add(floorGrid)


    // 5-1. 실제 M0609 + RG2 + 탐침 모델
    // Doosan 공식 M0609 visual mesh와 RG2 공개 visual mesh를 사용한다.
    const robotModel =
      buildM0609Model()

    // 로봇과 모든 Base 좌표 표시가 같은 화면 원점을 사용한다.
    // 작업대 상판과 scan/result 형상 좌표는 변경하지 않는다.
    robotModel.root.position.copy(
      toThreeBasePosition(0, 0, 0)
    )

    robotModelRef.current =
      robotModel.root

    robotJointRefs.current =
      robotModel.jointRefs

    scene.add(
      robotModel.root
    )

    robotModel.loadPromise
      .then((results) => {
        if (disposed) return
        const rejected =
          results.filter(
            (result) =>
              result.status === 'rejected'
          )

        setRobotModelStatus(
          rejected.length === 0
            ? 'READY'
            : rejected.length === results.length
              ? 'ERROR'
              : 'PARTIAL'
        )

        rejected.forEach(
          (result) =>
            console.error(
              '[3D] robot mesh load failed:',
              result.reason
            )
        )
      })

    // M0609 base_link와 작업대가 한 화면에 들어오게 한다.
    const viewCenter =
      tableOriginThree
        .clone()
        .add(toThreeBasePosition(0, 0, 0))
        .multiplyScalar(0.5)

    // Include the fully extended arm while waiting for the first joint snapshot.
    viewCenter.y = Math.max(viewCenter.y, 4.5)
    camera.position.set(
      viewCenter.x + 10,
      viewCenter.y + 8,
      viewCenter.z + 12
    )

    camera.lookAt(viewCenter)

    // 드래그 회전 / 휠 확대·축소 / 우클릭 이동.
    const controls =
      new OrbitControls(
        camera,
        renderer.domElement
      )

    controls.target.copy(
      viewCenter
    )

    controls.enableDamping = true
    controls.dampingFactor = 0.08
    controls.enablePan = true
    controls.minDistance = 1.5
    controls.maxDistance = 35


    // 6. scan/result 직육면체 부재
    // 고정 BoxGeometry 목업은 제거한다.
    // 최종 형상은 scan/result.vertices 8점으로 동적으로 생성한다.
    const workpieceGroup =
      new THREE.Group()

    scene.add(workpieceGroup)

    workpieceGroupRef.current =
      workpieceGroup


    // 7. XYZ 좌표축
    const axesHelper =
      new THREE.AxesHelper(2)

    axesHelper.position.copy(toThreeBasePosition(0, 0, 0))
    // ROS +Y -> Three -Z, ROS +Z -> Three +Y.
    axesHelper.rotation.x = -Math.PI / 2
    scene.add(axesHelper)

    // 8. 현재 TCP 팁 표시
    const tipGeometry =
      new THREE.SphereGeometry(
        (0.04 / 3) * 2.5,
        24,
        24
      )

    const tipMaterial =
      new THREE.MeshStandardMaterial({
        color: 0xff3333,
      })

    const tipMesh =
      new THREE.Mesh(
        tipGeometry,
        tipMaterial
      )

    // 아직 robot/sample을 받기 전이므로 숨긴다.
    tipMesh.visible = false

    scene.add(tipMesh)

    // 다른 useEffect에서도 이 Mesh를 조작할 수 있도록 보관한다.
    tipMeshRef.current = tipMesh


    // 9. TCP 이동 궤적
    const trajectoryGeometry =
      new THREE.BufferGeometry()

    const trajectoryMaterial =
      new THREE.LineBasicMaterial({
        color: 0x33aaff,
      })

    const trajectoryLine =
      new THREE.Line(
        trajectoryGeometry,
        trajectoryMaterial
      )

    scene.add(trajectoryLine)

    trajectoryLineRef.current = trajectoryLine

    // 10. 접촉점들을 담을 Group
    const contactGroup = new THREE.Group()

    scene.add(contactGroup)

    contactGroupRef.current = contactGroup

    // 11. 스캔 결과의 일반 모서리를 담을 Group
    const edgeGroup = new THREE.Group()

    scene.add(edgeGroup)

    edgeGroupRef.current = edgeGroup

    // 12. 외곽 엣지·경로 후보를 담을 Group
    const pathCandidateGroup = new THREE.Group()

    scene.add(pathCandidateGroup)

    pathCandidateGroupRef.current = pathCandidateGroup

    const modelProbeTip = robotModel.root.getObjectByName('probe_tip')
    const modelTipWorld = new THREE.Vector3()
    const probeShaft = robotModel.root.getObjectByName('probe_shaft')
    const shaftRestPosition = probeShaft?.position.clone()
    const tipRestPosition = modelProbeTip?.position.clone()
    const shaftCenterWorld = new THREE.Vector3()
    const shiftedCenterLocal = new THREE.Vector3()
    const probeShiftLocal = new THREE.Vector3()
    let probeOffsetFixed = false
    const shaftStartWorld = new THREE.Vector3()
    const shaftEndWorld = new THREE.Vector3()
    const shaftHalfLength = (probeShaft?.geometry.parameters.height ?? 0) / 2
    // 작업대·부재·측정 표시는 고정 world 좌표를 유지한다.
    // 관절 모델과 실측 TCP의 수신 시차를 장면 전체 이동으로 보정하지 않는다.
    const measuredScene = new THREE.Group()
    measuredScene.name = 'world_measurements'
    scene.add(measuredScene)
    measuredScene.add(tipMesh, trajectoryLine, contactGroup, workpieceGroup,
      edgeGroup, pathCandidateGroup, worktable, floorGrid, axesHelper)
    const measuredTipWorld = new THREE.Vector3()
    const weldEffect = createWeldEffect(measuredScene)

    // 13. 실시간 렌더링
    let animationFrameId

    function animate() {
      animationFrameId =
        requestAnimationFrame(animate)

      const sample = tipSampleRef.current
      const probeTip = modelProbeTip
      // 빨간 구·궤적·부재는 그대로 두고 봉만 ROS/world Y 방향으로 옮긴다.
      // ROS Y는 Three.js -Z다. 용접 전 한 번 구한 그리퍼 로컬 오프셋을 유지한다.
      const pathPositions = trajectoryLine.geometry.getAttribute('position')
      if (pathPositions?.count > 0) {
        measuredTipWorld.fromBufferAttribute(pathPositions, pathPositions.count - 1)
        tipMesh.position.copy(measuredTipWorld)
      }
      let probeSegment = null
      if (probeTip && probeShaft) {
        probeShaft.position.copy(shaftRestPosition)
        probeTip.position.copy(tipRestPosition)
        robotModel.root.updateMatrixWorld(true)
        if (!probeOffsetFixed && !weldRef.current?.active && pathPositions?.count > 0 &&
            sample && performance.now() - sample.receivedAt < 500 &&
            appliedJointsAtRef.current !== null && performance.now() - appliedJointsAtRef.current < 500) {
          probeShaft.getWorldPosition(shaftCenterWorld)
          shaftCenterWorld.z = measuredTipWorld.z
          shiftedCenterLocal.copy(shaftCenterWorld)
          probeShaft.parent.worldToLocal(shiftedCenterLocal)
          probeShiftLocal.subVectors(shiftedCenterLocal, shaftRestPosition)
          probeOffsetFixed = true
        }
        probeShaft.position.add(probeShiftLocal)
        probeTip.position.add(probeShiftLocal)
        robotModel.root.updateMatrixWorld(true)
        probeTip.getWorldPosition(modelTipWorld)
        // 기울어진 봉의 양 끝을 world 좌표로 보내 모서리와 가장 가까운 지점을 구한다.
        shaftStartWorld.set(0, -shaftHalfLength, 0)
        shaftEndWorld.set(0, shaftHalfLength, 0)
        probeShaft.localToWorld(shaftStartWorld)
        probeShaft.localToWorld(shaftEndWorld)
        probeSegment = {
          start: threePointWorldM(shaftStartWorld),
          end: threePointWorldM(shaftEndWorld),
        }
      }
      tipMesh.visible = !weldRef.current?.active && Boolean(
        pathPositions?.count && sample && performance.now() - sample.receivedAt < 500
      )
      if (weldRef.current && probeTip) {
        const tipThree = sample
          ? toThreeBasePosition(sample.x, sample.y, sample.z) : modelTipWorld
        const tipWorldM = threePointWorldM(tipThree)
        weldRef.current = appendWeldSample(
          weldRef.current,
          sample && performance.now() - sample.receivedAt < 500 ? sample : null,
          tipWorldM,
          scanResultRef.current,
          FIXTURE_ORIGIN_WORLD_MM,
          TABLE_ORIGIN_MM.z + WORKPIECE_CLEARANCE_MM,
          probeSegment
        )
      }
      const showScanOverlays = !weldRef.current?.active
      contactGroup.visible = showScanOverlays
      trajectoryLine.visible = showScanOverlays
      pathCandidateGroup.visible = showScanOverlays
      weldEffect.tick(weldRef.current?.scan_id === renderedScanRef.current ? weldRef.current : null)
      controls.update()

      renderer.render(
        scene,
        camera
      )
    }

    animate()


    // React 화면 종료 시 정리
    return () => {
      cancelAnimationFrame(animationFrameId)

      resizeObserver.disconnect()

      controls.dispose()

      disposed = true
      weldEffect.dispose()
      robotModel.dispose()
      disposeObject3D(scene)

      robotModelRef.current = null
      robotJointRefs.current = {}

      tipMeshRef.current = null
      trajectoryLineRef.current = null
      contactGroupRef.current = null
      workpieceGroupRef.current = null
      pathCandidateGroupRef.current = null
      edgeGroupRef.current = null

      renderer.dispose()
    }
  }, [])

  // =========================
  // M0609 관절 실시간 갱신
  // =========================

  useEffect(() => {
    Object.entries(
      jointPositions
    ).forEach(
      ([name, positionRad]) => {
        const joint =
          robotJointRefs.current[name]

        if (!joint) {
          return
        }

        // M0609 URDF의 joint_1~joint_6 axis는 모두 local +Z.
        joint.rotation.z =
          positionRad
      }
    )
    if (Object.keys(jointPositions).length === 6) {
      appliedJointsAtRef.current = performance.now()
    }
  }, [jointPositions])



  // =========================
  // 빨간 구는 파란 궤적의 마지막 실측 TCP와 동일한 world 좌표를 사용한다.
  // =========================

  // =========================
  // TCP 이동 궤적 3D 갱신
  // =========================

  useEffect(() => {
    if (!trajectoryLineRef.current) {
      return
    }

    if (tipTrajectory.length < 1) {
      return
    }

    const points = tipTrajectory.map((pose) =>
      toThreeBasePosition(
        pose.x,
        pose.y,
        pose.z
      )
    )

    const newGeometry =
      new THREE.BufferGeometry()
        .setFromPoints(points)

    trajectoryLineRef.current.geometry.dispose()

    trajectoryLineRef.current.geometry =
      newGeometry

  }, [tipTrajectory])

  // =========================
  // 접촉점 3D 갱신
  // =========================

  useEffect(() => {
    if (!contactGroupRef.current) {
      return
    }

    const group =
      contactGroupRef.current

    // 기존 접촉점 Mesh 제거
    group.clear()

    contactPoints.forEach((point) => {
      const geometry =
        new THREE.SphereGeometry(
          (0.08 / 9) * 2.5,
          20,
          20
        )

      const material =
        new THREE.MeshStandardMaterial({
          color: 0xffcc00,
        })

      const marker =
        new THREE.Mesh(
          geometry,
          material
        )

      // 판정 순간의 실제 탐침 TCP 좌표. scan/result를 만든 원본과 같은 좌표다.
      marker.position.copy(
        toThreeBasePosition(
          point.x,
          point.y,
          point.z
        )
      )

      group.add(marker)
    })

  }, [contactPoints])

  // =========================
  // scan/result 직육면체 3D 갱신
  // =========================

  useEffect(() => {
    if (!workpieceGroupRef.current) {
      return
    }

    const group =
      workpieceGroupRef.current

    group.position.set(0, 0, 0)

    // 이전 scan/result Mesh를 정리한다.
    group.children.forEach((child) => {
      child.geometry?.dispose()
      child.material?.dispose()
    })

    group.clear()

    if (!FIXTURE_ORIGIN_WORLD_MM) {
      return
    }

    // scan/result는 workpiece_fixture 기준이고 접촉점/궤적은 base_link 기준이다.
    // fixture 로컬 좌표를 고정된 화면/world 원점에 표시한다.
    group.position.copy(
      toThreePosition(
        FIXTURE_ORIGIN_WORLD_MM.x,
        FIXTURE_ORIGIN_WORLD_MM.y,
        FIXTURE_ORIGIN_WORLD_MM.z
      )
    )

    if (
      scanResult?.success !== true ||
      scanResult?.box_valid !== true ||
      !Array.isArray(scanResult.vertices) ||
      scanResult.vertices.length !== 8
    ) {
      return
    }

    const vertices =
      scanResult.vertices.map((point) => {
        const x = point?.x_mm
        const y = point?.y_mm
        const z = workpieceDisplayZ(point, scanResult)

        if (
          !Number.isFinite(x) ||
          !Number.isFinite(y) ||
          !Number.isFinite(z)
        ) {
          return null
        }

        return toThreePosition(
          x,
          y,
          z
        )
      })

    if (
      vertices.some(
        (point) => point === null
      )
    ) {
      return
    }

    // ScanResult.msg 꼭짓점 순서:
    // 0~3 = 윗면, 4~7 = 아랫면.
    // BoxGeometry를 새로 만드는 대신 실제 측정 꼭짓점으로
    // 삼각형 면을 구성한다. 따라서 향후 회전된 꼭짓점이
    // 들어와도 프론트 렌더러는 그대로 표현할 수 있다.
    const triangleIndices = [
      0, 1, 2,
      0, 2, 3,

      4, 6, 5,
      4, 7, 6,

      0, 4, 5,
      0, 5, 1,

      1, 5, 6,
      1, 6, 2,

      2, 6, 7,
      2, 7, 3,

      3, 7, 4,
      3, 4, 0,
    ]

    const positions = []

    triangleIndices.forEach((index) => {
      const point = vertices[index]

      positions.push(
        point.x,
        point.y,
        point.z
      )
    })

    const geometry =
      new THREE.BufferGeometry()

    geometry.setAttribute(
      'position',
      new THREE.Float32BufferAttribute(
        positions,
        3
      )
    )

    geometry.computeVertexNormals()

    const material =
      new THREE.MeshStandardMaterial({
        color: 0xd9dde3,
        metalness: 0.12,
        roughness: 0.62,
        transparent: true,
        opacity: 0.78,
        side: THREE.DoubleSide,
      })

    const mesh =
      new THREE.Mesh(
        geometry,
        material
      )

    group.add(mesh)

  }, [scanResult])


  // =========================
  // 스캔 결과 일반 모서리 3D 갱신
  // =========================

  useEffect(() => {
    if (!edgeGroupRef.current) {
      return
    }

    const group =
      edgeGroupRef.current

    group.position.set(0, 0, 0)

    // 이전 scan/result에서 그린 모서리를 정리한다.
    group.children.forEach((child) => {
      child.geometry?.dispose()
      child.material?.dispose()
    })

    group.clear()

    if (!FIXTURE_ORIGIN_WORLD_MM) {
      return
    }

    group.position.copy(
      toThreePosition(
        FIXTURE_ORIGIN_WORLD_MM.x,
        FIXTURE_ORIGIN_WORLD_MM.y,
        FIXTURE_ORIGIN_WORLD_MM.z
      )
    )

    // 성공한 scan/result와 edges 배열이 있을 때만 그린다.
    if (
      scanResult?.success !== true ||
      !Array.isArray(scanResult.edges)
    ) {
      return
    }

    scanResult.edges.forEach((edge) => {
      if (
        edge?.valid !== true ||
        !edge.start ||
        !edge.end
      ) {
        return
      }

      const start =
      toThreePosition(
        edge.start.x_mm,
        edge.start.y_mm,
        workpieceDisplayZ(edge.start, scanResult)
      )

      const end =
      toThreePosition(
        edge.end.x_mm,
        edge.end.y_mm,
        workpieceDisplayZ(edge.end, scanResult)
      )

      const geometry =
        new THREE.BufferGeometry()
          .setFromPoints([
            start,
            end,
          ])

      const material =
        new THREE.LineBasicMaterial({
          color: 0x666666,
        })

      const line =
        new THREE.Line(
          geometry,
          material
        )

      group.add(line)
    })
  }, [scanResult])

  // =========================
  // 외곽 엣지·경로 후보 3D 갱신
  // =========================

  useEffect(() => {
    if (!pathCandidateGroupRef.current) {
      return
    }

    const group =
      pathCandidateGroupRef.current

    group.position.set(0, 0, 0)

    // 이전 scan/result에서 그린 선의
    // geometry와 material을 먼저 정리한다.
    group.children.forEach((child) => {
      child.geometry?.dispose()
      child.material?.dispose()
    })

    group.clear()

    if (!FIXTURE_ORIGIN_WORLD_MM) {
      return
    }

    group.position.copy(
      toThreePosition(
        FIXTURE_ORIGIN_WORLD_MM.x,
        FIXTURE_ORIGIN_WORLD_MM.y,
        FIXTURE_ORIGIN_WORLD_MM.z
      )
    )

    // 정상적인 스캔 결과가 아니면
    // 그릴 경로 후보가 없다.
    if (
      scanResult?.success !== true ||
      !Array.isArray(
        scanResult.path_candidates
      )
    ) {
      return
    }

    scanResult.path_candidates.forEach(
      (candidate) => {
        if (
          candidate?.valid !== true ||
          !candidate.start ||
          !candidate.end
        ) {
          return
        }

        const start =
          toThreePosition(
            candidate.start.x_mm,
            candidate.start.y_mm,
            candidate.start.z_mm
          )

        const end =
          toThreePosition(
            candidate.end.x_mm,
            candidate.end.y_mm,
            candidate.end.z_mm
          )

        const geometry =
          new THREE.BufferGeometry()
            .setFromPoints([
              start,
              end,
            ])

        const material =
          new THREE.LineBasicMaterial({
            color: 0x00ff66,
            depthTest: false,
          })

        const line =
          new THREE.Line(
            geometry,
            material
          )

        line.renderOrder = 1

        group.add(line)
      }
    )
  }, [scanResult])

  useEffect(() => {
    scanResultRef.current = scanResult
    renderedScanRef.current = scanResult?.success === true && scanResult?.box_valid === true
      ? scanResult.scan_id : null
  }, [scanResult])

  const fixtureInRobotBase = FIXTURE_ORIGIN_WORLD_MM
    ? fixtureRelativeToBaseMm(FIXTURE_ORIGIN_WORLD_MM, ROBOT_BASE_WORLD_MM)
    : null
  const recordedFixture = scanResult?.ros_base_to_fixture_mm
  const fixtureFrameMismatch = Boolean(fixtureInRobotBase &&
    Array.isArray(recordedFixture) && recordedFixture.length === 3 &&
    Math.hypot(
      fixtureInRobotBase.x - recordedFixture[0],
      fixtureInRobotBase.y - recordedFixture[1],
      fixtureInRobotBase.z - recordedFixture[2],
    ) > 2)

  const tipWorldPose = tipPose
    ? basePointWorldMm(tipPose, ROBOT_BASE_WORLD_MM)
    : null
  const candidateWorldCoordinate = (point, axis) =>
    point && FIXTURE_ORIGIN_WORLD_MM
      ? formatNumber(fixturePointWorldMm(point, FIXTURE_ORIGIN_WORLD_MM)[axis])
      : '-'

  const progressPercent = progressTotal > 0
    ? Math.min(100, Math.max(0, (progress / progressTotal) * 100))
    : 0
  const phaseTone = ['ERROR', 'STOPPED'].includes(phase)
    ? 'danger'
    : phase === 'DONE'
      ? 'success'
      : phase === 'IDLE'
        ? 'neutral'
        : 'active'

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">WELD-MADE · M0609</p>
          <h1>접촉 탐색 시스템</h1>
          <p className="subtitle">외곽 엣지·경로 후보 생성 시스템</p>
        </div>
        <div className="system-badges" aria-label="시스템 연결 상태">
          <span className={`status-badge ${wsConnected ? 'is-ok' : 'is-error'}`}>
            <i /> WebSocket {wsConnected ? '연결됨' : '연결 안 됨'}
          </span>
          <span className={`status-badge ${robotModelStatus === 'READY' ? 'is-ok' : 'is-warn'}`}>
            <i /> M0609 {robotModelStatus}
          </span>
          <span className={`status-badge ${safetyLatched ? 'is-error' : 'is-ok'}`}>
            <i /> 안전 {safetyLatched ? '래치됨' : safetyStatusSeen ? '정상' : '확인 중'}
          </span>
        </div>
      </header>

      <div className="workspace-grid">
        <section className="panel viewer-panel">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">LIVE VIEW</p>
              <h2>3D 화면</h2>
            </div>
            <span className={`phase-chip ${phaseTone}`}>
              {getPhaseLabel(phase, progress, progressTotal)}
            </span>
          </div>

          <div className="canvas-wrap">
            <canvas ref={canvasRef} />
            <div className="view-legend" aria-label="3D 표시 범례">
              <span><i className="legend-tip" />탐침 끝</span>
              <span><i className="legend-contact" />접촉점</span>
              <span><i className="legend-path" />경로 후보</span>
            </div>
            {robotModelStatus === 'LOADING' && (
              <div className="canvas-notice">로봇 모델을 불러오는 중입니다.</div>
            )}
            {['PARTIAL', 'ERROR'].includes(robotModelStatus) && (
              <div className="canvas-notice is-error" role="alert">
                일부 로봇 모델을 불러오지 못했습니다.
              </div>
            )}
          </div>
          <div className="weld-controls">
            {Array.from({ length: 8 }, (_, line) => (
              <button key={line} disabled={!weld || weld.active || weldPending || safetyLatched || fixtureFrameMismatch || scanResult?.success !== true || !['DONE', 'IDLE', 'STOPPED'].includes(phase)}
                onClick={() => commandWeld('start', line)}>L{line} 용접 시작</button>
            ))}
            {/* <button className="danger" disabled={!weld?.active || weldPending} onClick={() => commandWeld('stop')}>용접 중지</button> */}
            <span role="status">{!weld ? '용접 상태 연결 대기' : `${({IDLE:'대기', PREPARING:'준비', APPROACH:'접근', WELDING:'용접', RETREAT:'후퇴', HOMING:'홈 복귀', DONE:'완료', STOPPING:'중지 중', STOPPED:'중단', ERROR:'오류'})[weld.phase] ?? weld.phase} · L${weld.line}`}</span>
            {fixtureFrameMismatch && <p role="alert">부재·로봇 좌표계 불일치: 저장된 ROS fixture 기준점은 재설정해야 합니다.</p>}
            {(weldError || weld?.detail) && <p role="alert">{weldError || weld.detail}</p>}
          </div>
          <p className="view-help">좌클릭 드래그: 회전 · 휠: 확대/축소 · 우클릭 드래그: 이동</p>
        </section>

        <aside className="side-column">
          <section className="panel action-panel">
            <div className="panel-heading compact">
              <div><p className="section-kicker">CONTROL</p><h2>작업 제어</h2></div>
            </div>
            <div className="control-panel">
              <button className="primary" disabled={weld?.active} onClick={handleStart}>시작</button>
              <button className="danger" onClick={() => weld?.active ? commandWeld('stop') : handleStop()}>중지</button>
              <button disabled={weld?.active} onClick={handleHome}>안전복귀</button>
              <button disabled={weld?.active} onClick={handleResume}>재시작</button>
              <button
                className="wide"
                onClick={handleSafetyReset}
                disabled={safetyStatusSeen && !safetyLatched}
                title={
                  !safetyStatusSeen
                    ? '안전 상태 미수신: 안전 해제 명령을 시도할 수 있습니다.'
                    : safetyLatched
                      ? '안전 래치를 해제합니다.'
                      : '안전 래치가 걸려 있지 않습니다.'
                }
              >안전 해제</button>
            </div>
          </section>

          <section className="panel status-panel">
            <div className="panel-heading compact">
              <div><p className="section-kicker">PROGRESS</p><h2>현재 상태</h2></div>
              <strong>{progress} / {progressTotal}</strong>
            </div>
            <div className="progress-track" aria-label={`진행도 ${progress} / ${progressTotal}`}>
              <span style={{ width: `${progressPercent}%` }} />
            </div>
            <dl className="status-list">
              <div><dt>현재 단계</dt><dd>{getPhaseLabel(phase, progress, progressTotal)}</dd></div>
              <div><dt>진행 방향</dt><dd>{direction}</dd></div>
              <div><dt>최근 명령</dt><dd>{commandStatus}</dd></div>
              <div><dt>관절 수신</dt><dd>{Object.keys(jointPositions).length} / 6</dd></div>
            </dl>
            <p className="scan-id">Scan ID <code>{scanId ?? '-'}</code></p>
          </section>

          <section className="panel tcp-panel">
            <div className="panel-heading compact">
              <div><p className="section-kicker">TCP POSITION · WORLD</p><h2>탐침 위치</h2></div>
            </div>
            {tipWorldPose ? (
              <div className="coordinate-grid">
                <div><span>X</span><strong>{formatNumber(tipWorldPose.x)}</strong><small>mm</small></div>
                <div><span>Y</span><strong>{formatNumber(tipWorldPose.y)}</strong><small>mm</small></div>
                <div><span>Z</span><strong>{formatNumber(tipWorldPose.z)}</strong><small>mm</small></div>
              </div>
            ) : <p className="empty-state">팁 위치를 기다리는 중입니다.</p>}
            <p className="mini-status">{jointStatus}</p>
          </section>
        </aside>
      </div>

      <section className="panel result-panel">
        <div className="panel-heading">
          <div><p className="section-kicker">SCAN RESULT</p><h2>외곽 엣지·경로 후보</h2></div>
          {scanResult?.success === true && <span className="result-ready">결과 생성 완료</span>}
        </div>

        {scanResult?.success === true && (
          <div className="measurement-grid">
            <div><span>폭</span><strong>{formatNumber(scanResult.width_mm)}</strong><small>mm</small></div>
            <div><span>길이</span><strong>{formatNumber(scanResult.length_mm)}</strong><small>mm</small></div>
            <div><span>높이</span><strong>{formatNumber(scanResult.height_mm)}</strong><small>mm</small></div>
            <div><span>경로 후보</span><strong>{scanResult.path_candidates?.length ?? 0}</strong><small>개</small></div>
          </div>
        )}
        {!scanResult && <p className="empty-state large">스캔을 시작하면 측정 결과와 경로 후보가 여기에 표시됩니다.</p>}
        {scanResult?.success === true && !FIXTURE_ORIGIN_WORLD_MM && (
          <p className="alert-message">부재 원점 미설정: VITE_FIXTURE_ORIGIN_WORLD_MM 값을 확인하세요.</p>
        )}
        {scanResult && scanResult.success !== true && (
          <p className="alert-message">경로 후보를 생성하지 못했습니다. {scanResult.reason ?? 'UNKNOWN'}</p>
        )}
        {scanResult?.success === true && !scanResult.path_candidates && (
          <p className="empty-state">경로 후보 데이터가 없습니다.</p>
        )}

        {scanResult?.success === true && Array.isArray(scanResult.path_candidates) && (
          <div className="table-wrap">
            <table>
              <thead><tr>
                <th>번호</th><th>시작 X</th><th>시작 Y</th><th>시작 Z</th>
                <th>끝 X</th><th>끝 Y</th><th>끝 Z</th><th>길이</th>
              </tr></thead>
              <tbody>
                {scanResult.path_candidates.map((candidate, index) => (
                  <tr key={index}>
                    <td><span className="path-number">{index + 1}</span></td>
                    <td>{candidateWorldCoordinate(candidate.start, 'x')} mm</td>
                    <td>{candidateWorldCoordinate(candidate.start, 'y')} mm</td>
                    <td>{candidateWorldCoordinate(candidate.start, 'z')} mm</td>
                    <td>{candidateWorldCoordinate(candidate.end, 'x')} mm</td>
                    <td>{candidateWorldCoordinate(candidate.end, 'y')} mm</td>
                    <td>{candidateWorldCoordinate(candidate.end, 'z')} mm</td>
                    <td><strong>{formatNumber(candidate.length_mm)} mm</strong></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {scanResult?.success === true && (
          <p className="result-meta">화면 좌표: World(mm) · 원본 결과: {scanResult.frame_id ?? '-'}</p>
        )}
      </section>

      <div className="details-grid">
        <section className="panel history-panel">
          <div className="panel-heading compact">
            <div><p className="section-kicker">COMMANDS</p><h2>명령 상태 이력</h2></div>
            <span className="count-badge">{commandHistory.length}</span>
          </div>
          <div className="scroll-area">
            {commandHistory.length === 0 && <p className="empty-state">아직 전송한 명령이 없습니다.</p>}
            {[...commandHistory].reverse().map((command) => (
              <article className="command-item" key={command.requestId}>
                <div><strong>{getCommandLabel(command.commandTopic)}</strong><span>{formatLogTime(command.updatedAtMs)}</span></div>
                <span className={`command-state ${command.status.toLowerCase()}`}>{command.status}</span>
                {(command.ack?.accepted === false || command.status === 'FAILED') && (
                  <p>{command.ack?.reason ?? command.result?.reason ?? '명령 처리 실패'}</p>
                )}
              </article>
            ))}
          </div>
        </section>

        <section className="panel log-panel">
          <div className="panel-heading compact">
            <div><p className="section-kicker">SYSTEM LOG</p><h2>시간순 로그</h2></div>
            <span className="count-badge">{logs.length}</span>
          </div>
          <div className="scroll-area log-list">
            {logs.length === 0 && <p className="empty-state">아직 로그가 없습니다.</p>}
            {[...logs].reverse().map((log, index) => (
              <p key={`${log.timestampMs}-${index}`}><time>{formatLogTime(log.timestampMs)}</time><span>{log.message}</span></p>
            ))}
          </div>
        </section>
      </div>

      <details className="diagnostics panel">
        <summary>상세 시스템 정보</summary>
        <div className="diagnostic-grid">
          <p><span>Phase 코드</span>{phase}</p>
          <p><span>Request ID</span>{lastRequestId ?? '-'}</p>
          <p><span>팁 기준 프레임</span>{tipPose?.frameId ?? '-'}</p>
          <p><span>RG2 자세</span>0.721396 rad · 탐침 돌출 13 mm</p>
        </div>
      </details>
    </main>
  )
}


export default App
