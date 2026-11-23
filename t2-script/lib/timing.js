'use strict';
/*
 * lib/timing.js
 * The deterministic timing layer. The LLM only writes TEXT (vo / caption /
 * onText / motion / art / whyArt). Every number in the job — sec, words, chars,
 * start, end, cues[].at, totalSec, credits — is computed here, NOT by the model.
 *
 * Why this split is the whole point (spec §3): "the player in studio.js and the
 * encoder in tools_build/driver.py both consume cues as-is — that is why captions
 * stay in sync between preview and file." If the model invented timings, preview
 * and render would drift. So the model is creative; the engine is the clock.
 *
 * Formulas are taken straight from the shipped build:
 *   - engine.js:139  sec = words / 2.6 / rate   (2.6 words/sec ≈ 156 wpm)
 *   - credits ≈ 10 s of finished video          (brand.js: 600 → 597 on a ~30 s job)
 *   - cues: cueSplit() chunks the caption across the scene window
 */

const WORDS_PER_SEC = 2.6; // 156 wpm — the shipped arithmetic (NOT a verified speaking-rate claim; it is the code's constant)

function countWords(s) {
  if (typeof s !== 'string') return 0;
  const t = s.trim();
  return t ? t.split(/\s+/).length : 0;
}

function countChars(s) {
  return typeof s === 'string' ? s.length : 0;
}

function r2(n) {
  return Math.round(n * 100) / 100;
}

// Seconds for a line of narration at a given rate multiplier.
function secFor(words, rate) {
  const r = rate > 0 ? rate : 1;
  return r2(words / (WORDS_PER_SEC * r));
}

// cueSplit: split a caption into readable subtitle windows and place each at a
// time proportional to its word position inside the scene. The first cue sits at
// `start`; the rest are spread across the scene's duration.
function buildCues(caption, start, sec, { maxWordsPerCue = 6 } = {}) {
  const words = (caption || '').trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return [];
  const chunks = [];
  for (let i = 0; i < words.length; i += maxWordsPerCue) {
    chunks.push(words.slice(i, i + maxWordsPerCue).join(' '));
  }
  // distribute by cumulative word count so a longer chunk occupies more time
  const total = words.length;
  const cues = [];
  let seen = 0;
  chunks.forEach((text, idx) => {
    const chunkWords = text.split(/\s+/).length;
    const at = idx === 0 ? r2(start) : r2(start + (seen / total) * sec);
    cues.push({ text, at });
    seen += chunkWords;
  });
  return cues;
}

// Compute all derived numeric fields for one scene. Returns a partial scene.
function sceneTiming({ vo, caption, start, rate }) {
  const words = countWords(vo);
  const chars = countChars(vo);
  const sec = secFor(words, rate);
  const end = r2(start + sec);
  const cues = buildCues(caption, start, sec);
  return { words, chars, sec, start: r2(start), end, cues };
}

// Lay out the whole scene list: contiguous timeline, totalSec, credits, and the
// pacing/drift warnings. Mutates a copy of each scene's numeric fields.
function layoutScenes(scenes, { rate, lengthSec }) {
  const out = [];
  let cursor = 0;
  const warnings = [];
  scenes.forEach((s, idx) => {
    const t = sceneTiming({ vo: s.vo, caption: s.caption, start: cursor, rate });
    const scene = Object.assign({}, s, t);
    out.push(scene);
    cursor = t.end;
    // per-scene pacing warnings (deterministic, not from the model)
    if (scene.words === 0) warnings.push(`scene ${idx + 1} ("${scene.beat}"): empty narration`);
    else if (t.sec < 1.2) warnings.push(`scene ${idx + 1} ("${scene.beat}"): very short (${t.sec}s, ${scene.words} words) — may flash`);
    else if (t.sec > 12) warnings.push(`scene ${idx + 1} ("${scene.beat}"): long (${t.sec}s, ${scene.words} words) — consider splitting`);
    if (countWords(scene.caption) > scene.words + 2) warnings.push(`scene ${idx + 1}: caption longer than narration`);
  });

  const totalSec = r2(cursor);
  const credits = Math.max(1, Math.ceil(totalSec / 10)); // credits ≈ 10 s of finished video

  // drift vs the requested length (the model is asked to size lines to lengthSec;
  // we measure the result instead of forcing it, so totalSec stays honest)
  if (lengthSec && totalSec > 0) {
    const drift = (totalSec - lengthSec) / lengthSec;
    if (Math.abs(drift) > 0.15) {
      warnings.push(`total ${totalSec}s is ${(drift * 100).toFixed(0)}% ${drift > 0 ? 'over' : 'under'} the requested ${lengthSec}s — lines are not sized to length`);
    }
  }

  return { scenes: out, totalSec, credits, warnings };
}

module.exports = { WORDS_PER_SEC, countWords, countChars, secFor, buildCues, sceneTiming, layoutScenes };
