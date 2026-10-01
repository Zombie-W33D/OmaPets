// Adapted from OpenPets pet-motion-engine + community walkabout (MIT),
// source revision 2d14120cf027c9e80db7ff78e60711be08d39df4.
// Pure functions so the hosted QML renderer and Node regression tests agree.
var GRAVITY_PER_TICK = 1.1
var MAX_FALL_SPEED = 24
var BOUNCE_THRESHOLD = 6
var WANDER_DISTANCE = 120
var SPEED_DURATION = { slow: 2250, normal: 1375, brisk: 750 }

function tossGravityScale(elapsedMs) {
  if (!Number.isFinite(elapsedMs) || elapsedMs < 0) return 1
  return 0.5 + 0.5 * Math.min(1, elapsedMs / 2000)
}

function gravityStep(y, vy, floor, bounce, gravityScale) {
  var ground = Number.isFinite(floor) ? Math.max(0, floor) : 0
  if (!Number.isFinite(y) || y > ground) return { y: ground, vy: 0 }
  var position = Math.max(0, y)
  var velocity = Number.isFinite(vy) ? vy : 0
  if (position === ground && velocity === 0) return { y: ground, vy: 0 }
  var elasticity = Number.isFinite(bounce) ? Math.max(0, Math.min(1, bounce)) : 0.4
  var pull = Number.isFinite(gravityScale) ? Math.max(0.5, Math.min(1, gravityScale)) : 1
  velocity = Math.min(velocity + GRAVITY_PER_TICK * pull, MAX_FALL_SPEED)
  position += velocity
  if (position < 0) {
    position = 0
    velocity = 0
  }
  if (position >= ground) {
    position = ground
    velocity = Math.abs(velocity) > BOUNCE_THRESHOLD && elasticity > 0
      ? -velocity * elasticity : 0
  }
  return { y: position, vy: velocity }
}

function petIdentity(profile) {
  if (!profile || !profile.id || !profile.petId) return ""
  return JSON.stringify([profile.id, profile.petId, profile.screen || ""])
}

function releaseVelocity(samples, x, y, now) {
  var zero = { vx: 0, vy: 0 }
  if (!Array.isArray(samples) || !Number.isFinite(x) || !Number.isFinite(y)
      || !Number.isFinite(now)) return zero
  var oldest = null
  for (var i = 0; i < samples.length; i++) {
    var sample = samples[i]
    if (!sample || !Number.isFinite(sample.x) || !Number.isFinite(sample.y)
        || !Number.isFinite(sample.t) || sample.t > now || now - sample.t > 120) continue
    if (!oldest || sample.t < oldest.t) oldest = sample
  }
  if (!oldest || now <= oldest.t) return zero
  var tickFactor = 14.4 / (now - oldest.t) // 90% of pointer speed over one 16ms tick
  return {
    vx: Math.max(-18, Math.min(18, (x - oldest.x) * tickFactor)),
    vy: Math.max(-21.6, Math.min(21.6, (y - oldest.y) * tickFactor))
  }
}

function horizontalStep(x, vx, width, petWidth) {
  var right = Number.isFinite(width) && Number.isFinite(petWidth)
    ? Math.max(0, width - petWidth) : 0
  var current = Number.isFinite(x) ? Math.max(0, Math.min(right, x)) : 0
  var speed = Number.isFinite(vx) ? vx : 0
  if (Math.abs(speed) < 0.25) return { x: current, vx: 0 }
  var next = Math.max(0, Math.min(right, current + speed))
  return { x: next, vx: next === 0 || next === right ? 0 : speed * 0.92 }
}

function wanderTarget(x, width, petWidth, direction) {
  var right = Number.isFinite(width) && Number.isFinite(petWidth)
    ? Math.max(0, width - petWidth) : 0
  var current = Number.isFinite(x) ? Math.max(0, Math.min(right, x)) : 0
  var step = direction < 0 ? -WANDER_DISTANCE : WANDER_DISTANCE
  var target = Math.max(0, Math.min(right, current + step))
  if (target === current) target = Math.max(0, Math.min(right, current - step))
  return target
}

function speedDuration(speed) {
  return Object.prototype.hasOwnProperty.call(SPEED_DURATION, speed)
    ? SPEED_DURATION[speed] : SPEED_DURATION.slow
}

function frameInterval(airborne, walking, category) {
  var original = airborne ? 168 : walking && category === "idle" ? 132
    : category === "idle" ? 900 : 180
  return Math.round(original / 1.2)
}

// OpenPets V1/V2 defines jumping, not a distinct falling row. An airborne
// pet uses jumping frames; unsupported atlases remain on the idle row.
function airborneAnimation(rows) {
  return rows >= 5 ? { row: 4, frames: 5 } : { row: 0, frames: 6 }
}
