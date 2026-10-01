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
  assert.match(release, /var held = Motion\.gripPosition\(point\.x, point\.y, root\.width, root\.height, sprite\.width, sprite\.height\)/);
  assert.match(release, /root\.dragX = held\.x/);
  assert.match(release, /root\.dragY = held\.y/);
  assert.match(release, /var now = Date\.now\(\)/);
  assert.match(release, /Motion\.releaseVelocity\(pointerSamples, point\.x, point\.y, now\)/);
  assert.match(release, /root\.tossStartedAtMs = now/);
  assert.match(release, /root\.roamX = root\.dragX/);
  assert.match(release, /root\.fallY = root\.dragY/);
  assert.match(release, /root\.velocityX = velocity\.vx/);
  assert.match(release, /root\.velocityY = velocity\.vy/);
  assert.match(release, /root\.dragX = -1/);
});

test('a toss gains 20% horizontal speed and loses 15% vertical speed over alpha.8', () => {
  const samples = [{ x: 100, y: 200, t: 1000 }, { x: 140, y: 180, t: 1040 }];
  const velocity = motion.releaseVelocity(samples, 150, 175, 1050);
  assert.ok(Math.abs(velocity.vx - 17.28) < 1e-9);
  assert.ok(Math.abs(velocity.vy + 6.12) < 1e-9);
  const paused = motion.releaseVelocity(samples, 150, 175, 1201);
  assert.equal(paused.vx, 0);
  assert.equal(paused.vy, 0);
  const fast = motion.releaseVelocity([{ x: 0, y: 0, t: 1000 }], 2000, -2000, 1001);
  assert.ok(Math.abs(fast.vx - 21.6) < 1e-9);
  assert.ok(Math.abs(fast.vy + 18.36) < 1e-9);
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

test('toss gravity starts at half and returns to normal over three seconds', () => {
  assert.equal(motion.tossGravityScale(0), 0.5);
  assert.equal(motion.tossGravityScale(1500), 0.75);
  assert.equal(motion.tossGravityScale(3000), 1);
  assert.equal(motion.tossGravityScale(5000), 1);
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

test('a falling pet lands only on a crossed, overlapping window or bar top', () => {
  const surfaces = [{ x: 100, y: 300, width: 200 }, { x: 400, y: 500, width: 80 }];
  assert.deepEqual({ ...motion.landingSurface(240, 263, 150, 40, 40, surfaces) }, { y: 300, x: 100, width: 200 });
  assert.equal(motion.landingSurface(270, 310, 150, 40, 40, surfaces), null);
  assert.equal(motion.landingSurface(240, 261, 60, 40, 40, surfaces), null);
  assert.equal(motion.landingSurface(240, 261, 300, 40, 40, surfaces), null);
  assert.equal(motion.landingSurface(100, 270, 150, 40, 40, surfaces)?.y, 300);
  assert.equal(motion.landingSurface(240, 261, 150, 40, 0, surfaces), null);
});

test('standing contact sits five percent above the sprite bottom on edges and floor', () => {
  assert.equal(motion.contactHeight(40), 38);
  assert.equal(motion.contactHeight(208), 197.6);
  assert.equal(motion.contactHeight(0), 0);
  const surface = { x: 100, y: 300, width: 200 };
  assert.equal(motion.landingSurface(260, 263, 150, 40, 40, [surface])?.y, 300);
  assert.equal(motion.landingSurface(260, 261, 150, 40, 40, [surface]), null);
  assert.equal(motion.supportAt(262, 150, 40, 40, [surface])?.y, 300);
  assert.equal(motion.supportAt(260, 150, 40, 40, [surface]), null);
  assert.match(windowSource, /groundY: Math\.max\(0, height - Motion\.contactHeight\(pixelHeight\)\)/);
  assert.match(windowSource, /landing\.y - Motion\.contactHeight\(root\.pixelHeight\)/);
});

test('perched pets walk within the supporting surface and fall when support disappears', () => {
  const surface = { x: 100, y: 300, width: 200 };
  assert.equal(motion.supportAt(262, 240, 40, 40, [surface])?.x, 100);
  assert.equal(motion.supportAt(262, 310, 40, 40, [surface]), null);
  assert.equal(motion.supportAt(262, 240, 40, 40, []), null);
  assert.equal(motion.wanderOnSurface(260, 380, surface, 40), 260);
  assert.equal(motion.wanderOnSurface(120, 0, surface, 40), 100);
});

test('service polls sanitized Hyprland geometry only while pets are enabled', () => {
  const service = fs.readFileSync(path.join(__dirname, '..', 'Service.qml'), 'utf8');
  assert.match(service, /property var surfaces: \(\{\}\)/);
  assert.match(service, /"surfaces"/);
  assert.match(service, /running: root\.renderableProfiles\.length > 0/);
  assert.match(service, /surfaces: root\.surfacesFor\(selectedScreen/);
});

test('the falling pet consults visible surfaces and releases them when geometry changes', () => {
  assert.match(windowSource, /Motion\.landingSurface\(root\.fallY,.*root\.surfaces\)/s);
  assert.match(windowSource, /Motion\.supportAt\(root\.supportY,.*root\.surfaces\)/s);
  assert.match(windowSource, /Motion\.wanderOnSurface\(/);
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
  assert.equal(motion.frameInterval(false, true, 'working'), 110);
});

test('working plays at eighty percent speed without slowing walking or other states', () => {
  assert.equal(motion.frameInterval(false, false, 'working'), 188);
  assert.equal(motion.frameInterval(false, false, 'thinking'), 150);
  assert.equal(motion.frameInterval(false, true, 'working'), 110);
  assert.equal(motion.frameInterval(true, false, 'working'), 140);
});

test('walking animation takes precedence over a requested action', () => {
  const animation = windowSource.split('readonly property var animation:')[1]?.split('property int frame:')[0] || '';
  assert.match(animation, /: walking \? \(\{ row: facingLeft \? 2 : 1, frames: 8 \}\)/);
  assert.ok(animation.indexOf(': walking ?') < animation.indexOf('profile.animations[category]'));
});

test('the frame timer keeps the 120% animation cadence outside the held state', () => {
  assert.match(windowSource, /interval: grabArea\.pressed \? 140 : Motion\.frameInterval\(root\.airborne,\s*root\.walking,\s*root\.category\)/);
});

test('the fifth atlas row is a held squirm when available, with a safe fallback', () => {
  assert.deepEqual({ ...motion.heldAnimation(9, 8) }, { row: 4, frames: 5 });
  assert.deepEqual({ ...motion.heldAnimation(4, 8) }, { row: 0, frames: 6 });
  assert.deepEqual({ ...motion.heldAnimation(9, 3) }, { row: 0, frames: 3 });
});

test('held frames pause at center then alternate swing and idle squirm', () => {
  assert.equal(motion.heldFrame(0, true), 2);
  assert.deepEqual([0, 1, 2, 3, 4].map(n => motion.heldFrame(n, true)), [2, 3, 2, 1, 2]);
  assert.deepEqual([0, 1, 2, 3, 4, 5, 6, 7].map(n => motion.heldFrame(n, false)),
    [2, 3, 4, 3, 2, 1, 0, 1]);
});

test('held pet grips 10% below its top without crossing the monitor', () => {
  assert.deepEqual({ ...motion.gripPosition(500, 300, 1000, 700, 100, 120) }, { x: 450, y: 288 });
  assert.deepEqual({ ...motion.gripPosition(500, 60, 1000, 700, 100, 120) }, { x: 450, y: 48 });
  assert.deepEqual({ ...motion.gripPosition(0, 0, 1000, 700, 100, 120) }, { x: 0, y: 0 });
  assert.deepEqual({ ...motion.gripPosition(990, 690, 1000, 700, 100, 120) }, { x: 900, y: 580 });
});

test('held pet faces against each new horizontal pointer movement', () => {
  assert.equal(motion.heldFacing(100, 110, false), true);
  assert.equal(motion.heldFacing(110, 95, true), false);
  assert.equal(motion.heldFacing(95, 95.5, false), false);
  assert.equal(motion.heldFacing(95, Number.NaN, true), true);
});

test('a held pet leans more against mouse motion and settles upright', () => {
  assert.equal(motion.heldSway(10), -5);
  assert.equal(motion.heldSway(20), -10);
  assert.equal(motion.heldSway(-100), 10);
  assert.equal(motion.heldSway(0), 0);
  assert.equal(motion.heldSway(Number.NaN), 0);
  assert.equal(motion.settleSway(-8), -4.8);
  assert.equal(motion.settleSway(0.1), 0);
});

test('left click only toggles the above-pet card while state events own the speech', () => {
  const released = windowSource.split('onReleased: function(mouse) {')[1]?.split('onCanceled:')[0] || '';
  assert.match(released, /root\.infoVisible = !root\.infoVisible/);
  assert.doesNotMatch(released, /emitEvent|applyEvent|Math\.random/);
  assert.match(windowSource, /id: card[\s\S]*visible: root\.infoVisible && !grabArea\.pressed/);
  assert.match(windowSource, /id: card[\s\S]*y: Math\.max\(0, sprite\.y - height - 8\)/);
  assert.match(windowSource, /Model\.statusLabel\(root\.category\)/);
  assert.match(windowSource, /id: bubble[\s\S]*readonly property string message: root\.activity && root\.activity\.phrase \? root\.activity\.phrase : ""/);
  assert.doesNotMatch(windowSource, /root\.infoVisible && root\.profile \? root\.profile\.id/);
});

test('waiting on the user waves briefly then rests between waves', () => {
  assert.match(windowSource, /property bool waitingWave: false/);
  assert.match(windowSource, /category === "waiting_on_you" && !waitingWave[\s\S]*\{ row: 0, frames: 6 \}/);
  assert.match(windowSource, /id: waitingWaveInterval[\s\S]*interval: 4000[\s\S]*running: root\.visible && root\.category === "waiting_on_you"[\s\S]*root\.waitingWave = true/);
  assert.match(windowSource, /id: waitingWaveDuration[\s\S]*interval: 800[\s\S]*root\.waitingWave = false/);
  assert.match(windowSource, /onCategoryChanged: \{[^}]*waitingWave = false/);
});

test('the hosted pet uses row five and moving or resting frames while held', () => {
  assert.match(windowSource, /readonly property var animation: grabArea\.pressed\s*\? Motion\.heldAnimation\(/);
  assert.match(windowSource, /interval: grabArea\.pressed \? 140 : Motion\.frameInterval/);
  assert.match(windowSource, /Motion\.heldFrame\(root\.heldPhase, Date\.now\(\) - root\.lastPointerMotionMs < 180\)/);
  assert.match(windowSource, /root\.frame = Motion\.heldAnimation\([^)]*\)\.row === 4 \? 2 : 0/);
});

test('pickup and drag keep the pointer at the grip point below the sprite top', () => {
  const press = windowSource.split('onPressed: function(mouse) {')[1]?.split('onPositionChanged:')[0] || '';
  const move = windowSource.split('onPositionChanged: function(mouse) {')[1]?.split('onReleased:')[0] || '';
  for (const handler of [press, move]) {
    assert.match(handler, /Motion\.gripPosition\(point\.x, point\.y, root\.width, root\.height, sprite\.width, sprite\.height\)/);
    assert.match(handler, /root\.dragX = held\.x/);
    assert.match(handler, /root\.dragY = held\.y/);
  }
});

test('held facing and sway follow mouse motion then settle', () => {
  const move = windowSource.split('onPositionChanged: function(mouse) {')[1]?.split('onReleased:')[0] || '';
  assert.match(move, /root\.heldFacingLeft = Motion\.heldFacing\(lastPointerX, point\.x, root\.heldFacingLeft\)/);
  assert.match(move, /root\.heldSwayAngle = Motion\.heldSway\(point\.x - lastPointerX\)/);
  assert.match(move, /root\.lastPointerMotionMs = Date\.now\(\)/);
  assert.match(windowSource, /xScale: grabArea\.pressed && root\.heldFacingLeft \? -1 : 1/);
  assert.match(windowSource, /rotation: grabArea\.pressed \? root\.heldSwayAngle : 0/);
  assert.match(windowSource, /Motion\.settleSway\(root\.heldSwayAngle\)/);
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
