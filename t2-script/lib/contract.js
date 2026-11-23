'use strict';
/*
 * lib/contract.js
 * The §3 job contract for QuickFrame. This is the seam the whole app hangs on:
 *   - engine.build(cfg) MUST return an object with exactly these top-level keys
 *     and scenes[] with exactly these per-scene keys.
 *   - The 7 stage keys (script → boards → art → voice → captions → encode → publish)
 *     are the render-log format and the pipeline promise. They never change.
 *
 * T2 only replaces the *script pass* (the text). It must not change this shape.
 * `validateJob` is the guard that makes "keep the return shape" enforceable, not
 * just a comment someone can ignore.
 */

// The seven stage keys. Order matters — it is the pipeline order the UI/encoder log.
const STAGES = ['script', 'boards', 'art', 'voice', 'captions', 'encode', 'publish'];

// Caption styles (studio.js STYLES / CAPS). Encoder mirrors "blocks" only.
const CAPTION_STYLES = ['blocks', 'karaoke', 'clean', 'none'];

// Music beds (studio.js BEDS).
const BEDS = ['chalk', 'drive', 'lofi', 'ai', 'none'];

// Aspect ratios the encoder ships today (T7 notes: only these two exist as output).
const ASPECTS = ['16:9', '9:16'];

// Top-level keys the app consumes from a job (job JSON §3).
const JOB_KEYS = [
  'id', 'topic', 'subject', 'template', 'templateName', 'audience', 'tone',
  'voice', 'aspect', 'music', 'captions', 'title', 'hook', 'totalSec', 'words',
  'description', 'tags', 'thumbnail', 'credits', 'warnings', 'scenes',
];

// Per-scene keys (job JSON §3).
const SCENE_KEYS = [
  'i', 'beat', 'vo', 'caption', 'onText', 'motion', 'art', 'whyArt',
  'clip', 'sec', 'words', 'chars', 'start', 'end', 'cues',
];

// voice is an object {...}; document its expected shape.
const VOICE_KEYS = ['name', 'rate', 'pitch'];

function isObj(v) { return v !== null && typeof v === 'object' && !Array.isArray(v); }
function isArr(v) { return Array.isArray(v); }
function isStr(v) { return typeof v === 'number' ? false : typeof v === 'string'; }
function isNum(v) { return typeof v === 'number' && Number.isFinite(v); }

// Collect missing/extra/mistyped keys. Returns an array of human-readable problems.
function checkShape(obj, keys, label, { allowExtra = false } = {}) {
  const problems = [];
  if (!isObj(obj)) { problems.push(`${label}: expected object, got ${obj === null ? 'null' : typeof obj}`); return problems; }
  for (const k of keys) {
    if (!(k in obj)) problems.push(`${label}.${k}: missing`);
  }
  if (!allowExtra) {
    for (const k of Object.keys(obj)) {
      if (!keys.includes(k)) problems.push(`${label}.${k}: unexpected key`);
    }
  }
  return problems;
}

// Full structural + type validation of a built job. Throws on any drift so a
// regression in the contract fails loudly at build time, not in the browser.
function validateJob(job) {
  const problems = [];
  problems.push(...checkShape(job, JOB_KEYS, 'job'));

  // types on the scalar/derived fields
  if (!isStr(job.id)) problems.push('job.id: must be string');
  if (!isStr(job.topic) || !job.topic.trim()) problems.push('job.topic: must be non-empty string');
  if (!isStr(job.template)) problems.push('job.template: must be string (spine key)');
  if (!isStr(job.templateName)) problems.push('job.templateName: must be string');
  if (!isStr(job.title)) problems.push('job.title: must be string');
  if (!isStr(job.hook)) problems.push('job.hook: must be string');
  if (!isNum(job.totalSec) || job.totalSec <= 0) problems.push('job.totalSec: must be positive number');
  if (!isNum(job.words) || job.words < 0) problems.push('job.words: must be number');
  if (!isNum(job.credits) || job.credits < 0) problems.push('job.credits: must be number');
  if (!isArr(job.tags)) problems.push('job.tags: must be array');
  if (!isArr(job.warnings)) problems.push('job.warnings: must be array');
  if (!isObj(job.thumbnail)) problems.push('job.thumbnail: must be object {text, art}');
  else {
    if (!('text' in job.thumbnail)) problems.push('job.thumbnail.text: missing');
    if (!('art' in job.thumbnail)) problems.push('job.thumbnail.art: missing');
  }
  if (!isObj(job.voice)) problems.push('job.voice: must be object {name, rate, pitch}');
  else problems.push(...checkShape(job.voice, VOICE_KEYS, 'job.voice', { allowExtra: true }));

  if (job.aspect && !ASPECTS.includes(job.aspect)) problems.push(`job.aspect: "${job.aspect}" not one of ${ASPECTS.join(', ')}`);
  if (job.captions && !CAPTION_STYLES.includes(job.captions)) problems.push(`job.captions: "${job.captions}" not one of ${CAPTION_STYLES.join(', ')}`);
  if (job.music && !BEDS.includes(job.music)) problems.push(`job.music: "${job.music}" not one of ${BEDS.join(', ')}`);

  // scenes
  if (!isArr(job.scenes) || job.scenes.length === 0) {
    problems.push('job.scenes: must be a non-empty array');
  } else {
    let cursor = 0;
    job.scenes.forEach((s, idx) => {
      const label = `job.scenes[${idx}]`;
      problems.push(...checkShape(s, SCENE_KEYS, label));
      if (!isNum(s.i) || s.i !== idx + 1) problems.push(`${label}.i: must equal ${idx + 1}`);
      if (!isStr(s.beat) || !s.beat.trim()) problems.push(`${label}.beat: must be non-empty string`);
      if (!isStr(s.vo) || !s.vo.trim()) problems.push(`${label}.vo: must be non-empty string`);
      if (!isStr(s.caption)) problems.push(`${label}.caption: must be string`);
      if (!isStr(s.onText)) problems.push(`${label}.onText: must be string`);
      if (!isStr(s.motion)) problems.push(`${label}.motion: must be string`);
      if (!isStr(s.art)) problems.push(`${label}.art: must be string (art-direction label)`);
      if (!isStr(s.whyArt)) problems.push(`${label}.whyArt: must be string`);
      if (!('clip' in s)) problems.push(`${label}.clip: must be present (string or null)`);
      if (!isNum(s.sec) || s.sec < 0) problems.push(`${label}.sec: must be non-negative number`);
      if (!isNum(s.words) || s.words < 0) problems.push(`${label}.words: must be number`);
      if (!isNum(s.chars) || s.chars < 0) problems.push(`${label}.chars: must be number`);
      if (!isNum(s.start) || !isNum(s.end)) problems.push(`${label}.start/.end: must be numbers`);
      else {
        if (Math.abs(s.start - cursor) > 0.02) problems.push(`${label}.start: ${s.start} != running cursor ${cursor.toFixed(2)} (timeline not contiguous)`);
        if (s.end < s.start) problems.push(`${label}: end < start`);
        cursor = s.end;
      }
      if (!isArr(s.cues)) problems.push(`${label}.cues: must be array`);
      else s.cues.forEach((c, ci) => {
        if (!isObj(c)) { problems.push(`${label}.cues[${ci}]: must be object {text, at}`); return; }
        if (!('text' in c)) problems.push(`${label}.cues[${ci}].text: missing`);
        if (!isNum(c.at)) problems.push(`${label}.cues[${ci}].at: must be number (seconds)`);
        else if (c.at < s.start - 0.001 || c.at > s.end + 0.001) problems.push(`${label}.cues[${ci}].at: ${c.at} outside scene window [${s.start}, ${s.end}]`);
      });
    });
    // totalSec must equal the sum of scene sec (to rounding)
    const sumSec = job.scenes.reduce((a, s) => a + (isNum(s.sec) ? s.sec : 0), 0);
    if (isNum(job.totalSec) && Math.abs(job.totalSec - sumSec) > 0.05) {
      problems.push(`job.totalSec: ${job.totalSec} != sum(scene.sec) ${sumSec.toFixed(2)}`);
    }
  }

  if (problems.length) {
    const err = new Error('CONTRACT VIOLATION:\n  - ' + problems.join('\n  - '));
    err.name = 'ContractError';
    err.problems = problems;
    throw err;
  }
  return true;
}

module.exports = { STAGES, CAPTION_STYLES, BEDS, ASPECTS, JOB_KEYS, SCENE_KEYS, VOICE_KEYS, validateJob };
