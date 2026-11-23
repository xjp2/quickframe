#!/usr/bin/env node
'use strict';
/*
 * bin/cli.js — run the T2 script engine from the shell.
 *
 *   node bin/cli.js --topic "why you can't tickle yourself" --spine why \
 *                   --seconds 30 --provider template
 *
 * Providers:
 *   template  offline deterministic stub (the OLD engine body) — no model, no keys.
 *   openai    real HTTP call to QWENWORK_LLM_BASE_URL/_API_KEY/_MODEL.
 *   agent     QwenWork model in-the-loop: writes out/prompt-<id>.json, reads a
 *             JSON response (--response), then does the real normalisation.
 *
 * Prints the §3 job JSON to stdout (or --out FILE). Exits 2 on a pending agent
 * response, 3 on a missing model endpoint, 1 on any other error.
 */

const fs = require('node:fs');
const path = require('node:path');
const { build } = require('../engine');
const { SPINE_KEYS } = require('../lib/templates');
const { REGISTRY } = require('../lib/providers');

const HELP = `QuickFrame T2 script engine

  node bin/cli.js --topic "<topic>" [options]

Options
  --topic, -t      (required) the thing to explain
  --spine, -s      one of: ${SPINE_KEYS.join(', ')}   (default: why)
  --seconds, -n    target length in seconds          (default: 30)
  --aspect         ${'16:9 | 9:16'}                     (default: 16:9)
  --voice          voice name, or name@rate e.g. atlas@1.1  (default: neutral)
  --tone           tone string                       (default: clear, friendly, confident)
  --captions       blocks | karaoke | clean | none   (default: blocks)
  --music          chalk | drive | lofi | ai | none  (default: chalk)
  --subject        broader category/niche            (default: explainer)
  --audience       job audience line (optional §3 field) (default: curious general viewers)
  --provider       ${Object.keys(REGISTRY).join(' | ')}   (default: env QF_T2_PROVIDER or openai)
  --response       path to the agent model JSON response (agent provider)
  --out, -o        write JSON to this file instead of stdout
  --help, -h       show this help
`;

function parseArgs(argv) {
  const a = {};
  for (let i = 0; i < argv.length; i++) {
    const tok = argv[i];
    if (!tok.startsWith('-')) continue;
    let key = tok.replace(/^--?/, '');
    const alias = { t: 'topic', s: 'spine', n: 'seconds', o: 'out', h: 'help' };
    key = alias[key] || key;
    if (key === 'help') { a.help = true; continue; }
    // flags that are pure booleans can be added here; today all take a value
    const val = argv[i + 1];
    if (val === undefined || val.startsWith('--')) { a[key] = true; continue; }
    a[key] = val; i++;
  }
  return a;
}

function buildCfg(a) {
  const cfg = {
    topic: a.topic,
    template: a.spine || 'why',
    lengthSec: a.seconds ? Number(a.seconds) : 30,
    aspect: a.aspect || '16:9',
    tone: a.tone || 'clear, friendly, confident',
    captions: a.captions || 'blocks',
    music: a.music || 'chalk',
    subject: a.subject || 'explainer',
  };
  if (a.voice) {
    const [name, rate] = String(a.voice).split('@');
    cfg.voice = { name, rate: rate ? Number(rate) : 1, pitch: 0 };
  }
  if (a.provider) cfg.provider = a.provider;
  if (a.response) cfg.responsePath = path.resolve(String(a.response));
  if (a.audience) cfg.audience = a.audience;
  return cfg;
}

async function main() {
  const a = parseArgs(process.argv.slice(2));
  if (a.help || !a.topic) { process.stdout.write(HELP); process.exit(a.help ? 0 : 2); }

  const cfg = buildCfg(a);
  let job;
  try {
    job = await build(cfg);
  } catch (e) {
    if (e && e.name === 'AgentResponsePendingError') {
      process.stderr.write(
        `\n[agent provider] waiting for the QwenWork model to author the response.\n` +
        `  prompt   -> ${e.promptPath}\n` +
        `  response <- ${e.responsePath}\n` +
        `Write the schema-shaped JSON there, then re-run.\n\n`
      );
      process.exit(2);
    }
    if (e && e.name === 'ModelNotConfiguredError') {
      process.stderr.write(`\n[openai provider] ${e.message}\n\n`);
      process.exit(3);
    }
    process.stderr.write(`\n[error] ${e.message}\n\n`);
    process.exit(1);
  }

  const json = JSON.stringify(job, null, 2);
  if (a.out) {
    const outPath = path.resolve(String(a.out));
    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    fs.writeFileSync(outPath, json + '\n', 'utf8');
    process.stderr.write(`wrote ${outPath}  (${job.scenes.length} scenes, ${job.totalSec}s, ${job.words} words, ${job.credits} credits, ${job.warnings.length} warnings)\n`);
  } else {
    process.stdout.write(json + '\n');
  }
}

main().catch((e) => { process.stderr.write(`\n[fatal] ${e && e.stack ? e.stack : e}\n`); process.exit(1); });
