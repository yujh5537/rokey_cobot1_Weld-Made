import * as THREE from 'three'
import { ColladaLoader } from 'three/addons/loaders/ColladaLoader.js'
import { STLLoader } from 'three/addons/loaders/STLLoader.js'

const ROS_METERS_TO_THREE = 10

const M0609_MESH_ROOT =
  'https://raw.githubusercontent.com/DoosanRobotics/doosan-robot2/6c5f3ba622bfa9d6f9cffebf21fa44f57db55b48/dsr_description2/meshes/m0609_white/'

const RG2_MESH_ROOT =
  'https://raw.githubusercontent.com/ABC-iRobotics/onrobot-ros2/c6e390313e831a2e54a0ad5894b2911cc360a16a/onrobot_rg_description/meshes/rg2/visual/'

export function setRosOrigin(
  object,
  xyz,
  rpy
) {
  object.position.set(
    xyz[0],
    xyz[1],
    xyz[2]
  )

  object.rotation.set(
    rpy[0],
    rpy[1],
    rpy[2],
    // URDF fixed-axis RPY = Rz(yaw) * Ry(pitch) * Rx(roll).
    'ZYX'
  )
}

function makeJointFrame(
  parent,
  name,
  xyz,
  rpy,
  jointRefs
) {
  const originFrame =
    new THREE.Group()

  setRosOrigin(
    originFrame,
    xyz,
    rpy
  )

  parent.add(originFrame)

  const jointFrame =
    new THREE.Group()

  originFrame.add(jointFrame)

  jointRefs[name] =
    jointFrame

  const linkFrame =
    new THREE.Group()

  jointFrame.add(linkFrame)

  return linkFrame
}

export function disposeObject3D(object) {
  object.traverse((child) => {
    child.geometry?.dispose()

    if (Array.isArray(child.material)) {
      child.material.forEach(
        (material) =>
          material?.dispose?.()
      )
    } else {
      child.material?.dispose?.()
    }
  })
}

function buildRg2Model(
  parent,
  loadTasks,
  lifetime,
  loadVisuals
) {
  const stlLoader =
    new STLLoader()

  const base =
    new THREE.Group()

  // 프로젝트에서 사용하는 RG2 xacro의 고정 장착 자세.
  base.rotation.z =
    Math.PI / 2

  parent.add(base)

  const whiteMaterial =
    new THREE.MeshStandardMaterial({
      color: 0xd7dadd,
      metalness: 0.35,
      roughness: 0.4,
    })

  const darkMaterial =
    new THREE.MeshStandardMaterial({
      color: 0x252a2f,
      metalness: 0.15,
      roughness: 0.55,
    })

  function loadStl(
    target,
    filename,
    material
  ) {
    if (!loadVisuals) return
    const task =
      stlLoader
        .loadAsync(
          `${RG2_MESH_ROOT}${filename}`
        )
        .then((geometry) => {
          if (lifetime.disposed) {
            geometry.dispose()
            return
          }
          geometry.computeVertexNormals()

          const mesh =
            new THREE.Mesh(
              geometry,
              material
            )

          target.add(mesh)
        })

    loadTasks.push(task)
  }

  loadStl(
    base,
    'base_link.stl',
    whiteMaterial
  )

  // 고정 시각화 자세. 실기 파지 폭 피드백을 나타내지는 않는다.
  const fingerAngle = 0.0

  function createFinger(
    reflect
  ) {
    const outerOrigin =
      new THREE.Group()

    outerOrigin.position.set(
      0,
      reflect * -0.017178,
      0.125797
    )

    if (reflect < 0) {
      outerOrigin.rotation.z =
        Math.PI
    }

    base.add(outerOrigin)

    const outerJoint =
      new THREE.Group()

    outerJoint.rotation.x =
      -fingerAngle

    outerOrigin.add(outerJoint)

    loadStl(
      outerJoint,
      'outer_knuckle.stl',
      whiteMaterial
    )

    const innerFingerOrigin =
      new THREE.Group()

    innerFingerOrigin.position.set(
      0,
      -0.039592,
      0.038177
    )

    outerJoint.add(
      innerFingerOrigin
    )

    innerFingerOrigin.rotation.x =
      fingerAngle

    loadStl(
      innerFingerOrigin,
      'inner_finger.stl',
      darkMaterial
    )

    const innerKnuckleOrigin =
      new THREE.Group()

    innerKnuckleOrigin.position.set(
      0,
      reflect * -0.007678,
      0.142297
    )

    if (reflect < 0) {
      innerKnuckleOrigin.rotation.z =
        -Math.PI
    }

    innerKnuckleOrigin.rotation.x =
      -fingerAngle

    base.add(
      innerKnuckleOrigin
    )

    loadStl(
      innerKnuckleOrigin,
      'inner_knuckle.stl',
      whiteMaterial
    )
  }

  createFinger(1)
  createFinger(-1)

  // 실기 TCP: flange -> probe tip = [0, 0, 252.12] mm.
  // RG2는 고정 파지이므로 탐침 끝점을 이 TCP에 맞춰 표시한다.
  const probeTipZ = 0.25212
  const probeLength = 0.102
  const probeRadius = 0.0015

  const probeMaterial =
    new THREE.MeshStandardMaterial({
      color: 0x70757a,
      metalness: 0.65,
      roughness: 0.28,
    })

  const probe =
    new THREE.Mesh(
      new THREE.CylinderGeometry(
        probeRadius,
        probeRadius,
        probeLength,
        18
      ),
      probeMaterial
    )

  probe.rotation.x =
    Math.PI / 2

  probe.position.z =
    probeTipZ -
    probeLength / 2

  base.add(probe)

  const probeTip =
    new THREE.Mesh(
      new THREE.SphereGeometry(
        0.000225,
        16,
        16
      ),
      probeMaterial
    )

  probeTip.position.z =
    probeTipZ

  probeTip.name = 'probe_tip'
  base.add(probeTip)

  return base
}

export function buildM0609Model({ loadVisuals = true } = {}) {
  const lifetime = { disposed: false }
  const root =
    new THREE.Group()

  // ROS z-up -> Three.js y-up:
  // (x, y, z) -> (x, z, -y)
  root.rotation.x =
    -Math.PI / 2

  // URDF는 metre 단위이고 화면은 100 mm = 1 unit.
  root.scale.setScalar(
    ROS_METERS_TO_THREE
  )

  const rosBase =
    new THREE.Group()

  root.add(rosBase)

  const jointRefs = {}
  const loadTasks = []

  const colladaLoader =
    new ColladaLoader()

  function loadDae(
    target,
    filename
  ) {
    if (!loadVisuals) return
    const task =
      colladaLoader
        .loadAsync(
          `${M0609_MESH_ROOT}${filename}`
        )
        .then((result) => {
          const visual =
            result.scene

          if (lifetime.disposed) {
            disposeObject3D(visual)
            return
          }
          // These pinned DAEs are Z_UP. ColladaLoader adds a Y-up rotation;
          // undo it because the robot root already performs ROS -> Three conversion.
          visual.rotation.set(0, 0, 0)

          // 공식 M0609 URDF의 visual mesh scale=0.001.
          visual.scale.setScalar(
            0.001
          )

          target.add(visual)
        })

    loadTasks.push(task)
  }

  loadDae(
    rosBase,
    'MF0609_0_0.dae'
  )

  const link1 =
    makeJointFrame(
      rosBase,
      'joint_1',
      [0, 0, 0.1345],
      [0, 0, 0],
      jointRefs
    )

  loadDae(
    link1,
    'MF0609_1_0.dae'
  )

  const link2 =
    makeJointFrame(
      link1,
      'joint_2',
      [0, 0.0062, 0],
      [0, -1.571, -1.571],
      jointRefs
    )

  ;[
    'MF0609_2_0.dae',
    'MF0609_2_1.dae',
    'MF0609_2_2.dae',
  ].forEach(
    (filename) =>
      loadDae(
        link2,
        filename
      )
  )

  const link3 =
    makeJointFrame(
      link2,
      'joint_3',
      [0.411, 0, 0],
      [0, 0, 1.571],
      jointRefs
    )

  loadDae(
    link3,
    'MF0609_3_0.dae'
  )

  const link4 =
    makeJointFrame(
      link3,
      'joint_4',
      [0, -0.368, 0],
      [1.571, 0, 0],
      jointRefs
    )

  ;[
    'MF0609_4_0.dae',
    'MF0609_4_1.dae',
  ].forEach(
    (filename) =>
      loadDae(
        link4,
        filename
      )
  )

  const link5 =
    makeJointFrame(
      link4,
      'joint_5',
      [0, 0, 0],
      [-1.571, 0, 0],
      jointRefs
    )

  loadDae(
    link5,
    'MF0609_5_0.dae'
  )

  const link6 =
    makeJointFrame(
      link5,
      'joint_6',
      [0, -0.121, 0],
      [1.571, 0, 0],
      jointRefs
    )

  loadDae(
    link6,
    'MF0609_6_0.dae'
  )

  buildRg2Model(
    link6,
    loadTasks,
    lifetime,
    loadVisuals
  )

  return {
    root,
    jointRefs,
    dispose() {
      lifetime.disposed = true
      disposeObject3D(root)
      root.removeFromParent()
    },
    loadPromise:
      Promise.allSettled(
        loadTasks
      ),
  }
}
