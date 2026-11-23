'use strict';
/*
 * engine.js — QuickFrame T2 script engine.
 *
 * This is the seam the whole app hangs on (spec §2/T2): `build(cfg)` turns a
 * topic + cfg into the §3 job JSON. The OLD engine.js was a deterministic stub;
 * here the *script pass* is one LLM call, but the RETURN SHAPE (§3) and the
 * seven stage keys are preserved exactly. Nothing else in the pipeline changes.
 *
 * Division of labour (the whole point of T2):
 *   - The LLM (a provider) writes ONLY creative text: title, hook, description,
 *     tags, thumbnail.text, and per-scene {vo, caption, onText, motion, art, whyArt}.
 *   - This engine computes EVERY number: sec, words, chars, start, end, cues[].at,
 *     totalSec, credits, and the warnings[] — via lib/timing.js — so the player
 *     (studio.js) and the encoder (tools_build/driver.py) stay in sync.
 *   - lib/contract.js then validates the assembled job and throws on any drift.
 *
 * cfg in:  {topic, template, lengthSec, aspect, voice, tone, captions, music, duck}
 *          (+ engine-internal: provider, responsePath, outDir)
 *   (extra cfg keys the §3 job does not carry — duck, provider, responsePath, outDir —
 *    are inputs only; they are never written into the returned job. The §3 job DOES
 *    carry `audience` and `subject` but the cfg does not, so the engine derives them
 *    from optional plain cfg fields with documented defaults.)
 *
 * Returns: a Promise resolving to the validated §3 job object.
 */

const path = require('node:path');

const { getSpine, FRAMES } = require('./lib/templates');
const { buildPrompt } = require('./lib/prompt');
const { layoutScenes, countWords } = require('./lib/timing');
const { validateJob, ASPECTS, CAPTION_STYLES, BEDS, SCENE_KEYS } = require('./lib/contract');
const { resolveProvider } = require('./lib/providers');

// ---- small helpers -----------------------------------------------------------

function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }

// Deterministic job id from topic + spine. The template provider is byte-for-byte
// reproducible (id included), which is what verify.js relies on. A production
// build would swap this for a UUID; the id is an identifier, not part of the script.
function makeId(topic, spineKey) {
  const slug = String(topic).toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .split('-').slice(0, 6).join('-');
  return `qf-${spineKey}-${slug || 'job'}`;
}

// Normalise cfg.voice (string | object | undefined) into the §3 {name, rate, pitch}.
function normalizeVoice(v) {
  if (!v) return { name: 'neutral', rate: 1, pitch: 0 };
  if (typeof v === 'string') return { name: v, rate: 1, pitch: 0 };
  const rate = Number.isFinite(v.rate) && v.rate > 0 ? v.rate : 1;
  const pitch = Number.isFinite(v.pitch) ? v.pitch : 0;
  return { name: v.name || 'neutral', rate, pitch };
}

// Coerce a scalar to a trimmed string with a fallback, recording a warning when
// the model omitted a required creative field.
function strField(value, fallback, field, warnings) {
  if (typeof value === 'string' && value.trim()) return value.trim();
  warnings.push(`model omitted "${field}"; used a deterministic fallback`);
  return fallback;
}

// Keep onText to <= 6 words (the encoder typesets it; long on-screen titles break
// the safe-area audit). Truncate + warn rather than fail.
function clampOnText(text, i, warnings) {
  let t = (typeof text === 'string' ? text : '').trim();
  if (!t) { warnings.push(`scene ${i + 1}: empty onText; used the beat label`); return t; }
  const words = t.split(/\s+/);
  if (words.length > 6) {
    warnings.push(`scene ${i + 1}: onText was ${words.length} words; trimmed to 6 for the frame`);
    t = words.slice(0, 6).join(' ');
  }
  return t;
}

// Assign a distinct frame id per scene from the on-disk pool. The model's art is
// honoured when valid + unused; collisions / unknown ids are repaired so
// "no art repeats" holds (studio.js: "Re-roll the boards → no art repeats").
function assignArt(modelScenes, spine, warnings) {
  const pool = FRAMES;
  const used = new Set();
  const defaults = spine.beats.map((b) => b.art);
  const arts = [];
  modelScenes.forEach((s, i) => {
    let a = typeof s.art === 'string' ? s.art.trim() : '';
    if (!pool.includes(a)) {
      if (a) warnings.push(`scene ${i + 1}: art "${a}" not in the on-disk pool; reassigned`);
      a = defaults[i] && pool.includes(defaults[i]) ? defaults[i] : pool[i % pool.length];
    }
    if (used.has(a)) {
      // first try this beat's default, then scan the pool for anything unused
      const alt = [defaults[i], ...pool].find((c) => pool.includes(c) && !used.has(c));
      warnings.push(`scene ${i + 1}: art "${a}" repeated; reassigned to "${alt}"`);
      a = alt;
    }
    used.add(a);
    arts.push(a);
  });
  return arts;
}

function sanitizeTags(raw, topic, spineKey, warnings) {
  let list = Array.isArray(raw) ? raw : [];
  list = list
    .filter((t) => typeof t === 'string' && t.trim())
    .map((t) => t.trim().toLowerCase().replace(/^#/, ''));
  list = [...new Set(list)];
  if (list.length === 0) {
    warnings.push('model returned no tags; used deterministic fallback tags');
    list = [String(topic).split(/\s+/)[0].toLowerCase(), spineKey, 'explainer'];
  }
  return list.slice(0, 8);
}

// ---- the seam ----------------------------------------------------------------

async function build(cfg) {
  if (!cfg || typeof cfg !== 'object') throw new Error('build(cfg): cfg must be an object');
  const topic = String(cfg.topic || '').trim();
  if (!topic) throw new Error('build(cfg): cfg.topic is required');

  const spineKey = cfg.template || cfg.spine || 'why';
  const spine = getSpine(spineKey);

  const lengthSec = Number.isFinite(cfg.lengthSec) && cfg.lengthSec > 0 ? cfg.lengthSec : 30;
  const aspect = ASPECTS.includes(cfg.aspect) ? cfg.aspect : '16:9';
  const captions = CAPTION_STYLES.includes(cfg.captions) ? cfg.captions : 'blocks';
  const music = BEDS.includes(cfg.music) ? cfg.music : 'chalk';
  const tone = cfg.tone || 'clear, friendly, confident';
  const voice = normalizeVoice(cfg.voice);
  const rate = voice.rate;
  // audience + subject are §3 job fields but are NOT in the cfg; derive them from
  // optional plain cfg overrides with documented defaults (no five-slot input).
  const audience = cfg.audience || 'curious general viewers';
  const subject = cfg.subject || 'explainer';
  const outDir = cfg.outDir || path.join(__dirname, 'out');

  const engineWarnings = [];

  // 1. one LLM call for the creative text.
  const prompt = buildPrompt(
    { topic, lengthSec, aspect, tone, voice },
    spine
  );
  const provider = resolveProvider(cfg);
  const jobId = makeId(topic, spine.key);
  const payload = await provider.generate({ cfg, spine, prompt, jobId, outDir });

  // 2. normalise the model payload -> exactly spine.beats.length creative scenes.
  if (!payload || !Array.isArray(payload.scenes)) {
    throw new Error(`Model payload has no scenes[] (provider: ${provider.name}).`);
  }
  const want = spine.beats.length;
  if (payload.scenes.length !== want) {
    throw new Error(`Model returned ${payload.scenes.length} scenes; spine "${spine.key}" requires exactly ${want}.`);
  }
  const modelScenes = payload.scenes;

  const arts = assignArt(modelScenes, spine, engineWarnings);

  const creativeScenes = modelScenes.map((s, i) => {
    const beat = spine.beats[i];
    const vo = strField(s.vo, beat.stubVo.replace(/\{topic\}/g, topic), `scene ${i + 1} vo`, engineWarnings);
    const caption = (typeof s.caption === 'string' && s.caption.trim()) ? s.caption.trim() : vo;
    const onText = clampOnText(s.onText, i, engineWarnings) || beat.beat;
    const motion = (typeof s.motion === 'string' && s.motion.trim()) ? s.motion.trim() : beat.motion;
    const whyArt = (typeof s.whyArt === 'string' && s.whyArt.trim()) ? s.whyArt.trim() : beat.whyArt;
    return {
      beat: beat.beat,
      vo,
      caption,
      onText,
      motion,
      art: arts[i],
      whyArt,
      clip: beat.clip != null ? beat.clip : (typeof s.clip === 'string' ? s.clip : null),
    };
  });

  // 3. EVERY number is computed here, never by the model.
  const { scenes, totalSec, credits, warnings } = layoutScenes(creativeScenes, { rate, lengthSec });
  // Attach the §3 scene index (the model never supplies it) and emit each scene
  // in the documented key order (i, beat, vo, ...). validateJob is order-independent;
  // this is purely so the produced job reads exactly like the §3 contract.
  const orderedScenes = scenes.map((s, idx) => {
    s.i = idx + 1;
    const out = {};
    for (const k of SCENE_KEYS) out[k] = s[k];
    return out;
  });

  // 4. assemble the §3 job (exact key set — contract.validateJob forbids extras).
  const title = strField(payload.title, `${cap(topic)} — ${spine.templateName}`, 'title', engineWarnings);
  const hook = strField(payload.hook, `You've noticed ${topic}. Here's what's really going on.`, 'hook', engineWarnings);
  const description = strField(payload.description, `A short ${spine.templateName.toLowerCase()} explainer about ${topic}.`, 'description', engineWarnings);
  const thumbText = strField(payload.thumbnail && payload.thumbnail.text, cap(topic).slice(0, 24), 'thumbnail.text', engineWarnings);
  const tags = sanitizeTags(payload.tags, topic, spine.key, engineWarnings);

  const words = orderedScenes.reduce((a, s) => a + countWords(s.vo), 0);

  const job = {
    id: jobId,
    topic,
    subject,
    template: spine.key,
    templateName: spine.templateName,
    audience,
    tone,
    voice,
    aspect,
    music,
    captions,
    title,
    hook,
    totalSec,
    words,
    description,
    tags,
    thumbnail: { text: thumbText, art: orderedScenes[0].art },
    credits,
    warnings: engineWarnings.concat(warnings),
    scenes: orderedScenes,
  };

  // 5. the contract guard — throws on any drift from §3.
  validateJob(job);
  return job;
}

module.exports = { build, makeId, normalizeVoice };
