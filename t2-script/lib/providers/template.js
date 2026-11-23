'use strict';
/*
 * providers/template.js — the deterministic stub (the OLD engine body), kept as an
 * explicit offline provider. Same topic ⇒ same script, byte-for-byte. This is what
 * verify.js uses to prove the contract + timing layer are stable and to prove the
 * LLM path genuinely CHANGES the narration (acceptance: vo differs from template).
 *
 * It is NOT the default. It is only selected with provider:"template" so a build
 * never silently degrades to canned text.
 */
const { stubVoFor } = require('../templates');

function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }

module.exports = {
  name: 'template',
  // returns the same "model payload" shape the real providers return
  generate({ cfg, spine }) {
    const scenes = spine.beats.map((b) => {
      const vo = stubVoFor(b, cfg.topic);
      return {
        vo,
        caption: vo,
        onText: b.beat,
        motion: b.motion,
        art: b.art,
        whyArt: b.whyArt,
      };
    });
    return {
      title: `${cap(cfg.topic)} — ${spine.templateName}`,
      hook: `You've noticed ${cfg.topic}. Here's what's really going on.`,
      description: `A short ${spine.templateName.toLowerCase()} explainer about ${cfg.topic}.`,
      tags: [cfg.topic.split(/\s+/)[0].toLowerCase(), spine.key, 'explainer'],
      thumbnail: { text: cap(cfg.topic).slice(0, 24) },
      scenes,
    };
  },
};
