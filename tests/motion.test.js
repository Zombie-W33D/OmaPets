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
