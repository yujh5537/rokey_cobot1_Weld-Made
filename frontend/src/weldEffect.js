import * as THREE from 'three'

// Adapted from the supplied ArcWelding particle/stitch effect to world-space 3D.
// World-space beads remain attached to the workpiece while the camera moves.
export function createWeldEffect(scene) {
  const group = new THREE.Group()
  scene.add(group)
  const beadGeometry = new THREE.SphereGeometry(0.007, 6, 4)
  const beadMaterial = new THREE.MeshBasicMaterial({ color: 0x333333 })
  const beads = new THREE.InstancedMesh(beadGeometry, beadMaterial, 5000)
  beads.frustumCulled = false
  beads.count = 0
  group.add(beads)
  const positions = new Float32Array(360 * 6)
  const colors = new Float32Array(360 * 6)
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))
  const material = new THREE.LineBasicMaterial({ vertexColors: true, transparent: true,
    blending: THREE.AdditiveBlending, depthWrite: false })
  const sparks = new THREE.LineSegments(geometry, material)
  sparks.frustumCulled = false
  group.add(sparks)
  const glow = new THREE.Mesh(new THREE.SphereGeometry(0.03, 12, 8),
    new THREE.MeshBasicMaterial({ color: 0xe5f5ff, transparent: true,
      blending: THREE.AdditiveBlending, depthWrite: false }))
  group.add(glow)
  const particles = []
  const matrix = new THREE.Matrix4()
  let runId = ''
  let previous = performance.now()
  let count = 0
  function tick(state) {
    const now = performance.now()
    const dt = Math.min((now - previous) / 1000, 0.05)
    previous = now
    if (state?.run_id !== runId) {
      runId = state?.run_id
      count = 0
      particles.length = 0
    }
    const points = state?.beads ?? []
    for (; count < Math.min(points.length, 5000); count++) {
      const p = points[count]
      matrix.makeTranslation(p[0] * 10, p[2] * 10, -p[1] * 10)
      beads.setMatrixAt(count, matrix)
    }
    beads.count = count
    beads.instanceMatrix.needsUpdate = true
    glow.visible = Boolean(state?.arc && state?.contact)
    // End the arc immediately, including particles already emitted. Keep the beads.
    if (!glow.visible) particles.length = 0
    if (glow.visible) {
      const p = state.contact
      glow.position.set(p[0] * 10, p[2] * 10, -p[1] * 10)
      glow.scale.setScalar(1 + Math.random() * 0.7)
      for (let i = 0; i < Math.ceil(dt * 360) && particles.length < 360; i++) {
        particles.push({ p: glow.position.clone(), v: new THREE.Vector3(
          (Math.random() - 0.5) * 1.8, Math.random() * 2,
          (Math.random() - 0.5) * 1.8), age: 0, life: 0.25 + Math.random() * 0.55 })
      }
    }
    for (let i = particles.length - 1; i >= 0; i--) {
      const p = particles[i]
      p.age += dt
      if (p.age > p.life) { particles.splice(i, 1); continue }
      p.v.multiplyScalar(Math.exp(-2 * dt))
      p.v.y -= dt * 2
      p.p.addScaledVector(p.v, dt)
    }
    particles.forEach((p, i) => {
      const tail = p.p.clone().addScaledVector(p.v, -0.045)
      p.p.toArray(positions, i * 6)
      tail.toArray(positions, i * 6 + 3)
      const a = 1 - p.age / p.life
      colors.set([a, a * 0.55, a * 0.08, a * 0.3, a * 0.08, 0], i * 6)
    })
    geometry.setDrawRange(0, particles.length * 2)
    geometry.attributes.position.needsUpdate = true
    geometry.attributes.color.needsUpdate = true
  }
  return { tick, dispose: () => beads.dispose() }
}
