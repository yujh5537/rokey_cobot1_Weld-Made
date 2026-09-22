// Names may be plain joint_1, dsr01/joint_1 or dsr01_joint_1.
export function parseRobotJoints(payload) {
  if (!payload || !Array.isArray(payload.names) ||
      !Array.isArray(payload.positions_rad) ||
      payload.names.length !== payload.positions_rad.length) return null

  const positions = {}
  for (let i = 0; i < payload.names.length; i += 1) {
    const name = payload.names[i]
    if (typeof name !== 'string') return null
    const match = name.match(/^(?:.*[/_])?(joint_[1-6])$/)
    if (!match) continue // Ignore gripper and other non-arm joints.
    const key = match[1]
    const value = payload.positions_rad[i]
    if (!Number.isFinite(value) || Object.hasOwn(positions, key)) return null
    positions[key] = value
  }
  return Object.keys(positions).length === 6 ? positions : null
}
