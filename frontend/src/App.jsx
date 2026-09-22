import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
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

function getBaseToFixtureMm() {
  const raw =
    import.meta.env
      .VITE_BASE_TO_FIXTURE_MM ?? ''

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

const BASE_TO_FIXTURE_MM = getBaseToFixtureMm()

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
  // Three.js canvas
  const canvasRef = useRef(null)

  // Three.js에서 현재 TCP 팁 Mesh를 참조한다.
  const tipMeshRef = useRef(null)

  // Three.js에서 TCP 이동 궤적 Line을 참조한다.
  const trajectoryLineRef = useRef(null)

  // Three.js 접촉점들을 담는 Group
  const contactGroupRef = useRef(null)

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

  // 현재 로봇 TCP 팁 위치
  // robot/sample의 pose는 base_link 기준, 단위는 mm
  const [tipPose, setTipPose] = useState(null)

  // robot/sample로 받은 TCP 이동 기록
  const [tipTrajectory, setTipTrajectory] = useState([])

  // contact/event로 받은 접촉점 목록
  const [contactPoints, setContactPoints] = useState([])

  // scan/result로 받은 최종 형상 결과
  const [scanResult, setScanResult] = useState(null)

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
    sendScanCommand('home')
  }


  function handleResume() {
    sendScanCommand('resume')
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


        // scan/state
        if (topic === 'scan/state') {
          const nextPhase =
            payload.phase ?? 'UNKNOWN'

          const nextScanId =
            payload.scan_id ?? null

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

          // 현재 TCP 위치
          setTipPose(newTipPose)

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
          payload.pose
        ) {
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
          setScanResult(payload)

          addLog(
            payload.success === true
              ? '스캔 형상 결과 수신'
              : `스캔 결과 실패: ${payload.reason ?? 'UNKNOWN'}`,
            payload.stamp_ms
          )
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
      websocket.close()
    }
  }, [])


  // =========================
  // Three.js 화면
  // =========================

  useEffect(() => {
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

    renderer.setSize(900, 500)


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
    // - 실제 바닥 = 작업대 상판보다 94 mm 아래
    // - 화면 축척 = 100 mm -> Three.js 1 unit
    const worktable = new THREE.Group()

    const tableWidth = 4.0
    const tableDepth = 3.0
    const tableHeight = 94 * DISPLAY_SCALE
    const topThickness = 0.12
    const floorY = -tableHeight

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

    // 작업대 상판보다 실제 바닥이 94 mm 아래에 있다.
    const floorGrid =
      new THREE.GridHelper(
        8,
        16,
        0x7f8a93,
        0xc4c9ce
      )

    floorGrid.position.y =
      floorY

    floorGrid.material.transparent =
      true

    floorGrid.material.opacity =
      0.32

    scene.add(floorGrid)


    // 5-1. M0609 위치 확인용 목업
    // 실제 URDF/GLTF 모델을 붙이기 전 배치 확인용이다.
    // 작업대가 M0609의 오른쪽에 보이도록 로봇을 왼쪽에 둔다.
    const robotGroup =
      new THREE.Group()

    const robotBase =
      new THREE.Mesh(
        new THREE.CylinderGeometry(
          0.32,
          0.38,
          0.35,
          48
        ),
        new THREE.MeshStandardMaterial({
          color: 0xe9edf0,
          metalness: 0.35,
          roughness: 0.45,
        })
      )

    robotBase.position.y =
      -0.175

    robotGroup.add(robotBase)

    const robotBody =
      new THREE.Mesh(
        new THREE.CylinderGeometry(
          0.18,
          0.22,
          0.65,
          48
        ),
        new THREE.MeshStandardMaterial({
          color: 0x2c6e9b,
          metalness: 0.25,
          roughness: 0.4,
        })
      )

    robotBody.position.y =
      0.325

    robotGroup.add(robotBody)

    // 임시 시각 배치값. 실제 Base↔fixture 관계는 이후 좌표 계약으로 치환한다.
    robotGroup.position.set(
      -2.7,
      0,
      0
    )

    scene.add(robotGroup)


    // 6. 직육면체 부재
    const workpieceGeometry =
      new THREE.BoxGeometry(
        2,
        1,
        1.2
      )

    const workpieceMaterial =
      new THREE.MeshStandardMaterial()

    const workpiece = new THREE.Mesh(
      workpieceGeometry,
      workpieceMaterial
    )

    workpiece.position.y = 0.5

    scene.add(workpiece)


    // 7. XYZ 좌표축
    const axesHelper =
      new THREE.AxesHelper(2)

    scene.add(axesHelper)

    // 8. 현재 TCP 팁 표시
    const tipGeometry =
      new THREE.SphereGeometry(
        0.12,
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

    // 13. 실시간 렌더링
    let animationFrameId

    function animate() {
      animationFrameId =
        requestAnimationFrame(animate)

      renderer.render(
        scene,
        camera
      )
    }

    animate()


    // React 화면 종료 시 정리
    return () => {
      cancelAnimationFrame(animationFrameId)

      tipMeshRef.current = null
      trajectoryLineRef.current = null
      contactGroupRef.current = null
      pathCandidateGroupRef.current = null
      edgeGroupRef.current = null

      renderer.dispose()
    }
  }, [])

  // =========================
  // TCP 팁 3D 위치 갱신
  // =========================

  useEffect(() => {
    if (!tipPose) {
      return
    }

    if (!tipMeshRef.current) {
      return
    }

    // MQTT/Web 좌표 단위는 mm.
    // 화면 표시를 위해 100 mm = Three.js 1 unit로 축소한다.
    tipMeshRef.current.position.copy(
      toThreePosition(
        tipPose.x,
        tipPose.y,
        tipPose.z
      )
    )

    tipMeshRef.current.visible = true
  }, [tipPose])

  // =========================
  // TCP 이동 궤적 3D 갱신
  // =========================

  useEffect(() => {
    if (!trajectoryLineRef.current) {
      return
    }

    if (tipTrajectory.length < 2) {
      return
    }

    const points = tipTrajectory.map((pose) =>
      toThreePosition(
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
          0.08,
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

      marker.position.copy(
        toThreePosition(
          point.x,
          point.y,
          point.z
        )
      )

      group.add(marker)
    })

  }, [contactPoints])

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

    if (!BASE_TO_FIXTURE_MM) {
      return
    }

    group.position.copy(
      toThreePosition(
        BASE_TO_FIXTURE_MM.x,
        BASE_TO_FIXTURE_MM.y,
        BASE_TO_FIXTURE_MM.z
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
        edge.start.z_mm
      )

      const end =
      toThreePosition(
        edge.end.x_mm,
        edge.end.y_mm,
        edge.end.z_mm
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

    if (!BASE_TO_FIXTURE_MM) {
      return
    }

    group.position.copy(
      toThreePosition(
        BASE_TO_FIXTURE_MM.x,
        BASE_TO_FIXTURE_MM.y,
        BASE_TO_FIXTURE_MM.z
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

  return (
    <main>

      <h1>접촉 탐색 시스템</h1>

      <p>
        외곽 엣지·경로 후보 생성 시스템
      </p>


      {/* 제어 버튼 */}
      <section className="control-panel">

        <button onClick={handleStart}>
          시작
        </button>

        <button onClick={handleStop}>
          중지
        </button>

        <button onClick={handleHome}>
          안전복귀
        </button>

        <button onClick={handleResume}>
          재시작
        </button>

      </section>


      {/* 현재 상태 */}
      <section className="status-panel">

        <h2>현재 상태</h2>

        <p>
          FastAPI WebSocket:{' '}
          {wsConnected ? '연결됨' : '연결 안 됨'}
        </p>

        <p>
          현재 단계:{' '}
          {getPhaseLabel(
            phase,
            progress,
            progressTotal
          )}
        </p>

        <p>
          Phase 코드: {phase}
        </p>

        <p>
          진행 방향: {direction}
        </p>

        <p>
          진행도: {progress} / {progressTotal}
        </p>

        <p>
          Scan ID: {scanId ?? '-'}
        </p>

        <p>
          최근 명령 상태: {commandStatus}
        </p>

        <p>
          Request ID: {lastRequestId ?? '-'}
        </p>

        {tipPose ? (
          <>
            <p>
              팁 기준 프레임: {tipPose.frameId}
            </p>

            <p>
              팁 위치:
              {' '}
              X {formatNumber(tipPose.x)} mm /
              {' '}
              Y {formatNumber(tipPose.y)} mm /
              {' '}
              Z {formatNumber(tipPose.z)} mm
            </p>
          </>
        ) : (
          <p>
            팁 위치: 아직 수신되지 않음
          </p>
        )}

      </section>

      {/* 외곽 엣지·경로 후보 */}
      <section>

        <h2>외곽 엣지·경로 후보</h2>

        {scanResult && (
          <p>
            결과 좌표 프레임:{' '}
            {scanResult.frame_id ?? '-'}
          </p>
        )}

        {scanResult?.success === true &&
        !BASE_TO_FIXTURE_MM && (
          <p>
            작업대 원점 미설정:
            VITE_BASE_TO_FIXTURE_MM 값을 확인하세요.
          </p>
        )}

        {scanResult &&
          scanResult.success !== true && (
            <p>
              경로 후보를 생성하지 못했습니다.
              {' '}
              {scanResult.reason ?? 'UNKNOWN'}
            </p>
          )}

        {scanResult?.success === true &&
          !scanResult.path_candidates && (
            <p>
              경로 후보 데이터가 없습니다.
            </p>
          )}

        {scanResult?.success === true &&
          Array.isArray(
            scanResult.path_candidates
          ) && (
            <table>

              <thead>
                <tr>
                  <th>번호</th>
                  <th>시작 X</th>
                  <th>시작 Y</th>
                  <th>시작 Z</th>
                  <th>끝 X</th>
                  <th>끝 Y</th>
                  <th>끝 Z</th>
                  <th>길이</th>
                </tr>
              </thead>

              <tbody>
                {scanResult.path_candidates.map(
                  (candidate, index) => (
                    <tr key={index}>
                      <td>
                        {index + 1}
                      </td>

                      <td>
                        {formatNumber(
                          candidate.start?.x_mm
                        )} mm
                      </td>

                      <td>
                        {formatNumber(
                          candidate.start?.y_mm
                        )} mm
                      </td>

                      <td>
                        {formatNumber(
                          candidate.start?.z_mm
                        )} mm
                      </td>

                      <td>
                        {formatNumber(
                          candidate.end?.x_mm
                        )} mm
                      </td>

                      <td>
                        {formatNumber(
                          candidate.end?.y_mm
                        )} mm
                      </td>

                      <td>
                        {formatNumber(
                          candidate.end?.z_mm
                        )} mm
                      </td>

                      <td>
                        {formatNumber(
                          candidate.length_mm
                        )} mm
                      </td>
                    </tr>
                  )
                )}
              </tbody>

            </table>
          )}

      </section>

      {/* 명령 상태 이력 */}
      <section>

        <h2>명령 상태 이력</h2>

        {commandHistory.length === 0 && (
          <p>아직 전송한 명령이 없습니다.</p>
        )}

        {commandHistory.map((command) => (
          <div key={command.requestId}>

            <p>
              명령:{' '}
              {getCommandLabel(
                command.commandTopic
              )}
            </p>

            <p>
              접수 결과:{' '}
              {command.status === 'REJECTED'
                ? '거절'
                : command.ack?.accepted === true
                  ? '접수'
                  : '대기'}
            </p>

            <p>
              실행 결과:{' '}
              {command.status === 'SUCCEEDED'
                ? '완료'
                : command.status === 'FAILED'
                  ? '실패'
                  : command.status === 'REJECTED'
                    ? '-'
                    : '대기'}
            </p>

            <p>
              상태 코드: {command.status}
            </p>

            {command.ack?.accepted === false &&
              command.ack?.reason && (
                <p>
                  거절 사유: {command.ack.reason}
                  {command.ack.reason_code != null &&
                    ` (${command.ack.reason_code})`}
                  {command.ack.detail &&
                    ` — ${command.ack.detail}`}
                </p>
              )}

            {command.status === 'FAILED' &&
              command.result?.reason && (
                <p>
                  실패 사유: {command.result.reason}
                  {command.result.reason_code != null &&
                    ` (${command.result.reason_code})`}
                  {command.result.detail &&
                    ` — ${command.result.detail}`}
                </p>
              )}

            <p>
              Request ID: {command.requestId}
            </p>

            <p>
              갱신 시각:{' '}
              {formatLogTime(command.updatedAtMs)}
            </p>

          </div>
        ))}

      </section>

      {/* Three.js */}
      <section>

        <h2>3D 화면</h2>

        <canvas ref={canvasRef} />

      </section>


      {/* 로그 */}
      <section className="log-panel">

        <h2>시간순 로그</h2>

        {logs.length === 0 && (
          <p>아직 로그가 없습니다.</p>
        )}

        {logs.map((log, index) => (
          <p
            key={`${log.timestampMs}-${index}`}
          >
            {formatLogTime(log.timestampMs)}
            {' - '}
            {log.message}
          </p>
        ))}

      </section>

    </main>
  )
}


export default App
