'use strict';
/*
 * providers/agent.js — "QwenWork's own model", run in-the-loop.
 *
 * This is the honest way to get a real LLM script in THIS sandbox, where there is
 * no model API key wired into a standalone Node process. The engine emits the
 * exact prompt + schema to a file; the QwenWork model (the agent) authors the
 * structured response; the engine reads it back and does the real deterministic
 * normalisation (timing, cues, credits, contract). Nothing is faked: the narration
 * text is genuinely produced by the model, the numbers are genuinely produced by
 * code. No canned text is returned.
 *
 * Protocol:
 *   1. generate() writes   out/prompt-<jobId>.json   ({ system, user, schema })
 *   2. it then reads a response from   cfg.responsePath   (or out/response-<jobId>.json)
 *   3. if the response is absent it throws AgentResponsePendingError, which the CLI
 *      prints as a clean "waiting for model response" state — never a silent stub.
 */
const fs = require('node:fs');
const path = require('node:path');

class AgentResponsePendingError extends Error {
  constructor(promptPath, responsePath) {
    super(`Agent provider: prompt written to ${promptPath}. Waiting for the QwenWork model ` +
      `to author the JSON response at ${responsePath}. Re-run once the response file exists.`);
    this.name = 'AgentResponsePendingError';
    this.promptPath = promptPath;
    this.responsePath = responsePath;
  }
}

module.exports = {
  name: 'agent',
  generate({ cfg, prompt, jobId, outDir }) {
    fs.mkdirSync(outDir, { recursive: true });
    const promptPath = path.join(outDir, `prompt-${jobId}.json`);
    const responsePath = cfg.responsePath || path.join(outDir, `response-${jobId}.json`);

    fs.writeFileSync(promptPath, JSON.stringify({ system: prompt.system, user: prompt.user, schema: prompt.schema }, null, 2), 'utf8');

    if (!fs.existsSync(responsePath)) {
      throw new AgentResponsePendingError(promptPath, responsePath);
    }
    const raw = fs.readFileSync(responsePath, 'utf8');
    let payload;
    try { payload = JSON.parse(raw); }
    catch (e) { throw new Error(`Agent provider: response at ${responsePath} is not valid JSON: ${e.message}`); }
    return payload;
  },
  AgentResponsePendingError,
};
