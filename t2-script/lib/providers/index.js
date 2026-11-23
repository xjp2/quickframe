'use strict';
/*
 * providers/index.js — provider registry + selection.
 *
 * Selection order: cfg.provider  >  env QF_T2_PROVIDER  >  default "openai".
 * The default is the real HTTP model. "template" must be chosen explicitly so a
 * production build can never silently fall back to canned narration.
 */
const template = require('./template');
const openai = require('./openai');
const agent = require('./agent');

const REGISTRY = { template, openai, agent };
const DEFAULT_PROVIDER = 'openai';

function resolveProvider(cfg) {
  const name = (cfg && cfg.provider) || process.env.QF_T2_PROVIDER || DEFAULT_PROVIDER;
  const p = REGISTRY[name];
  if (!p) throw new Error(`Unknown provider "${name}". Available: ${Object.keys(REGISTRY).join(', ')}`);
  return p;
}

module.exports = { REGISTRY, DEFAULT_PROVIDER, resolveProvider };
