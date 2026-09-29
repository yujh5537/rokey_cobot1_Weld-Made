// All visual positions use one world frame. Robot samples are relative to
// base_link; fixture vertices are relative to the fixture origin.
export const TABLE_HEIGHT_MM = 94

export function robotBaseWorldMm(tableTopWorldMm) {
  return { x: 0, y: 0, z: tableTopWorldMm.z - TABLE_HEIGHT_MM }
}

export function basePointWorldMm(point, baseWorldMm) {
  return {
    x: point.x + baseWorldMm.x,
    y: point.y + baseWorldMm.y,
    z: point.z + baseWorldMm.z,
  }
}

export function fixtureRelativeToBaseMm(fixtureWorldMm, baseWorldMm) {
  return {
    x: fixtureWorldMm.x - baseWorldMm.x,
    y: fixtureWorldMm.y - baseWorldMm.y,
    z: fixtureWorldMm.z - baseWorldMm.z,
  }
}

export function fixturePointWorldMm(point, fixtureWorldMm) {
  return {
    x: point.x_mm + fixtureWorldMm.x,
    y: point.y_mm + fixtureWorldMm.y,
    z: point.z_mm + fixtureWorldMm.z,
  }
}
