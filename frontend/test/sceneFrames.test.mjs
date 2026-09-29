import test from 'node:test'
import assert from 'node:assert/strict'
import { TABLE_HEIGHT_MM, basePointWorldMm, fixturePointWorldMm, fixtureRelativeToBaseMm, robotBaseWorldMm } from '../src/sceneFrames.js'

test('standard Virtual scene maps robot base, axes, TCP and fixture to one frame', () => {
  const table = { x: 425, y: -184, z: 400 }
  const base = robotBaseWorldMm(table)
  assert.equal(TABLE_HEIGHT_MM, 94)
  assert.deepEqual(base, { x: 0, y: 0, z: 306 })
  assert.deepEqual(basePointWorldMm({ x: 0, y: 0, z: 0 }, base), base)
  const fixtureInBase = fixtureRelativeToBaseMm(table, base)
  assert.deepEqual(fixtureInBase, { x: 425, y: -184, z: 94 })
  assert.deepEqual(basePointWorldMm(fixtureInBase, base), table)
  assert.deepEqual(fixturePointWorldMm({ x_mm: 0, y_mm: 0, z_mm: 40 }, table),
    { x: 425, y: -184, z: 440 })
})

test('DB scene keeps the measured table and fixture in the same frame', () => {
  const table = { x: 420.255, y: -156.675, z: 95.006 }
  const base = robotBaseWorldMm(table)
  const fixtureInBase = fixtureRelativeToBaseMm(table, base)
  assert.ok(Math.abs(base.z - 1.006) < 1e-9)
  assert.ok(Math.abs(fixtureInBase.z - 94) < 1e-9)
})
