import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'

const position = p => new THREE.Vector3(p.x_mm, p.y_mm, p.z_mm)
const valid = p => p && ['x_mm','y_mm','z_mm'].every(k => Number.isFinite(p[k]))
function dispose(object) {
  object.traverse(child => { child.geometry?.dispose(); if (Array.isArray(child.material)) child.material.forEach(m => m.dispose()); else child.material?.dispose() })
}

export default function Scene({ sample, trail, points }) {
  const host = useRef(null)
  const view = useRef(null)
  useEffect(() => {
    const container = host.current
    const scene = new THREE.Scene()
    scene.background = new THREE.Color('#101e2e')
    const camera = new THREE.PerspectiveCamera(45, 1, 1, 10000)
    camera.up.set(0,0,1)
    camera.position.set(800,-650,650)
    let renderer
    try { renderer = new THREE.WebGLRenderer({ antialias: true }) }
    catch { container.textContent = 'WebGL을 사용할 수 없습니다. TCP 숫자 표시는 계속 제공됩니다.'; return }
    renderer.setPixelRatio(Math.min(devicePixelRatio,2))
    container.appendChild(renderer.domElement)
    const controls = new OrbitControls(camera,renderer.domElement)
    controls.target.set(250,0,50); controls.update()
    scene.add(new THREE.HemisphereLight(0xffffff,0x445566,3))
    const grid = new THREE.GridHelper(1000,20,0x58748e,0x294052)
    grid.rotation.x = Math.PI/2; scene.add(grid)
    const table = new THREE.Mesh(new THREE.BoxGeometry(1000,700,10), new THREE.MeshStandardMaterial({ color: 0x24384a, transparent:true, opacity:0.45 }))
    table.position.z=-6; scene.add(table)
    scene.add(new THREE.AxesHelper(100))
    const dynamic = new THREE.Group(); scene.add(dynamic)
    const draw = () => renderer.render(scene,camera)
    const resize = () => { const w=container.clientWidth, h=420; renderer.setSize(w,h); camera.aspect=w/h; camera.updateProjectionMatrix(); draw() }
    const observer = new ResizeObserver(resize); observer.observe(container)
    controls.addEventListener('change',draw)
    view.current={dynamic,draw}
    resize()
    return () => { view.current=null; observer.disconnect(); controls.dispose(); dispose(scene); renderer.dispose(); renderer.domElement.remove() }
  }, [])
  useEffect(() => {
    if (!view.current) return
    const {dynamic,draw}=view.current
    dispose(dynamic); dynamic.clear()
    if (sample?.valid && valid(sample.pose)) {
      const tip=new THREE.Mesh(new THREE.SphereGeometry(4,16,12),new THREE.MeshStandardMaterial({color:0x75f3db}))
      tip.position.copy(position(sample.pose)); dynamic.add(tip)
    }
    const path=trail.filter(valid)
    if(path.length>1) dynamic.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(path.map(position)),new THREE.LineBasicMaterial({color:0x61b8ff})))
    for(const event of points.filter(e=>e.frame_id===sample?.frame_id && valid(e.pose))) {
      const marker=new THREE.Mesh(new THREE.SphereGeometry(3,12,8),new THREE.MeshBasicMaterial({color:0xffba64}))
      marker.position.copy(position(event.pose)); dynamic.add(marker)
    }
    draw()
  },[sample,trail,points])
  return <div ref={host} className="canvas-host" aria-label="팁 위치와 접촉점 3D 화면" />
}
