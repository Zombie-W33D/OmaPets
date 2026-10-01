// Adapted from OpenPets pet-motion-engine + community walkabout (MIT),
// source revision 2d14120cf027c9e80db7ff78e60711be08d39df4.
// Pure functions so the hosted QML renderer and Node regression tests agree.
var GRAVITY_PER_TICK = 1.1
var MAX_FALL_SPEED = 24
var BOUNCE_THRESHOLD = 6
var WANDER_DISTANCE = 120
var SPEED_DURATION = { slow: 2250, normal: 1375, brisk: 750 }
var CATEGORY_ANIMATION_SPEED = { working: 0.8 }

function tossGravityScale(elapsedMs) {
  if (!Number.isFinite(elapsedMs) || elapsedMs < 0) return 1
  return 0.5 + 0.5 * Math.min(1, elapsedMs / 3000)
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

function validSurface(surface, x, petWidth) {
  return surface && Number.isFinite(surface.x) && Number.isFinite(surface.y)
    && Number.isFinite(surface.width) && surface.width > 0
    && Number.isFinite(x) && Number.isFinite(petWidth) && petWidth > 0
    && x + petWidth / 2 > surface.x
    && x + petWidth / 2 < surface.x + surface.width
}

function contactHeight(petHeight) {
  return Number.isFinite(petHeight) && petHeight > 0 ? petHeight * 0.95 : 0
}
function landingSurface(fromY, toY, x, petWidth, petHeight, surfaces) {
  if (!Array.isArray(surfaces) || !Number.isFinite(fromY) || !Number.isFinite(toY)
      || !Number.isFinite(petHeight) || petHeight <= 0 || toY <= fromY) return null
  var contact = contactHeight(petHeight)
  var hit = null
  for (var i = 0; i < surfaces.length; i++) {
    var surface = surfaces[i]
    if (!validSurface(surface, x, petWidth)) continue
    var top = surface.y - contact
    if (fromY + contact <= surface.y && toY + contact >= surface.y
        && (!hit || top < hit.y - contact)) hit = surface
  }
  return hit
}

function supportAt(y, x, petWidth, petHeight, surfaces) {
  if (!Array.isArray(surfaces) || !Number.isFinite(y) || !Number.isFinite(petHeight)) return null
  for (var i = 0; i < surfaces.length; i++) {
    var surface = surfaces[i]
    if (validSurface(surface, x, petWidth) && Math.abs(y + contactHeight(petHeight) - surface.y) < 1)
      return surface
  }
  return null
}

function wanderOnSurface(current, target, surface, petWidth) {
  if (!surface || !Number.isFinite(surface.x) || !Number.isFinite(surface.width)
      || !Number.isFinite(petWidth) || surface.width < petWidth) return current
  return Math.max(surface.x, Math.min(surface.x + surface.width - petWidth, target))
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
  var elapsed = now - oldest.t
  var horizontalFactor = 17.28 / elapsed // 108% of pointer speed over one 16ms tick
  var verticalFactor = 12.24 / elapsed   // 76.5% of pointer speed over one 16ms tick
  return {
    vx: Math.max(-21.6, Math.min(21.6, (x - oldest.x) * horizontalFactor)),
    vy: Math.max(-18.36, Math.min(18.36, (y - oldest.y) * verticalFactor))
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
  var original = airborne ? 168 : walking ? 132
    : category === "idle" ? 900 : 180
  var speed = !airborne && !walking && CATEGORY_ANIMATION_SPEED[category]
    ? CATEGORY_ANIMATION_SPEED[category] : 1
  return Math.round(original / 1.2 / speed)
}

function heldAnimation(rows, columns) {
  var count = Number.isFinite(columns) ? Math.max(1, Math.floor(columns)) : 1
  return rows >= 5 && count >= 5
    ? { row: 4, frames: 5 } : { row: 0, frames: Math.min(6, count) }
}

function gripPosition(x, y, width, height, petWidth, petHeight) {
  var right = Number.isFinite(width) && Number.isFinite(petWidth)
    ? Math.max(0, width - petWidth) : 0
  var bottom = Number.isFinite(height) && Number.isFinite(petHeight)
    ? Math.max(0, height - petHeight) : 0
  return {
    x: Number.isFinite(x) ? Math.max(0, Math.min(right, x - petWidth / 2)) : 0,
    y: Number.isFinite(y) ? Math.max(0, Math.min(bottom, y - (Number.isFinite(petHeight) ? petHeight * 0.1 : 0))) : 0
  }
}

function heldFacing(previousX, currentX, wasFacingLeft) {
  if (!Number.isFinite(previousX) || !Number.isFinite(currentX)) return !!wasFacingLeft
  return Math.abs(currentX - previousX) > 1 ? currentX > previousX : !!wasFacingLeft
}

function heldSway(deltaX) {
  return Number.isFinite(deltaX) && deltaX !== 0
    ? Math.max(-10, Math.min(10, -0.5 * deltaX)) : 0
}

function settleSway(angle) {
  return Number.isFinite(angle) && Math.abs(angle) > 0.25 ? angle * 0.6 : 0
}

function heldFrame(phase, moving) {
  var swing = [2, 3, 2, 1]
  var squirm = [2, 3, 4, 3, 2, 1, 0, 1]
  var sequence = moving ? swing : squirm
  var index = Number.isFinite(phase) ? Math.max(0, Math.floor(phase)) : 0
  return sequence[index % sequence.length]
}

// OpenPets V1/V2 defines jumping, not a distinct falling row. An airborne
// pet uses jumping frames; unsupported atlases remain on the idle row.
function airborneAnimation(rows) {
  return rows >= 5 ? { row: 4, frames: 5 } : { row: 0, frames: 6 }
}
