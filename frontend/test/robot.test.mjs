import assert from 'node:assert/strict'
import { test } from 'node:test'
import { Group, Vector3, BoxGeometry, Mesh, MeshBasicMaterial } from 'three'
import { ColladaLoader } from 'three/addons/loaders/ColladaLoader.js'
import { STLLoader } from 'three/addons/loaders/STLLoader.js'
import { buildM0609Model, setRosOrigin } from '../src/robotModel.js'
import { parseGripperJoints, parseRobotJoints } from '../src/robotJoints.js'

test('URDF fixed-axis pitch/yaw maps local X to base Z', () => {
  const frame = new Group()
  setRosOrigin(frame, [0, 0, 0], [0, -Math.PI / 2, -Math.PI / 2])
  const actual = new Vector3(1, 0, 0).applyQuaternion(frame.quaternion)
  assert.ok(actual.distanceTo(new Vector3(0, 0, 1)) < 1e-12)
})

// Independent Rz(yaw) Ry(pitch) Rx(roll) matrix FK from upstream
// DoosanRobotics/doosan-robot2@6c5f3ba / dsr_description2/urdf/m0609.white.urdf.
// Tool endpoint: flange [0, 0, 0.25212] m, then (x,z,-y) * 10.
for (const [q, expected] of [
  [[0, 0, 0, 0, 0, 0], [0.001509836150225383, 12.866199659608952, -0.06383275132679628]],
  [[-0.3704, 0.2164, 1.5402, -0.0007, 1.3843, -0.2655], [4.216556844090745, 0.9473771359529615, 1.5752515454675244]],
  [[0.4, -0.6, 0.8, 0.3, -0.2, 0.1], [-1.3725537021584933, 12.068255498044916, 0.7486825110268509]],
]) {
  test(`probe follows six-joint FK: ${q}`, () => {
    const model = buildM0609Model({ loadVisuals: false })
    q.forEach((angle, i) => { model.jointRefs[`joint_${i + 1}`].rotation.z = angle })
    const actual = model.root.getObjectByName('probe_tip').getWorldPosition(new Vector3())
    assert.ok(actual.distanceTo(new Vector3(...expected)) < 1e-9)
    model.dispose()
  })
}

test('arm joint input accepts only one complete six-axis snapshot', () => {
  const names = ['joint_6', 'joint_2', 'joint_1', 'joint_4', 'joint_3', 'joint_5']
  const payload = { names, positions_rad: [0.6, 0.2, 0.1, 0.4, 0.3, 0.5] }

  assert.deepEqual(parseRobotJoints(payload), {
    joint_1: 0.1,
    joint_2: 0.2,
    joint_3: 0.3,
    joint_4: 0.4,
    joint_5: 0.5,
    joint_6: 0.6,
  })

  for (const bad of [
    null,
    {},
    { names, positions_rad: [] },
    { names, positions_rad: [NaN, 0, 0, 0, 0, 0] },
    { names: [...names, 'rg2_finger_joint'], positions_rad: [...payload.positions_rad, 0] },
    { names: [...names.slice(0, -1), 'joint_1'], positions_rad: payload.positions_rad },
  ]) {
    assert.equal(
      parseRobotJoints(bad),
      null
    )
  }
})

test('RG2 joint input is parsed independently from arm joints', () => {
  const payload = {
    names: [
      'rg2_finger_joint',
      'rg2_left_inner_knuckle_joint',
      'rg2_left_inner_finger_joint',
      'rg2_right_outer_knuckle_joint',
      'rg2_right_inner_knuckle_joint',
      'rg2_right_inner_finger_joint',
    ],
    positions_rad: [0.2, -0.2, 0.2, -0.2, -0.2, 0.2],
  }

  assert.deepEqual(
    parseGripperJoints(payload),
    Object.fromEntries(
      payload.names.map(
        (name, index) => [
          name,
          payload.positions_rad[index],
        ]
      )
    )
  )

  assert.equal(
    parseGripperJoints({
      names: ['rg2_finger_joint'],
      positions_rad: [0],
    }),
    null
  )
})

test('COLLADA correction and late-load cleanup work without a browser', async (t) => {
  const pending = []
  t.mock.method(ColladaLoader.prototype, 'loadAsync', () => new Promise(resolve => pending.push(resolve)))
  t.mock.method(STLLoader.prototype, 'loadAsync', async () => new BoxGeometry())
  const model = buildM0609Model()
  const visuals = pending.map(resolve => {
    const scene = new Group()
    scene.rotation.x = -Math.PI / 2 // ColladaLoader Z_UP conversion
    scene.add(new Mesh(new BoxGeometry(), new MeshBasicMaterial()))
    resolve({ scene })
    return scene
  })
  await model.loadPromise
  for (const visual of visuals) {
    assert.equal(visual.rotation.x, 0)
    assert.equal(visual.scale.x, 0.001)
  }
  model.dispose()

  pending.length = 0
  const unmounted = buildM0609Model()
  unmounted.dispose()
  let disposed = 0
  for (const resolve of pending) {
    const scene = new Group()
    const geometry = new BoxGeometry()
    geometry.addEventListener('dispose', () => { disposed += 1 })
    scene.add(new Mesh(geometry, new MeshBasicMaterial()))
    resolve({ scene })
  }
  await unmounted.loadPromise
  assert.equal(disposed, 10)
})
