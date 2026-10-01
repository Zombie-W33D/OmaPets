// Adapted from OpenPets pet-motion-engine + community walkabout (MIT),
// source revision 2d14120cf027c9e80db7ff78e60711be08d39df4.
// Pure functions so the hosted QML renderer and Node regression tests agree.
var GRAVITY_PER_TICK = 1.1
var MAX_FALL_SPEED = 24
var BOUNCE_THRESHOLD = 6
var WANDER_DISTANCE = 120
var SPEED_DURATION = { slow: 2250, normal: 1375, brisk: 750 }

function gravityStep(y, vy, floor, bounce) {
  var ground = Number.isFinite(floor) ? Math.max(0, floor) : 0
  if (!Number.isFinite(y) || y > ground) return { y: ground, vy: 0 }
  var position = Math.max(0, y)
  var velocity = Number.isFinite(vy) ? vy : 0
  if (position === ground && velocity === 0) return { y: ground, vy: 0 }
  var elasticity = Number.isFinite(bounce) ? Math.max(0, Math.min(1, bounce)) : 0.4
  velocity = Math.min(velocity + GRAVITY_PER_TICK, MAX_FALL_SPEED)
  position += velocity
  if (position >= ground) {
    position = ground
    velocity = Math.abs(velocity) > BOUNCE_THRESHOLD && elasticity > 0
      ? -velocity * elasticity : 0
  }
  return { y: position, vy: velocity }
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
