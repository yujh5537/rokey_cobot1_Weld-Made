import { closestEdgeParameter } from './weldContact.js'

// During WELD_PATH, top seams use TCP projection; vertical seams use the
// nearest point between the displayed shaft segment and the finite edge.
// This estimates visual contact from geometry; it does not confirm physical contact.

const ACTIVE_PHASES = new Set(['PREPARING', 'APPROACH', 'WELDING', 'RETREAT', 'HOMING', 'STOPPING'])
const BEAD_STEP_M = 0.00025
const WELD_STATE_MAX_AGE_MS = 2500

export function updateWeldState(previous, message, scanResult, fixtureOriginMm, bottomWorldMm) {
  const runId = message.weld_id || ''
  const changedRun = Boolean(runId && runId !== previous?.run_id)
  const phase = message.phase || 'IDLE'
  const sameScan = Boolean(previous?.scan_id && previous.scan_id === message.scan_id)
  const next = {
    ...previous,
    ...message,
    run_id: runId,
    receivedAt: performance.now(),
    line: message.line_index ?? previous?.line ?? 0,
    active: ACTIVE_PHASES.has(phase),
    arc: phase === 'WELDING',
    contact: null,
    startedMotionId: changedRun ? null : previous?.startedMotionId ?? null,
    beads: sameScan ? previous?.beads ?? [] : [],
    painted: sameScan ? previous?.painted ?? {} : {},
    verticalBeads: sameScan ? previous?.verticalBeads ?? {} : {},
  }
  if (phase === 'WELDING' && next.line >= 4 && next.line <= 7 &&
      Number.isFinite(message.line_progress) && message.line_progress >= 1) {
    paintBead(next, next.line, 1, scanResult, fixtureOriginMm, bottomWorldMm)
  }
  // lines_done is the backend confirmation; retreat alone may follow a failure.
  if (!changedRun && sameScan && message.lines_done > (previous?.lines_done ?? 0)) {
    paintBead(next, previous.line, 1, scanResult, fixtureOriginMm, bottomWorldMm)
  }
  return next
}

// Final results identify completed lines even when an intermediate state was missed.
export function applyWeldResult(state, result, scanResult, fixtureOriginMm, bottomWorldMm) {
  if (!state || result.weld_id !== state.run_id || result.scan_id !== state.scan_id ||
      result.scan_id !== scanResult?.scan_id || !Array.isArray(result.lines)) return state
  const next = { ...state, arc: false, contact: null }
  for (const line of result.lines) {
    if (line.status === 'DONE') {
      paintBead(next, line.index, 1, scanResult, fixtureOriginMm, bottomWorldMm)
    }
  }
  return next
}

// Gray beads follow the same projected TCP position as the spark glow.
function paintBead(state, line, progress, scanResult, fixtureOriginMm, bottomWorldMm) {
  if (!Number.isInteger(line) || line < 0 || line > 7 ||
      !Number.isFinite(progress) || progress <= 0 || !fixtureOriginMm ||
      state.scan_id !== scanResult?.scan_id) return
  const edge = scanResult.edges?.[line < 4 ? line : line + 4]
  if (!edge?.valid || !edge.start || !edge.end) return
  const origin = [fixtureOriginMm.x, fixtureOriginMm.y, fixtureOriginMm.z]
  const a = [edge.start.x_mm, edge.start.y_mm, edge.start.z_mm]
    .map((v, i) => (v + origin[i]) / 1000)
  const b = [edge.end.x_mm, edge.end.y_mm, edge.end.z_mm]
    .map((v, i) => (v + origin[i]) / 1000)
  if (line >= 4 && Number.isFinite(bottomWorldMm)) b[2] = bottomWorldMm / 1000
  if (![...a, ...b].every(Number.isFinite)) return
  const end = Math.min(1, progress)
  const start = state.painted?.[line] ?? 0
  if (line >= 4) {
    const filled = Math.max(start, end)
    state.verticalBeads = { ...state.verticalBeads, [line]: {
      start: a,
      end: a.map((value, i) => value + filled * (b[i] - value)),
    } }
    state.painted = { ...state.painted, [line]: filled }
    return
  }
  if (end <= start) return
  const length = Math.hypot(...b.map((v, i) => v - a[i]))
  // Use a fixed grid along each edge. Small progress updates must not add
  // one bead per frame and exhaust the shared 5,000-instance capacity.
  // At most 601 points per line: all eight complete edges fit in 5,000 instances.
  const divisions = Math.min(600, Math.max(1, Math.ceil(length / BEAD_STEP_M)))
  const firstIndex = state.painted?.[line] === undefined
    ? 0 : Math.floor(start * divisions) + 1
  const lastIndex = end === 1 ? divisions : Math.floor(end * divisions)
  const added = []
  for (let i = firstIndex; i <= lastIndex; i++) {
    const t = i / divisions
    added.push([...a.map((v, axis) => v + (b[axis] - v) * t), line])
  }
  state.beads = [...state.beads, ...added].slice(0, 5000)
  state.painted = { ...state.painted, [line]: end }
}

export function contactPoint(state, sample, tipWorldM, scanResult, fixtureOriginMm, bottomWorldMm, probeSegment) {
  if (!state?.arc || state.phase !== 'WELDING' ||
      !Number.isFinite(state.receivedAt) || performance.now() - state.receivedAt > WELD_STATE_MAX_AGE_MS ||
      !sample || !tipWorldM || !scanResult || !fixtureOriginMm ||
      state.scan_id !== scanResult.scan_id || sample.frameId !== 'base_link' ||
      sample.operation !== 'WELD_PATH' || !Number.isInteger(state.motion_id) ||
      state.motion_id <= 0 || sample.motionId !== state.motion_id ||
      !Number.isFinite(state.line_progress) || state.line_progress <= 0 || state.line_progress >= 1) return null

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
  if (line >= 4 && Number.isFinite(bottomWorldMm)) b[2] = bottomWorldMm / 1000
  const direction = b.map((value, i) => value - a[i])
  const lengthSquared = direction.reduce((sum, value) => sum + value * value, 0)
  if (lengthSquared <= 0) return null
  const projection = tip.reduce((sum, value, i) => sum + (value - a[i]) * direction[i], 0)
  const t = line >= 4
    ? closestEdgeParameter(a, b, probeSegment)
    : Math.max(0, Math.min(1, projection / lengthSquared))
  if (t === null) return null
  const nearest = a.map((value, i) => value + t * direction[i])
  return [...nearest, line, t]
}

export function appendWeldSample(state, sample, tipWorldM, scanResult, fixtureOriginMm, bottomWorldMm, probeSegment) {
  if (!state) return state
  const contact = contactPoint(state, sample, tipWorldM, scanResult, fixtureOriginMm, bottomWorldMm, probeSegment)
  const next = { ...state, contact,
    startedMotionId: contact ? state.motion_id : state.startedMotionId }
  if (state.arc && contact) {
    paintBead(next, state.line, contact[4], scanResult, fixtureOriginMm, bottomWorldMm)
  }
  return next
}
