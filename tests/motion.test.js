const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// The exact same dependency-free JavaScript is imported by PetWindow.qml.
const source = fs.readFileSync(path.join(__dirname, '..', 'Motion.js'), 'utf8');
const windowSource = fs.readFileSync(path.join(__dirname, '..', 'PetWindow.qml'), 'utf8');
const motion = vm.createContext({ Math, Number });
vm.runInContext(source, motion);

test('a newly visible pet starts at the top of its selected monitor', () => {
  assert.match(windowSource, /function resetPhysics\(\)\s*\{[^}]*fallY\s*=\s*profile\s*&&\s*profile\.pet\s*&&\s*height\s*>\s*0\s*\?\s*0\s*:\s*-1/s);
});

test('a pet has no saved-height flash before the first physics tick', () => {
  assert.match(windowSource, /readonly property real petY:\s*dragY\s*>=\s*0\s*\?\s*dragY\s*:\s*\(fallY\s*>=\s*0\s*\?\s*fallY\s*:\s*0\)/);
});

test('horizontal easing remains disabled until the pet lands', () => {
  assert.match(windowSource, /Behavior on x\s*\{\s*enabled:\s*root\.grounded\s*&&\s*root\.profile\s*&&\s*root\.profile\.mode\s*===\s*"wander"/);
});

test('a position write keeps the same visible pet identity', () => {
  const original = { id: 'codedump', petId: 'krang-box', screen: 'DP-1', position: { x: 0.5, y: 0.3 } };
  const moved = { ...original, position: { x: 0.8, y: 0.1 }, mode: 'stay' };
  assert.equal(motion.petIdentity(original), motion.petIdentity(moved));
  assert.notEqual(motion.petIdentity(original), motion.petIdentity({ ...original, petId: 'socksy' }));
  assert.notEqual(motion.petIdentity(original), motion.petIdentity({ ...original, screen: 'DP-2' }));
  assert.equal(motion.petIdentity(null), '');
});

test('same-pet settings refresh does not restart a toss at the top', () => {
  const handler = windowSource.split('onProfileChanged: {')[1]?.split('onHeightChanged:')[0] || '';
  assert.match(handler, /var nextKey = Motion\.petIdentity\(profile\)/);
  assert.match(handler, /if \(nextKey !== renderedPetKey\) \{[\s\S]*Qt\.callLater\(root\.resetPhysics\)/);
});

test('release uses actual cursor location and momentum instead of snapping to saved placement', () => {
  const release = windowSource.split('onReleased: function(mouse) {')[1]?.split('onCanceled:')[0] || '';
  assert.match(release, /root\.dragX = Math\.max\(0, Math\.min\(root\.width - sprite\.width, point\.x - offsetX\)\)/);
  assert.match(release, /root\.dragY = Math\.max\(0, Math\.min\(root\.height - sprite\.height, point\.y - offsetY\)\)/);
  assert.match(release, /var now = Date\.now\(\)/);
  assert.match(release, /Motion\.releaseVelocity\(pointerSamples, point\.x, point\.y, now\)/);
  assert.match(release, /root\.tossStartedAtMs = now/);
  assert.match(release, /root\.roamX = root\.dragX/);
  assert.match(release, /root\.fallY = root\.dragY/);
  assert.match(release, /root\.velocityX = velocity\.vx/);
  assert.match(release, /root\.velocityY = velocity\.vy/);
  assert.match(release, /root\.dragX = -1/);
});

test('a recent pointer swipe gets another 20% launch speed over alpha.6', () => {
  const samples = [{ x: 100, y: 200, t: 1000 }, { x: 140, y: 180, t: 1040 }];
  const velocity = motion.releaseVelocity(samples, 150, 175, 1050);
  assert.ok(Math.abs(velocity.vx - 11.52) < 1e-9);
  assert.ok(Math.abs(velocity.vy + 5.76) < 1e-9);
  const paused = motion.releaseVelocity(samples, 150, 175, 1201);
  assert.equal(paused.vx, 0);
  assert.equal(paused.vy, 0);
  const fast = motion.releaseVelocity([{ x: 0, y: 0, t: 1000 }], 2000, -2000, 1001);
  assert.ok(Math.abs(fast.vx - 14.4) < 1e-9);
  assert.ok(Math.abs(fast.vy + 17.28) < 1e-9);
});

test('airborne horizontal momentum makes a short arc and stops at screen edges', () => {
  const step = motion.horizontalStep(200, 8, 1000, 100);
  assert.equal(step.x, 208);
  assert.ok(Math.abs(step.vx - 7.36) < 1e-9);
  const edge = motion.horizontalStep(895, 10, 1000, 100);
  assert.equal(edge.x, 900);
  assert.equal(edge.vx, 0);
  const stopped = motion.horizontalStep(200, 0.1, 1000, 100);
  assert.equal(stopped.x, 200);
  assert.equal(stopped.vx, 0);
});

test('the fall timer moves horizontally while airborne and stops momentum on landing', () => {
  const fallTick = windowSource.split('running: root.visible && root.fallY >= 0')[1]?.split('function startRoam()')[0] || '';
  assert.match(fallTick, /Motion\.horizontalStep\(root\.roamX >= 0 \? root\.roamX : root\.petX, root\.velocityX, root\.width, root\.pixelWidth\)/);
  assert.match(fallTick, /root\.roamX = lateral\.x/);
  assert.match(fallTick, /root\.velocityX = lateral\.vx/);
  assert.match(fallTick, /if \(root\.grounded\) root\.velocityX = 0/);
});

test('the fall timer gradually restores normal gravity only after a toss', () => {
  const fallTick = windowSource.split('running: root.visible && root.fallY >= 0')[1]?.split('function startRoam()')[0] || '';
  assert.match(fallTick, /var gravityScale = root\.tossStartedAtMs < 0 \? 1 : Motion\.tossGravityScale\(Date\.now\(\) - root\.tossStartedAtMs\)/);
  assert.match(fallTick, /Motion\.gravityStep\(root\.fallY, root\.velocityY, root\.groundY, 0\.4, gravityScale\)/);
});

test('toss gravity starts at half and returns to normal over five seconds', () => {
  assert.equal(motion.tossGravityScale(0), 0.5);
  assert.equal(motion.tossGravityScale(2500), 0.75);
  assert.equal(motion.tossGravityScale(5000), 1);
  assert.equal(motion.tossGravityScale(10000), 1);
  assert.equal(motion.tossGravityScale(-1), 1);
  assert.equal(motion.tossGravityScale(Number.NaN), 1);
});

test('tossed gravity scales acceleration without weakening the release speed or normal drops', () => {
  const half = motion.gravityStep(100, 0, 700, 0, 0.5);
  assert.ok(Math.abs(half.y - 100.55) < 1e-9);
  assert.ok(Math.abs(half.vy - 0.55) < 1e-9);
  const launched = motion.gravityStep(100, 17.28, 700, 0, 0.5);
  assert.ok(Math.abs(launched.vy - 17.83) < 1e-9);
  const cap = motion.gravityStep(100, 100, 700, 0, 0.5);
  assert.equal(cap.y, 124);
  assert.equal(cap.vy, 24);
  const normal = motion.gravityStep(100, 0, 700, 0);
  assert.equal(normal.y, 101.1);
  assert.equal(normal.vy, 1.1);
});

test('gravity accelerates, caps velocity and settles at the sprite-height floor', () => {
  let state = motion.gravityStep(100, 0, 700, 0);
  assert.equal(state.y, 101.1);
  assert.equal(state.vy, 1.1);
  let fastest = 0;
  for (let i = 0; i < 150; i++) {
    state = motion.gravityStep(state.y, state.vy, 700, 0);
    fastest = Math.max(fastest, state.vy);
  }
  assert.equal(state.y, 700);
  assert.equal(state.vy, 0);
  assert.equal(fastest, 24);
  const settled = motion.gravityStep(state.y, state.vy, 700, 0);
  assert.equal(settled.y, state.y);
  assert.equal(settled.vy, state.vy);
});

test('an upward throw meets the top edge and then falls back down', () => {
  const top = motion.gravityStep(2, -8, 700, 0.4);
  assert.equal(top.y, 0);
  assert.equal(top.vy, 0);
  const next = motion.gravityStep(top.y, top.vy, 700, 0.4);
  assert.ok(next.y > 0);
});

test('bounce loses energy, then settles with no floor jitter', () => {
  let state = { y: 100, vy: 0 };
  let bounced = false;
  for (let i = 0; i < 200; i++) {
    state = motion.gravityStep(state.y, state.vy, 700, 0.4);
    if (state.vy < 0) bounced = true;
  }
  assert.equal(bounced, true);
  assert.equal(state.y, 700);
  assert.equal(state.vy, 0);
});

test('invalid positions and a shrinking monitor cannot put a pet off-screen', () => {
  const invalid = motion.gravityStep(Number.NaN, 4, 500, 0.4);
  assert.equal(invalid.y, 500);
  assert.equal(invalid.vy, 0);
  const shrunk = motion.gravityStep(900, 20, 500, 0.4);
  assert.equal(shrunk.y, 500);
  assert.equal(shrunk.vy, 0);
});

test('wander uses OpenPets 120px steps and reverses at a monitor edge', () => {
  assert.equal(motion.wanderTarget(200, 1000, 100, 1), 320);
  assert.equal(motion.wanderTarget(900, 1000, 100, 1), 780);
  assert.equal(motion.wanderTarget(50, 1000, 100, -1), 0);
  assert.equal(motion.wanderTarget(20, 80, 100, 1), 0);
});

test('sprite frames play at 120% of their former cadence', () => {
  assert.equal(motion.frameInterval(true, false, 'idle'), 140);
  assert.equal(motion.frameInterval(false, true, 'idle'), 110);
  assert.equal(motion.frameInterval(false, false, 'idle'), 750);
  assert.equal(motion.frameInterval(false, false, 'thinking'), 150);
});

test('the frame timer uses the shared 120% animation cadence', () => {
  assert.match(windowSource, /id:\s*frameTick\s+interval:\s*Motion\.frameInterval\(root\.airborne,\s*root\.walking,\s*root\.category\)/);
});

test('OpenPets speed presets and airborne animation have a bounded fallback', () => {
  assert.equal(motion.speedDuration('slow'), 2250);
  assert.equal(motion.speedDuration('normal'), 1375);
  assert.equal(motion.speedDuration('brisk'), 750);
  assert.equal(motion.speedDuration('unknown'), 2250);
  const airborne = motion.airborneAnimation(9);
  assert.equal(airborne.row, 4);
  assert.equal(airborne.frames, 5);
  assert.equal(motion.airborneAnimation(3).row, 0);
});
