import test from 'node:test'
import assert from 'node:assert/strict'
import { appendWeldSample, updateWeldState } from '../src/weldLive.js'

const fixture = {
  scan_id: 'fixture',
  edges: Array.from({ length: 12 }, (_, i) => ({
    valid: true,
    start: { x_mm: i, y_mm: i * 2, z_mm: 40 },
  })),
}
const origin = { x: 425, y: -184, z: 400 }

test('P4 phase and run changes control the effect', () => {
  const welding = updateWeldState(null, {
    weld_id: 'w1', scan_id: 'fixture', phase: 'WELDING', line_index: 0,
  })
  assert.equal(welding.arc, true)
  assert.equal(welding.active, true)
  const done = updateWeldState({ ...welding, beads: [[1, 2, 3, 0]] }, {
    weld_id: 'w1', scan_id: 'fixture', phase: 'DONE', line_index: 7,
  })
  assert.equal(done.arc, false)
  assert.equal(done.beads.length, 1)
  const next = updateWeldState(done, {
    weld_id: 'w2', scan_id: 'fixture', phase: 'PREPARING', line_index: 0,
  })
  assert.deepEqual(next.beads, [])
  assert.deepEqual(next.anchors, {})
})

test('top bead begins on the saved seam and follows TCP weave', () => {
  const state = updateWeldState(null, {
    weld_id: 'w1', scan_id: 'fixture', phase: 'WELDING', line_index: 0,
  })
  const first = appendWeldSample(state, { x: 500, y: -150, z: 450 }, fixture, origin)
  assert.deepEqual(first.beads[0].map((n) => Number(n.toFixed(6))), [0.425, -0.184, 0.4403, 0])
  const next = appendWeldSample(first, { x: 502, y: -148, z: 450 }, fixture, origin)
  assert.equal(next.beads.length, 2)
  assert.equal(next.beads[1][0], 0.427)
  assert.equal(next.beads[1][1], -0.182)
})

test('vertical bead uses edge 8 and stops when welding phase ends', () => {
  const welding = updateWeldState(null, {
    weld_id: 'w1', scan_id: 'fixture', phase: 'WELDING', line_index: 4,
  })
  const first = appendWeldSample(welding, { x: 500, y: -150, z: 450 }, fixture, origin)
  assert.equal(first.beads[0][0], 0.433)
  assert.equal(first.beads[0][2], 0.44)
  const stopped = updateWeldState(first, {
    weld_id: 'w1', scan_id: 'fixture', phase: 'STOPPED', line_index: 4,
  })
  assert.equal(appendWeldSample(stopped, { x: 501, y: -150, z: 449 }, fixture, origin).beads.length, 1)
})
