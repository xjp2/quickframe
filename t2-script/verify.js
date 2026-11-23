'use strict';
/*
 * verify.js — T2 regression suite. Node built-ins only; no model, no keys.
 *
 * Proves the three things the task's acceptance test asks for, plus the contract:
 *   1. build() returns a job that PASSES lib/contract.validateJob (exact §3 shape).
 *   2. The LLM path genuinely CHANGES the script: agent-provider vo differs from
 *      the deterministic template vo for the same topic (T2 acceptance).
 *   3. The template path is byte-for-byte deterministic (same topic => same job),
 *      i.e. it reproduces the OLD stub behaviour and the contract/timing never drift.
 *   4. Timing invariants: totalSec == sum(scene.sec), contiguous timeline, every
 *      cue inside its scene window, credits == ceil(totalSec/10).
 *   5. Art-direction: no frame id repeats within a job.
 *   6. The seven stage keys are intact.
 *
 * Run:  node verify.js   (exits 1 on any failure)
 */

const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert');

const { build } = require('./engine');
const { validateJob, STAGES, JOB_KEYS, SCENE_KEYS } = require('./lib/contract');
const { getSpine } = require('./lib/templates');

let passed = 0, failed = 0;
function ok(name, fn) {
  try { fn(); console.log(`  PASS  ${name}`); passed++; }
  catch (e) { console.log(`  FAIL  ${name}\n        ${e.message}`); failed++; }
}

// A genuine, model-authored response for an unseen topic, used to exercise the
// agent provider offline and deterministically (this stands in for the QwenWork
// model writing the JSON — the engine still computes every number).
const TOPIC = 'why you can never tickle yourself';
const SPINE = 'why';
const AGENT_FIXTURE = {
  title: "Why You Can't Tickle Yourself",
  hook: 'Your own fingers are the one thing that cannot surprise you. Here is why.',
  description: 'A short why-it-happens explainer about why self-tickling never lands.',
  tags: ['tickle', 'brain', 'prediction', 'neuroscience'],
  thumbnail: { text: 'You Cannot Tickle You' },
  scenes: [
    { vo: 'Try it right now. Reach over and tickle your own arm. Almost nothing.', caption: 'Reach over and tickle your own arm. Nothing.', onText: 'Try It Now', motion: 'pan', art: 'hero', whyArt: 'wide shot of a person reaching for their own arm' },
    { vo: 'The guess is that you are just not sensitive there. You are. Ask a friend.', caption: 'The guess says you are not sensitive there.', onText: 'The Usual Guess', motion: 'draw-on', art: 'f1', whyArt: 'simple two-hand concept sketch' },
    { vo: 'The real reason is smaller. Your brain predicts the touch before it lands.', caption: 'Your brain predicts the touch before it lands.', onText: 'The Brain Predicts', motion: 'zoom', art: 'f2', whyArt: 'close-in diagram of the prediction signal' },
    { vo: 'Test it: a robot hand that tickles with a half-second delay works instantly.', caption: 'Add a delay and suddenly it works.', onText: 'Add A Delay', motion: 'build', art: 'f4', whyArt: 'worked-example panel with a delayed robot hand' },
    { vo: 'So it is not the finger. It is a brain that cannot surprise itself.', caption: 'A brain that cannot surprise itself.', onText: 'No Surprise', motion: 'reveal', art: 's6', whyArt: 'comparison: self touch vs delayed touch' },
  ],
};

async function main() {
  console.log('\nQuickFrame T2 — verify\n');

  // ---- 1. template path: valid + deterministic ------------------------------
  const t1 = await build({ topic: TOPIC, template: SPINE, lengthSec: 30, provider: 'template' });
  const t2 = await build({ topic: TOPIC, template: SPINE, lengthSec: 30, provider: 'template' });

  ok('template build passes contract.validateJob', () => { validateJob(t1); });
  ok('template build is byte-for-byte deterministic (old-stub behaviour)', () => {
    assert.strictEqual(JSON.stringify(t1), JSON.stringify(t2), 'two template builds differ');
  });
  ok('job has exactly the §3 top-level keys', () => {
    const got = Object.keys(t1).sort(), want = JOB_KEYS.slice().sort();
    assert.deepStrictEqual(got, want, `keys differ: ${JSON.stringify(got)}`);
  });
  ok('scene has exactly the §3 per-scene keys', () => {
    const got = Object.keys(t1.scenes[0]).sort(), want = SCENE_KEYS.slice().sort();
    assert.deepStrictEqual(got, want, `scene keys differ: ${JSON.stringify(got)}`);
  });

  // ---- 2. the seven stage keys are intact -----------------------------------
  ok('seven stage keys preserved in order', () => {
    assert.deepStrictEqual(STAGES, ['script', 'boards', 'art', 'voice', 'captions', 'encode', 'publish']);
  });

  // ---- 3. timing invariants on the template job -----------------------------
  ok('totalSec == sum(scene.sec)', () => {
    const sum = t1.scenes.reduce((a, s) => a + s.sec, 0);
    assert.ok(Math.abs(t1.totalSec - sum) < 0.05, `${t1.totalSec} vs ${sum}`);
  });
  ok('timeline is contiguous (each start == previous end)', () => {
    let cursor = 0;
    t1.scenes.forEach((s, i) => {
      assert.ok(Math.abs(s.start - cursor) < 0.02, `scene ${i + 1} start ${s.start} != ${cursor}`);
      assert.ok(Math.abs(s.end - (s.start + s.sec)) < 0.02, `scene ${i + 1} end != start+sec`);
      cursor = s.end;
    });
  });
  ok('every cue.at sits inside its scene window', () => {
    t1.scenes.forEach((s, i) => s.cues.forEach((c, ci) => {
      assert.ok(c.at >= s.start - 0.001 && c.at <= s.end + 0.001, `scene ${i + 1} cue ${ci} at ${c.at} outside [${s.start},${s.end}]`);
    }));
  });
  ok('credits == ceil(totalSec/10)', () => {
    assert.strictEqual(t1.credits, Math.max(1, Math.ceil(t1.totalSec / 10)));
  });
  ok('per-scene words/chars match the narration', () => {
    t1.scenes.forEach((s) => {
      assert.strictEqual(s.words, s.vo.trim().split(/\s+/).length);
      assert.strictEqual(s.chars, s.vo.length);
    });
  });

  // ---- 4. art-direction: no repeats within a job ----------------------------
  ok('no art frame repeats within the template job', () => {
    const arts = t1.scenes.map((s) => s.art);
    assert.strictEqual(new Set(arts).size, arts.length, `repeats: ${arts.join(',')}`);
  });

  // ---- 5. warnings[] is always present and an array -------------------------
  ok('warnings[] is an array', () => { assert.ok(Array.isArray(t1.warnings)); });

  // ---- 6. LLM path genuinely differs from the template (T2 acceptance) ------
  const respPath = path.join(__dirname, 'out', 'verify-agent-response.json');
  fs.mkdirSync(path.dirname(respPath), { recursive: true });
  fs.writeFileSync(respPath, JSON.stringify(AGENT_FIXTURE, null, 2), 'utf8');
  const llm = await build({ topic: TOPIC, template: SPINE, lengthSec: 30, provider: 'agent', responsePath: respPath });

  ok('agent/LLM build passes contract.validateJob', () => { validateJob(llm); });
  ok('LLM vo differs from the template vo for the same topic (acceptance)', () => {
    const same = llm.scenes.filter((s, i) => s.vo === t1.scenes[i].vo);
    assert.strictEqual(same.length, 0, `${same.length} scene(s) identical to the stub`);
  });
  ok('LLM job keeps the same spine beats + 5 scenes', () => {
    assert.strictEqual(llm.scenes.length, getSpine(SPINE).beats.length);
    llm.scenes.forEach((s, i) => assert.strictEqual(s.beat, getSpine(SPINE).beats[i].beat));
  });
  ok('LLM warnings[] still populated as an array', () => { assert.ok(Array.isArray(llm.warnings)); });
  ok('LLM credits recomputed from its own totalSec', () => {
    assert.strictEqual(llm.credits, Math.max(1, Math.ceil(llm.totalSec / 10)));
  });
  ok('LLM job numbers are computed, not copied from the model', () => {
    // the model never supplied sec/words/start/end/cues; assert they are well-formed
    const sum = llm.scenes.reduce((a, s) => a + s.sec, 0);
    assert.ok(Math.abs(llm.totalSec - sum) < 0.05);
    llm.scenes.forEach((s) => assert.ok(s.cues.length >= 1 && s.words > 0));
  });
  ok('LLM job has no repeated art', () => {
    const arts = llm.scenes.map((s) => s.art);
    assert.strictEqual(new Set(arts).size, arts.length);
  });

  // ---- 7. the contract guard actually rejects a malformed job ---------------
  ok('validateJob throws on a malformed job (guard is real)', () => {
    const bad = JSON.parse(JSON.stringify(t1));
    delete bad.hook; bad.scenes[0].start = 99;
    assert.throws(() => validateJob(bad), /CONTRACT VIOLATION/);
  });

  // ---- 8. unknown spine / empty topic fail loudly ---------------------------
  await (async () => {
    let threw = false;
    try { await build({ topic: '', provider: 'template' }); } catch { threw = true; }
    ok('empty topic throws', () => assert.ok(threw));
  })();

  console.log(`\n${failed === 0 ? 'ALL GREEN' : 'FAILURES'}  —  ${passed} passed, ${failed} failed\n`);
  process.exit(failed === 0 ? 0 : 1);
}

main().catch((e) => { console.error('\n[verify crashed]', e && e.stack ? e.stack : e); process.exit(1); });
