import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import './App.css'


function App() {
  // Three.js canvas
  const canvasRef = useRef(null)

  // 화면에 표시할 현재 상태
  const [phase, setPhase] = useState('IDLE')
  const [direction, setDirection] = useState('-')
  const [progress, setProgress] = useState(0)

  // 시간순 로그
  const [logs, setLogs] = useState([])


  // =========================
  // 로그 추가 함수
  // =========================
  function addLog(message) {
    const now = new Date().toLocaleTimeString()

    setLogs((prevLogs) => [
      ...prevLogs,
      `${now} - ${message}`,
    ])
  }


  // =========================
  // 버튼 함수
  // =========================

  function handleStart() {
    setPhase('EDGE_SEARCH')
    setDirection('POS_X')
    setProgress(1)

    addLog('스캔 시작')
  }


  function handleStop() {
    setPhase('STOPPED')

    addLog('스캔 중지')
  }


  function handleHome() {
    setPhase('HOMING')
    setDirection('-')

    addLog('안전복귀 시작')
  }


  function handleResume() {
    setPhase('EDGE_SEARCH')
    setDirection('POS_X')

    addLog('스캔 재시작')
  }


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
    const tableGeometry =
      new THREE.BoxGeometry(
        4,
        0.2,
        3
      )

    const tableMaterial =
      new THREE.MeshStandardMaterial()

    const table = new THREE.Mesh(
      tableGeometry,
      tableMaterial
    )

    table.position.y = -0.1

    scene.add(table)


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


    // 8. 화면 그리기
    renderer.render(
      scene,
      camera
    )


    // React 화면 종료 시 정리
    return () => {
      renderer.dispose()
    }
  }, [])


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
          현재 단계: {phase}
        </p>

        <p>
          진행 방향: {direction}
        </p>

        <p>
          진행도: {progress} / 4
        </p>

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
          <p key={index}>
            {log}
          </p>
        ))}

      </section>

    </main>
  )
}


export default App
