const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '..', 'Model.js'), 'utf8')
  .replace(/^\.pragma library\s*\n/, '');
const model = vm.createContext({ Math });
vm.runInContext(script, model);

const profile = {
  id: 'aria', enabled: true, pet: { name: 'Socksy' },
  phrases: { thinking: ['one', 'two'], yes: ['Yes.'], no: [] },
};

test('an event needs an enabled local profile and a known category', () => {
  assert.equal(model.applyEvent([profile], {}, 'other', 'thinking', 100, () => 0), null);
  assert.equal(model.applyEvent([profile], {}, 'aria', 'not-a-category', 100, () => 0), null);
  assert.equal(model.applyEvent([{ ...profile, enabled: false }], {}, 'aria', 'yes', 100, () => 0), null);
});

test('a repeat event chooses a different phrase without reading agent text', () => {
  const first = model.applyEvent([profile], {}, 'aria', 'thinking', 100, () => 0);
  assert.equal(first.phrase, 'one');
  const second = model.applyEvent([profile], { aria: first }, 'aria', 'thinking', 200, () => 0);
  assert.equal(second.phrase, 'two');
  const silent = model.applyEvent([profile], {}, 'aria', 'no', 200, () => 0);
  assert.equal(silent.phrase, '');
});

test('card labels the distinct agent states without inventing a message', () => {
  assert.equal(model.statusLabel('thinking'), 'Thinking');
  assert.equal(model.statusLabel('working'), 'Working');
  assert.equal(model.statusLabel('waiting_on_you'), 'Waiting for you');
  assert.equal(model.statusLabel('waiting_on_task'), 'Waiting on task');
  assert.equal(model.statusLabel('finished'), 'Finished');
  assert.equal(model.statusLabel('failed'), 'Failed');
  assert.equal(model.statusLabel('idle'), 'Idle');
});

test('terminal events expire sooner than ongoing activity', () => {
  assert.equal(model.visibleEvent({ category: 'yes', time: 100 }, 8101).category, 'idle');
  assert.equal(model.visibleEvent({ category: 'thinking', time: 100 }, 8101).category, 'thinking');
  assert.equal(model.visibleEvent({ category: 'thinking', time: 100 }, 120101).category, 'idle');
});

test('working, thinking, both waiting states, finished and failed select their own lines', () => {
  const categories = ['working', 'thinking', 'waiting_on_you', 'waiting_on_task', 'finished', 'failed'];
  const phrases = Object.fromEntries(categories.map(category => [category, [`${category} line`]]));
  for (const category of categories) {
    const event = model.applyEvent([{ ...profile, phrases }], {}, 'aria', category, 100, () => 0);
    assert.equal(event?.category, category);
    assert.equal(event?.phrase, `${category} line`);
  }
  assert.equal(model.visibleEvent({ category: 'working', time: 100 }, 8101).category, 'working');
  assert.equal(model.visibleEvent({ category: 'finished', time: 100 }, 8101).category, 'idle');
  assert.equal(model.visibleEvent({ category: 'failed', time: 100 }, 8101).category, 'idle');
});
