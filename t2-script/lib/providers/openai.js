'use strict';
/*
 * providers/openai.js — the real LLM-backed call.
 *
 * It speaks the OpenAI /chat/completions wire format, which is what "QwenWork's
 * own model" exposes when an endpoint is configured. It reads:
 *   QWENWORK_LLM_BASE_URL   (e.g. https://.../v1)   [required]
 *   QWENWORK_LLM_API_KEY    (bearer token)           [required]
 *   QWENWORK_LLM_MODEL      (model id)               [required]
 *
 * There is NO hardcoded key and NO silent fallback. If the endpoint is not
 * configured, it throws ModelNotConfiguredError — the engine surfaces that as a
 * blocker instead of quietly returning canned text (per the user's standing rule:
 * never present a simulated pipeline as a working backend).
 */
const http = require('node:http');
const https = require('node:https');
const { URL } = require('node:url');

class ModelNotConfiguredError extends Error {
  constructor(missing) {
    super(`LLM endpoint not configured. Missing env: ${missing.join(', ')}. ` +
      `Set QWENWORK_LLM_BASE_URL / QWENWORK_LLM_API_KEY / QWENWORK_LLM_MODEL, ` +
      `or run with --provider agent (QwenWork model in-the-loop) / --provider template (offline stub).`);
    this.name = 'ModelNotConfiguredError';
    this.missing = missing;
  }
}

function postJson(urlStr, headers, bodyObj, timeoutMs = 60000) {
  return new Promise((resolve, reject) => {
    let url;
    try { url = new URL(urlStr); } catch (e) { return reject(new Error(`bad base url: ${urlStr}`)); }
    const lib = url.protocol === 'http:' ? http : https;
    const payload = Buffer.from(JSON.stringify(bodyObj), 'utf8');
    const req = lib.request(url, {
      method: 'POST',
      headers: Object.assign({ 'content-type': 'application/json', 'content-length': payload.length }, headers),
      timeout: timeoutMs,
    }, (res) => {
      const chunks = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => {
        const text = Buffer.concat(chunks).toString('utf8');
        if (res.statusCode < 200 || res.statusCode >= 300) {
          return reject(new Error(`LLM HTTP ${res.statusCode}: ${text.slice(0, 400)}`));
        }
        try { resolve(JSON.parse(text)); } catch (e) { reject(new Error(`LLM non-JSON response: ${text.slice(0, 400)}`)); }
      });
    });
    req.on('timeout', () => { req.destroy(new Error('LLM request timed out')); });
    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}

// strip ```json fences if a model wraps despite instructions
function extractJson(text) {
  if (!text) throw new Error('empty model content');
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  const raw = fenced ? fenced[1] : text;
  const start = raw.indexOf('{');
  const end = raw.lastIndexOf('}');
  if (start === -1 || end === -1) throw new Error('no JSON object in model content');
  return JSON.parse(raw.slice(start, end + 1));
}

module.exports = {
  name: 'openai',
  async generate({ prompt, cfg }) {
    const base = process.env.QWENWORK_LLM_BASE_URL;
    const key = process.env.QWENWORK_LLM_API_KEY;
    const model = process.env.QWENWORK_LLM_MODEL;
    const missing = [];
    if (!base) missing.push('QWENWORK_LLM_BASE_URL');
    if (!key) missing.push('QWENWORK_LLM_API_KEY');
    if (!model) missing.push('QWENWORK_LLM_MODEL');
    if (missing.length) throw new ModelNotConfiguredError(missing);

    const body = {
      model,
      messages: prompt.messages,
      temperature: cfg.temperature != null ? cfg.temperature : 0.7,
      response_format: { type: 'json_object' },
    };
    const endpoint = base.replace(/\/$/, '') + '/chat/completions';
    const data = await postJson(endpoint, { authorization: `Bearer ${key}` }, body);
    const content = data && data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content;
    if (!content) throw new Error('LLM response had no message content: ' + JSON.stringify(data).slice(0, 300));
    return extractJson(content);
  },
  ModelNotConfiguredError,
};
