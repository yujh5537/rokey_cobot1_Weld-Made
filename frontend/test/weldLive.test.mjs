import test from 'node:test'
import assert from 'node:assert/strict'
import { appendWeldSample, contactPoint, updateWeldState } from '../src/weldLive.js'

const origin = { x: 425, y: -184, z: 400 }
const edges = Array.from({ length: 12 }, () => ({ valid: false }))
edges[0] = {
  valid: true,
  start: { x_mm: 0, y_mm: 0, z_mm: 40 },
  end: { x_mm: 100, y_mm: 0, z_mm: 40 },
}
edges[8] = {
  valid: true,
  start: { x_mm: 0, y_mm: 0, z_mm: 40 },
  end: { x_mm: 0, y_mm: 0, z_mm: 0 },
}
const fixture = { scan_id: 'fixture', edges }
const sample = { frameId: 'base_link', operation: 'WELD_PATH', motionId: 51 }
const welding = (line = 0) => updateWeldState(null, {
  weld_id: 'w1', scan_id: 'fixture', phase: 'WELDING', line_index: line, motion_id: 51,
})

test('arc and beads require the visible probe sphere to touch the saved seam', () => {
  let state = welding()
  const above = { x: 0.45, y: -0.184, z: 0.443 }
  assert.equal(contactPoint(state, sample, above, fixture, origin), null)
  state = appendWeldSample(state, sample, above, fixture, origin)
  assert.equal(state.beads.length, 0)
  assert.equal(state.contact, null)

  const touching = { x: 0.45, y: -0.184, z: 0.4401 }
  state = appendWeldSample(state, sample, touching, fixture, origin)
  assert.deepEqual(state.contact, [0.45, -0.184, 0.44, 0])
  assert.deepEqual(state.beads, [[0.45, -0.184, 0.44, 0]])
  state = appendWeldSample(state, sample, above, fixture, origin)
  assert.equal(state.contact, null)
  assert.equal(state.beads.length, 1)
})

test('corner contact clamps to the endpoint; past the corner has no effect', () => {
  const state = welding()
  assert.deepEqual(contactPoint(state, sample, {
    x: 0.425, y: -0.184, z: 0.44,
  }, fixture, origin), [0.425, -0.184, 0.44, 0])
  assert.equal(contactPoint(state, sample, {
    x: 0.424, y: -0.184, z: 0.44,
  }, fixture, origin), null)
})

test('effect follows the vertical edge 8 in world coordinates', () => {
  const state = welding(4)
  assert.deepEqual(contactPoint(state, sample, {
    x: 0.425, y: -0.184, z: 0.42,
  }, fixture, origin), [0.425, -0.184, 0.42, 4])
})

test('another motion, frame, scan or phase cannot light the arc', () => {
  const state = welding()
  const tip = { x: 0.45, y: -0.184, z: 0.44 }
  assert.equal(contactPoint(state, { ...sample, motionId: 52 }, tip, fixture, origin), null)
  assert.equal(contactPoint(state, { ...sample, operation: 'HOME' }, tip, fixture, origin), null)
  assert.equal(contactPoint(state, { ...sample, frameId: 'other' }, tip, fixture, origin), null)
  assert.equal(contactPoint({ ...state, scan_id: 'other' }, sample, tip, fixture, origin), null)
  const stopped = updateWeldState(state, {
    weld_id: 'w1', scan_id: 'fixture', phase: 'STOPPED', line_index: 0, motion_id: 0,
  })
  assert.equal(contactPoint(stopped, sample, tip, fixture, origin), null)
})

test('new weld clears the old bead and contact', () => {
  const old = { ...welding(), beads: [[0.45, -0.184, 0.44, 0]], contact: [0.45, -0.184, 0.44, 0] }
  const next = updateWeldState(old, {
    weld_id: 'w2', scan_id: 'fixture', phase: 'PREPARING', line_index: 0, motion_id: 0,
  })
  assert.deepEqual(next.beads, [])
  assert.equal(next.contact, null)
})

test('Three probe position maps to the same world coordinates as the fixture', async () => {
  const { threePointWorldM } = await import('../src/sceneFrames.js')
  const tipWorld = threePointWorldM({ x: 4.5, y: 4.4, z: 1.84 })
  assert.deepEqual(tipWorld, { x: 0.45, y: -0.184, z: 0.44000000000000006 })
  assert.deepEqual(contactPoint(welding(), sample, tipWorld, fixture, origin),
    [0.45, -0.184, 0.44, 0])
})
