import * as THREE from 'three'
import { ColladaLoader } from 'three/addons/loaders/ColladaLoader.js'
import { STLLoader } from 'three/addons/loaders/STLLoader.js'

const ROS_METERS_TO_THREE = 10

const M0609_MESH_ROOT =
  'https://raw.githubusercontent.com/DoosanRobotics/doosan-robot2/6c5f3ba622bfa9d6f9cffebf21fa44f57db55b48/dsr_description2/meshes/m0609_white/'

const RG2_MESH_ROOT =
  'https://raw.githubusercontent.com/ABC-iRobotics/onrobot-ros2/c6e390313e831a2e54a0ad5894b2911cc360a16a/onrobot_rg_description/meshes/rg2/visual/'

// RG2는 이 프로젝트에서 탐침을 고정 파지하므로 웹에서는 항상 닫힌 자세로 표시한다.
// upstream RG2 URDF의 finger_joint upper limit(45 deg)를 닫힘 자세로 사용한다.
export const RG2_CLOSED_MASTER_RAD = 0.785398

const RG2_CLOSED_JOINTS = {
  rg2_finger_joint: RG2_CLOSED_MASTER_RAD,
  rg2_left_inner_knuckle_joint: -RG2_CLOSED_MASTER_RAD,
  rg2_left_inner_finger_joint: RG2_CLOSED_MASTER_RAD,
  rg2_right_outer_knuckle_joint: -RG2_CLOSED_MASTER_RAD,
  rg2_right_inner_knuckle_joint: -RG2_CLOSED_MASTER_RAD,
  rg2_right_inner_finger_joint: RG2_CLOSED_MASTER_RAD,
}

const PROBE_EXTENSION_FROM_GRIPPER_M = 0.013

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
  loadVisuals,
  gripperJointRefs
) {
  const stlLoader =
    new STLLoader()

  const base =
    new THREE.Group()

  // m0609_rg2_bringup/urdf/onrobot_rg2.xacro:
  // tool0 -> rg2_base_link fixed origin rpy="1.5708 0 1.5708".
  setRosOrigin(
    base,
    [0, 0, 0],
    [Math.PI / 2, 0, Math.PI / 2]
  )

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

  function createFinger(
    side,
    reflect
  ) {
    // outer knuckle origin
    const outerOrigin =
      new THREE.Group()

    setRosOrigin(
      outerOrigin,
      [0, reflect * -0.017178, 0.125797],
      [0, 0, reflect < 0 ? Math.PI : 0]
    )

    base.add(outerOrigin)

    // Revolute joint: left=finger_joint(axis -X),
    // right=right_outer_knuckle_joint(axis +X).
    const outerJoint =
      new THREE.Group()

    outerOrigin.add(outerJoint)

    if (side === 'left') {
      gripperJointRefs.rg2_finger_joint = {
        object: outerJoint,
        axis: 'x',
        sign: -1,
      }
    } else {
      gripperJointRefs.rg2_right_outer_knuckle_joint = {
        object: outerJoint,
        axis: 'x',
        sign: 1,
      }
    }

    loadStl(
      outerJoint,
      'outer_knuckle.stl',
      whiteMaterial
    )

    // inner finger origin -> +X revolute joint
    const innerFingerOrigin =
      new THREE.Group()

    setRosOrigin(
      innerFingerOrigin,
      [0, -0.039592, 0.038177],
      [0, 0, 0]
    )

    outerJoint.add(
      innerFingerOrigin
    )

    const innerFingerJoint =
      new THREE.Group()

    innerFingerOrigin.add(
      innerFingerJoint
    )

    gripperJointRefs[
      `rg2_${side}_inner_finger_joint`
    ] = {
      object: innerFingerJoint,
      axis: 'x',
      sign: 1,
    }

    loadStl(
      innerFingerJoint,
      'inner_finger.stl',
      darkMaterial
    )

    // inner knuckle origin -> +X revolute joint
    const innerKnuckleOrigin =
      new THREE.Group()

    setRosOrigin(
      innerKnuckleOrigin,
      [0, reflect * -0.007678, 0.142297],
      [0, 0, reflect < 0 ? -Math.PI : 0]
    )

    base.add(
      innerKnuckleOrigin
    )

    const innerKnuckleJoint =
      new THREE.Group()

    innerKnuckleOrigin.add(
      innerKnuckleJoint
    )

    gripperJointRefs[
      `rg2_${side}_inner_knuckle_joint`
    ] = {
      object: innerKnuckleJoint,
      axis: 'x',
      sign: 1,
    }

    loadStl(
      innerKnuckleJoint,
      'inner_knuckle.stl',
      whiteMaterial
    )
  }

  createFinger('left', 1)
  createFinger('right', -1)

  // 실시간 RG2 joint 값과 무관하게 항상 닫힌 고정 파지 자세로 시작한다.
  Object.entries(
    RG2_CLOSED_JOINTS
  ).forEach(
    ([name, positionRad]) => {
      const ref =
        gripperJointRefs[name]

      if (!ref) return

      ref.object.rotation[
        ref.axis
      ] =
        positionRad * ref.sign
    }
  )

  // upstream RG2 control geometry의 닫힌 자세에서 손가락 끝 높이를 계산한다.
  // 사용자가 실측한 기준: 그리퍼 끝 -> 탐침 최하단 끝 = 13 mm.
  const rg2L3 = 0.055
  const rg2Theta3 = 0.76794
  const rg2Dz = 0.1095 + 0.0427
  const gripperEndZ =
    rg2L3 *
      Math.sin(
        RG2_CLOSED_MASTER_RAD +
          rg2Theta3
      ) +
    rg2Dz

  const probeLength =
    PROBE_EXTENSION_FROM_GRIPPER_M

  const probeTipZ =
    gripperEndZ +
    probeLength

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

  // Upstream M0609 URDF fixed flange frame:
  // link_6 -> tool0 rpy="pi -pi/2 0".
  const tool0 =
    new THREE.Group()

  setRosOrigin(
    tool0,
    [0, 0, 0],
    [Math.PI, -Math.PI / 2, 0]
  )

  link6.add(tool0)

  const gripperJointRefs = {}

  buildRg2Model(
    tool0,
    loadTasks,
    lifetime,
    loadVisuals,
    gripperJointRefs
  )

  return {
    root,
    jointRefs,
    gripperJointRefs,
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
