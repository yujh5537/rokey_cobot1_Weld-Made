// P4 weld/state and robot/sample are the only sources for the live effect.
// Positions are Base millimetres at the MQTT boundary; weldEffect uses metres.
const ACTIVE_PHASES = new Set(['PREPARING', 'APPROACH', 'WELDING', 'RETREAT', 'HOMING', 'STOPPING'])

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
    beads: changedRun ? [] : previous?.beads ?? [],
    anchors: changedRun ? {} : previous?.anchors ?? {},
  }
}

export function appendWeldSample(state, sample, scanResult, fixtureOriginMm) {
  if (!state?.arc || !sample || !scanResult || !fixtureOriginMm ||
      state.scan_id !== scanResult.scan_id) return state
  const line = state.line
  const edge = scanResult.edges?.[line < 4 ? line : line + 4]
  const start = edge?.start
  if (!Number.isInteger(line) || line < 0 || line > 7 || !edge?.valid || !start ||
      ![sample.x, sample.y, sample.z, start.x_mm, start.y_mm, start.z_mm]
        .every(Number.isFinite)) return state

  const anchor = state.anchors[line] ?? sample
  const x = fixtureOriginMm.x + start.x_mm + sample.x - anchor.x
  const y = fixtureOriginMm.y + start.y_mm + sample.y - anchor.y
  const z = line < 4
    ? fixtureOriginMm.z + start.z_mm + 0.3
    : fixtureOriginMm.z + start.z_mm + sample.z - anchor.z
  const bead = [x / 1000, y / 1000, z / 1000, line]
  const last = state.beads.at(-1)
  const step = last ? Math.hypot(bead[0] - last[0], bead[1] - last[1], bead[2] - last[2]) : Infinity
  if (step < 0.0004) return state
  return {
    ...state,
    anchors: { ...state.anchors, [line]: anchor },
    beads: [...state.beads.slice(-4999), bead],
  }
}
