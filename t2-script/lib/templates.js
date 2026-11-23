'use strict';
/*
 * lib/templates.js
 * The spine beat-sheets: 6 spines × 5 beats (spec §2/T2: "Spine beat-sheets live
 * in TEMPLATES; 6 spines × 5 beats").
 *
 * A spine is STRUCTURE, not content. Each beat carries:
 *   beat   — the label shown in the beat-sheet (stable, human-readable)
 *   role   — the instruction handed to the LLM for that beat (what it must do)
 *   art    — default art-direction frame id from the on-disk pool (FRAMES, engine.js:6)
 *   whyArt — the shot-type rationale (T3 keeps artFor as the art-direction layer)
 *   motion — default camera/motion verb
 *   clip   — default motion-clip slot (null until a clip is generated)
 *   stubVo — the deterministic fallback narration (the OLD stub text).
 *
 * The LLM provider must produce vo that DIFFERS from stubVo (acceptance test).
 * The template provider reuses stubVo verbatim => byte-for-byte the old stub
 * behaviour (same topic ⇒ same script), which is what the regression test checks.
 *
 * Spines drafted from spec §6: why, compounding, myth, howto, story, inside.
 */

// On-disk storyboard pool (engine.js:6). artFor maps a beat to one of these;
// within a single job we keep them distinct so no art repeats (studio.js flow:
// "Re-roll the boards → art labels change, no art repeats").
const FRAMES = ['f1', 'f2', 'f4', 's5', 's6', 'vert', 'vphone', 'hero'];

// Each spine: 5 beats. `art` defaults are chosen so the 5 beats in a job use 5
// distinct frames from the pool.
const TEMPLATES = {
  why: {
    templateName: 'Why it happens',
    logline: 'Explain the real cause behind a thing people experience but misunderstand.',
    beats: [
      { beat: 'The question',     role: 'Open on the exact thing the viewer notices and quietly asks "why?".', art: 'hero',  whyArt: 'wide establishing shot of the everyday moment', motion: 'pan',   clip: null, stubVo: 'You have noticed {topic}. It happens all the time, and almost nobody can explain it.' },
      { beat: 'The guess',        role: 'State the common, intuitive explanation people reach for.',          art: 'f1',    whyArt: 'simple two-object concept sketch',           motion: 'draw-on', clip: null, stubVo: 'The usual answer about {topic} feels obvious. It is also wrong.' },
      { beat: 'The real mechanism', role: 'Name the actual mechanism in one plain, spoken sentence.',         art: 'f2',    whyArt: 'close-in diagram of the mechanism',           motion: 'zoom',  clip: null, stubVo: 'The truth behind {topic} is smaller and more mechanical than it looks.' },
      { beat: 'The proof',        role: 'Give one concrete example or test that shows the mechanism is real.', art: 'f4',   whyArt: 'worked-example panel',                      motion: 'build', clip: null, stubVo: 'Watch what happens to {topic} when you test it. The mechanism shows itself.' },
      { beat: 'The takeaway',     role: 'Land the single idea the viewer should remember.',                   art: 's6',    whyArt: 'comparison: guess vs truth',                motion: 'reveal', clip: null, stubVo: 'So {topic} is not magic. It is one cause doing its job every time.' },
    ],
  },
  compounding: {
    templateName: 'It compounds',
    logline: 'Show how small repeated steps bend into a large outcome over time.',
    beats: [
      { beat: 'The seed',     role: 'Introduce the tiny starting amount or first action.',        art: 'hero',  whyArt: 'single small object, lots of space',    motion: 'pan',   clip: null, stubVo: 'It starts with one small move: {topic}.' },
      { beat: 'First cycle',  role: 'Show one repetition and how it barely seems to matter.',     art: 'f1',    whyArt: 'two identical steps side by side',      motion: 'draw-on', clip: null, stubVo: 'Do {topic} once. Then again. Nothing looks different.' },
      { beat: 'The curve bends', role: 'Reveal the moment growth stops being linear.',            art: 'f2',    whyArt: 'line graph turning upward',             motion: 'build', clip: null, stubVo: 'But {topic} keeps its gains, and the line starts to bend up.' },
      { beat: 'The inflection', role: 'Point at the threshold where the effect becomes obvious.', art: 's5',    whyArt: 'marker crossing a threshold',           motion: 'zoom',  clip: null, stubVo: 'There is a point where {topic} flips from invisible to undeniable.' },
      { beat: 'The endgame',  role: 'Land the big result and the one thing to do about it.',      art: 's6',    whyArt: 'small vs large comparison',             motion: 'reveal', clip: null, stubVo: 'That is what {topic} becomes. Start early, stay consistent.' },
    ],
  },
  myth: {
    templateName: 'Myth vs fact',
    logline: 'Take a widely-held belief apart and replace it with what is actually true.',
    beats: [
      { beat: 'The myth',        role: 'State the popular belief plainly, as believers say it.',   art: 'hero',  whyArt: 'big bold claim on screen',              motion: 'pan',   clip: null, stubVo: 'Everyone says this about {topic}. It is one of the most repeated ideas out there.' },
      { beat: 'Why it feels true', role: 'Explain the intuition that makes the myth believable.',   art: 'f1',    whyArt: 'relatable everyday scene',                motion: 'draw-on', clip: null, stubVo: 'It feels right, because {topic} looks exactly like the story.' },
      { beat: 'Where it came from', role: 'Trace the origin or the half-truth behind it.',          art: 'f2',    whyArt: 'timeline / source sketch',                motion: 'zoom',  clip: null, stubVo: 'The idea about {topic} started from a real fact, then got stretched.' },
      { beat: "What's actually true", role: 'Give the correct version in one clean sentence.',      art: 's5',    whyArt: 'cross out, replace',                      motion: 'build', clip: null, stubVo: 'Here is the truth about {topic}, stripped of the myth.' },
      { beat: 'What to believe', role: 'Land the corrected takeaway and what to do with it.',      art: 's6',    whyArt: 'before/after belief swap',              motion: 'reveal', clip: null, stubVo: 'So on {topic}, believe this instead. It changes what you do next.' },
    ],
  },
  howto: {
    templateName: 'How to',
    logline: 'Walk the viewer from a goal to a done result in clear steps.',
    beats: [
      { beat: 'The goal',   role: 'Name the outcome and why it is worth the effort.',        art: 'hero',  whyArt: 'destination / finished state',          motion: 'pan',   clip: null, stubVo: 'Here is how {topic} actually works, start to finish.' },
      { beat: 'Step one',   role: 'Give the first concrete action, no fluff.',               art: 'f1',    whyArt: 'hand performing first action',            motion: 'draw-on', clip: null, stubVo: 'First, set up {topic} the right way. One thing only.' },
      { beat: 'Step two',   role: 'Give the second action, building on the first.',          art: 'f2',    whyArt: 'second action, connected to first',     motion: 'build', clip: null, stubVo: 'Next, {topic} needs the piece that most people skip.' },
      { beat: 'Step three', role: 'Give the final action or the common pitfall to avoid.',   art: 's5',    whyArt: 'checkmark / pitfall flag',              motion: 'zoom',  clip: null, stubVo: 'Then finish {topic} and dodge the one mistake that ruins it.' },
      { beat: 'The result', role: 'Show the done state and the single most important tip.',  art: 's6',    whyArt: 'finished result, highlighted',          motion: 'reveal', clip: null, stubVo: 'That is {topic} done. Repeat the steps and it gets faster.' },
    ],
  },
  story: {
    templateName: 'The story',
    logline: 'Tell a short real or reconstructed story that teaches one idea.',
    beats: [
      { beat: 'The setup',   role: 'Introduce the person/subject and the ordinary starting point.', art: 'hero',  whyArt: 'character in a scene',                  motion: 'pan',   clip: null, stubVo: 'It begins with {topic}, in a perfectly ordinary place.' },
      { beat: 'The turn',    role: 'Introduce the event that changes everything.',                  art: 'f1',    whyArt: 'disrupting moment',                     motion: 'draw-on', clip: null, stubVo: 'Then something shifts, and {topic} is no longer routine.' },
      { beat: 'The struggle', role: 'Show the difficulty or the cost of the turn.',                 art: 'f2',    whyArt: 'obstacle / tension',                    motion: 'zoom',  clip: null, stubVo: 'The hard part of {topic} is where most people give up.' },
      { beat: 'The reveal',  role: 'Deliver the outcome and what it actually turned on.',           art: 's5',    whyArt: 'payoff moment',                       motion: 'build', clip: null, stubVo: 'In the end, {topic} came down to one decision made early.' },
      { beat: 'The lesson',  role: 'Land the single idea the story teaches.',                       art: 's6',    whyArt: 'moral, isolated',                     motion: 'reveal', clip: null, stubVo: 'The lesson of {topic} is bigger than the story itself.' },
    ],
  },
  inside: {
    templateName: 'Inside the system',
    logline: 'Open up a process or product and show the hidden machinery and tradeoffs.',
    beats: [
      { beat: 'The surface',     role: 'Show what the user sees and takes for granted.',            art: 'hero',  whyArt: 'clean exterior view',                   motion: 'pan',   clip: null, stubVo: 'On the surface, {topic} looks simple. You just use it.' },
      { beat: 'Under the hood',  role: 'Reveal the first layer of real machinery.',                 art: 'f2',    whyArt: 'exploded / cutaway view',               motion: 'zoom',  clip: null, stubVo: 'Lift the lid on {topic} and there is work happening you never see.' },
      { beat: 'The hidden step', role: 'Name the step nobody thinks about but everything depends on.', art: 's5',  whyArt: 'one highlighted component',             motion: 'build', clip: null, stubVo: 'The quiet step inside {topic} is the one that does the heavy lifting.' },
      { beat: 'The tradeoff',    role: 'Explain the cost or compromise built into the design.',      art: 's6',    whyArt: 'balance / two-sided',                   motion: 'draw-on', clip: null, stubVo: 'Every choice in {topic} trades something away. Here is the price.' },
      { beat: 'The big picture', role: 'Zoom out to why the whole thing is built this way.',         art: 'f1',    whyArt: 'system-wide view',                      motion: 'reveal', clip: null, stubVo: 'Step back and {topic} makes sense: it is built for one priority.' },
    ],
  },
};

const SPINE_KEYS = Object.keys(TEMPLATES);

// Attach the spine key onto each template object so downstream code (the
// template provider's tags, the engine's job.template) can read `spine.key`
// without re-deriving it. Done once at load; the value is the object's own key.
SPINE_KEYS.forEach((k) => { TEMPLATES[k].key = k; });

function getSpine(key) {
  const spine = TEMPLATES[key];
  if (!spine) throw new Error(`Unknown spine "${key}". Available: ${SPINE_KEYS.join(', ')}`);
  return spine;
}

// Deterministic stub narration for a beat (the OLD engine body). Substitutes the
// topic so same topic ⇒ same line, exactly like the stub.
function stubVoFor(beat, topic) {
  return beat.stubVo.replace(/\{topic\}/g, topic).replace(/\{Topic\}/g, cap(topic));
}

function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }

module.exports = { TEMPLATES, SPINE_KEYS, FRAMES, getSpine, stubVoFor };
