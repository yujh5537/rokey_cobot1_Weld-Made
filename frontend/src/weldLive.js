// During WELD_PATH, project the visible probe tip onto the saved seam.
// Physical contact is not required; sparks stay on the finite edge.

const ACTIVE_PHASES = new Set(['PREPARING', 'APPROACH', 'WELDING', 'RETREAT', 'HOMING', 'STOPPING'])
const BEAD_STEP_M = 0.00025

export function updateWeldState(previous, message) {
  const runId = message.weld_id || ''
  const changedRun = Boolean(runId && runId !== previous?.run_id)
  const phase = message.phase || 'IDLE'
  return {
    ...previous,
    ...message,
    run_id: runId,
    line: message.line_index ?? previous?.line ?? 0,
    active: ACTIVE_PHASES.has(phase),
    arc: phase === 'WELDING',
    contact: null,
    beads: changedRun ? [] : previous?.beads ?? [],
  }
}

export function contactPoint(state, sample, tipWorldM, scanResult, fixtureOriginMm) {
  if (!state?.arc || !sample || !tipWorldM || !scanResult || !fixtureOriginMm ||
      state.scan_id !== scanResult.scan_id || sample.frameId !== 'base_link' ||
      sample.operation !== 'WELD_PATH' || !Number.isInteger(state.motion_id) ||
      state.motion_id <= 0 || sample.motionId !== state.motion_id) return null

  const line = state.line
  if (!Number.isInteger(line) || line < 0 || line > 7) return null
  const edge = scanResult.edges?.[line < 4 ? line : line + 4]
  if (!edge?.valid || !edge.start || !edge.end) return null

  const start = [edge.start.x_mm, edge.start.y_mm, edge.start.z_mm]
  const end = [edge.end.x_mm, edge.end.y_mm, edge.end.z_mm]
  const origin = [fixtureOriginMm.x, fixtureOriginMm.y, fixtureOriginMm.z]
  const tip = [tipWorldM.x, tipWorldM.y, tipWorldM.z]
  if (![...start, ...end, ...origin, ...tip].every(Number.isFinite)) return null
  const a = start.map((value, i) => (value + origin[i]) / 1000)
  const b = end.map((value, i) => (value + origin[i]) / 1000)
  const direction = b.map((value, i) => value - a[i])
  const lengthSquared = direction.reduce((sum, value) => sum + value * value, 0)
  if (lengthSquared <= 0) return null
  const projection = tip.reduce((sum, value, i) => sum + (value - a[i]) * direction[i], 0)
  const t = Math.max(0, Math.min(1, projection / lengthSquared))
  const nearest = a.map((value, i) => value + t * direction[i])
  return [...nearest, line]
}

export function appendWeldSample(state, sample, tipWorldM, scanResult, fixtureOriginMm) {
  if (!state) return state
  const contact = contactPoint(state, sample, tipWorldM, scanResult, fixtureOriginMm)
  if (!contact) return state.contact ? { ...state, contact: null } : state
  const last = state.beads.at(-1)
  const step = last && last[3] === contact[3]
    ? Math.hypot(...contact.slice(0, 3).map((value, i) => value - last[i]))
    : Infinity
  return {
    ...state,
    contact,
    beads: step < BEAD_STEP_M ? state.beads : [...state.beads.slice(-4999), contact],
  }
}
