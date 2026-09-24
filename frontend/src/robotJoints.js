const ARM_JOINTS = new Set([
  'joint_1',
  'joint_2',
  'joint_3',
  'joint_4',
  'joint_5',
  'joint_6',
])

const RG2_JOINTS = new Set([
  'rg2_finger_joint',
  'rg2_left_inner_knuckle_joint',
  'rg2_left_inner_finger_joint',
  'rg2_right_outer_knuckle_joint',
  'rg2_right_inner_knuckle_joint',
  'rg2_right_inner_finger_joint',
])

function parseNamedSnapshot(
  payload,
  allowedNames
) {
  if (
    !payload ||
    !Array.isArray(payload.names) ||
    !Array.isArray(payload.positions_rad) ||
    payload.names.length !== payload.positions_rad.length ||
    payload.names.length !== allowedNames.size
  ) {
    return null
  }

  const positions = {}

  for (
    let i = 0;
    i < payload.names.length;
    i += 1
  ) {
    const name = payload.names[i]
    const value = payload.positions_rad[i]

    if (
      typeof name !== 'string' ||
      !allowedNames.has(name) ||
      !Number.isFinite(value) ||
      Object.hasOwn(positions, name)
    ) {
      return null
    }

    positions[name] = value
  }

  return Object.keys(positions).length === allowedNames.size
    ? positions
    : null
}

// mqtt_bridge가 joint_state_broadcaster의 M0609 6축만 robot/joints로 보낸다.
export function parseRobotJoints(payload) {
  return parseNamedSnapshot(
    payload,
    ARM_JOINTS
  )
}

// joint_state_publisher가 합성한 12축 메시지에서 RG2 6축만 분리해 보낸다.
export function parseGripperJoints(payload) {
  return parseNamedSnapshot(
    payload,
    RG2_JOINTS
  )
}
