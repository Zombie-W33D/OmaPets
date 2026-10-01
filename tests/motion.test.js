const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// The exact same dependency-free JavaScript is imported by PetWindow.qml.
const source = fs.readFileSync(path.join(__dirname, '..', 'Motion.js'), 'utf8');
const motion = vm.createContext({ Math, Number });
vm.runInContext(source, motion);

test('gravity accelerates, caps velocity and settles at the sprite-height floor', () => {
  let state = { y: 100, vy: 0 };
  let fastest = 0;
  for (let i = 0; i < 150; i++) {
    state = motion.gravityStep(state.y, state.vy, 700, 0);
    fastest = Math.max(fastest, state.vy);
  }
  assert.equal(state.y, 700);
  assert.equal(state.vy, 0);
  assert.equal(fastest, 48);
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

test('OpenPets speed presets and airborne animation have a bounded fallback', () => {
  assert.equal(motion.speedDuration('slow'), 1800);
  assert.equal(motion.speedDuration('normal'), 1100);
  assert.equal(motion.speedDuration('brisk'), 600);
  assert.equal(motion.speedDuration('unknown'), 1800);
  const airborne = motion.airborneAnimation(9);
  assert.equal(airborne.row, 4);
  assert.equal(airborne.frames, 5);
  assert.equal(motion.airborneAnimation(3).row, 0);
});
