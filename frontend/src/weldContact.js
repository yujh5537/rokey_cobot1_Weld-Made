// Both segments are in world metres. Return the edge fraction nearest the
// finite probe shaft, accounting for its angle and both endpoints.
const subtract = (a, b) => a.map((value, i) => value - b[i])
const dot = (a, b) => a.reduce((sum, value, i) => sum + value * b[i], 0)
const clamp = (value) => Math.max(0, Math.min(1, value))

export function closestEdgeParameter(a, b, probe) {
  if (!probe?.start || !probe?.end) return null
  const p = [probe.start.x, probe.start.y, probe.start.z]
  const q = [probe.end.x, probe.end.y, probe.end.z]
  if (![...a, ...b, ...p, ...q].every(Number.isFinite)) return null
  const u = subtract(b, a)
  const v = subtract(q, p)
  const w = subtract(a, p)
  const A = dot(u, u)
  const B = dot(u, v)
  const C = dot(v, v)
  const D = dot(u, w)
  const E = dot(v, w)
  if (A <= 1e-20) return null

  // The minimum lies inside both segments or on one of the four boundaries.
  // Prefer the tip in ties (parallel/overlapping segments).
  const candidates = [
    [clamp((B - D) / A), 1],
    [clamp(-D / A), 0],
    [0, C > 1e-20 ? clamp(E / C) : 0],
    [1, C > 1e-20 ? clamp((E + B) / C) : 0],
  ]
  const determinant = A * C - B * B
  if (determinant > 1e-12 * A * C) {
    const t = (B * E - C * D) / determinant
    const s = (A * E - B * D) / determinant
    if (t >= 0 && t <= 1 && s >= 0 && s <= 1) candidates.push([t, s])
  }
  let closest = null
  let bestDistance = Infinity
  for (const [t, s] of candidates) {
    const difference = w.map((value, i) => value + t * u[i] - s * v[i])
    const distance = dot(difference, difference)
    if (distance < bestDistance) {
      bestDistance = distance
      closest = t
    }
  }
  return closest
}
