'use strict';
/*
 * lib/prompt.js
 * Builds the single LLM call for the SCRIPT step of QuickFrame's pipeline
 * (qwen-agents-md.txt §4: topic -> script -> storyboard -> animation ->
 * captions+music -> render -> publish). The script pass turns a topic + cfg into
 * the storyboard-ready text; every number is computed in lib/timing.js.
 *
 * Grounding is the real contract ONLY (§3): the job cfg
 *   {topic, template, lengthSec, aspect, voice, tone, captions, music}
 * and the six spines x five beats in lib/templates.js. The model returns ONLY
 * creative text against a strict JSON schema; the engine is the clock.
 */

const { WORDS_PER_SEC } = require('./timing');

// The exact JSON shape the model must return. Kept as a plain object so the
// provider can serialise it into the prompt (and validate the response).
function responseSchema() {
  return {
    type: 'object',
    required: ['title', 'hook', 'description', 'tags', 'thumbnail', 'scenes'],
    properties: {
      title: { type: 'string', description: 'Short video title, <= 70 chars.' },
      hook: { type: 'string', description: 'One-line hook, <= 140 chars, that makes a viewer stay.' },
      description: { type: 'string', description: '1-3 sentence description for the destination.' },
      tags: { type: 'array', items: { type: 'string' }, description: '3-8 lowercase topic tags.' },
      thumbnail: { type: 'object', required: ['text'], properties: { text: { type: 'string', description: 'Thumbnail headline, <= 6 words.' } } },
      scenes: {
        type: 'array',
        description: 'Exactly 5 scenes, in beat order.',
        items: {
          type: 'object',
          required: ['vo', 'caption', 'onText', 'motion', 'art', 'whyArt'],
          properties: {
            vo: { type: 'string', description: 'Spoken narration for this beat. Short spoken sentences, no bullets.' },
            caption: { type: 'string', description: 'Subtitle line. Usually mirrors vo, may be lightly trimmed.' },
            onText: { type: 'string', description: 'The headline TYPESET onto the frame. <= 6 words. The encoder draws this; do not describe it as image text.' },
            motion: { type: 'string', description: 'One camera/motion verb: pan, draw-on, zoom, build, reveal, cut.' },
            art: { type: 'string', description: 'Art-direction frame id from the pool: f1,f2,f4,s5,s6,vert,vphone,hero.' },
            whyArt: { type: 'string', description: 'One clause: why this shot fits this beat.' },
          },
        },
      },
    },
  };
}

// Target words per scene so totalSec lands near lengthSec.
function targetWordsPerScene(lengthSec, rate, beats) {
  const r = rate > 0 ? rate : 1;
  const total = Math.round(lengthSec * WORDS_PER_SEC * r);
  return Math.max(6, Math.round(total / beats));
}

function buildPrompt(cfg, spine) {
  const rate = (cfg.voice && cfg.voice.rate) || 1;
  const targetWords = targetWordsPerScene(cfg.lengthSec || 30, rate, spine.beats.length);

  const beatPlan = spine.beats
    .map((b, i) => `  ${i + 1}. ${b.beat} — ${b.role} (default shot: ${b.art})`)
    .join('\n');

  const system = [
    'You write the SCRIPT step of QuickFrame, a stickman/whiteboard explainer-video pipeline (topic -> script -> storyboard -> animation -> captions+music -> render -> publish).',
    'Your script becomes the storyboard: one short scene per beat, in the spine\'s beat order.',
    'Write for the EAR, not the eye: short spoken sentences a person reads aloud in one breath.',
    'Never invent statistics, prices, or facts. If a claim is assumed, keep it generic.',
    'The narration (vo) must be specific to THIS topic — do not echo generic template lines.',
    'onText is the words TYPESET onto the frame by the encoder, not painted into an image. Keep it <= 6 words.',
    'Return ONLY a single JSON object that matches the schema. No prose, no markdown fences.',
  ].join(' ');

  const user = [
    `TOPIC: ${cfg.topic}`,
    `SPINE: ${spine.templateName} — ${spine.logline}`,
    `TONE: ${cfg.tone || 'clear, friendly, confident'}`,
    `VOICE RATE: ${rate}x   ASPECT: ${cfg.aspect || '16:9'}   TARGET LENGTH: ${cfg.lengthSec || 30}s`,
    ``,
    `Write exactly ${spine.beats.length} scenes, one per beat, in this order:`,
    beatPlan,
    ``,
    `Size each scene's narration to about ${targetWords} words so the whole script lands near ${cfg.lengthSec || 30}s.`,
    `Use only these frame ids for art: ${spine.beats.map(b => b.art).join(', ')} (you may reassign among them, but keep them distinct across scenes).`,
    ``,
    'Return JSON matching this schema:',
    JSON.stringify(responseSchema()),
  ].join('\n');

  return {
    system,
    user,
    schema: responseSchema(),
    targetWordsPerScene: targetWords,
    // provider-agnostic messages array for an OpenAI-compatible call
    messages: [
      { role: 'system', content: system },
      { role: 'user', content: user },
    ],
  };
}

module.exports = { buildPrompt, responseSchema, targetWordsPerScene };
