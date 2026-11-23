/* =============================================================================
 * QuickFrame — real backend wiring for the Studio Demo "generator" block.
 *
 * WHAT THIS REPLACES
 *   The Hashmeta studio-demo page (page id 6, block `generator`) currently runs
 *   a 100% client-side simulation: startRun() drives a setTimeout "seq", and
 *   finishRun()/recordVideo()/makeFrames() draw stickman frames on a <canvas>
 *   and encode a blob: WebM in the browser. No network. This module replaces
 *   that with the real T1 job service call flow:
 *
 *     form submit -> POST {API_BASE}/jobs -> poll GET {API_BASE}/jobs/<id>
 *       -> render the 7-stage progress from job.stageState + job.log
 *       -> present the signed download URL (job.download.url) in the player.
 *
 * HOW TO APPLY (surgical, keeps the rest of the block intact)
 *   1. At the very top of the generator block's IIFE, set the ONE config value
 *      below (QF_API_BASE). Nothing else in the file should hard-code a host.
 *   2. Replace the bodies of `startRun()` and `finishRun()` with the versions
 *      given here, and DELETE `recordVideo()` and `makeFrames()` (no longer
 *      used). Keep every other helper (setRail, logLine, panel, showError,
 *      clearTimers, resetRail, the `topic`/`state`/`capSel`/`voiceSel`/`video`
 *      references) exactly as the block already defines them — this code uses
 *      those in-scope names.
 *   See README.md §"Applying to the Hashmeta site" for the exact find/replace.
 *
 * The seven stage keys and the job contract are UNCHANGED: the request body is
 * {topic, template, lengthSec, aspect, voice, tone, captions, music, silentVoice?}
 * and progress reads the server's stageState keyed on
 *   script -> boards -> art -> voice -> captions -> encode -> publish
 * ========================================================================== */

/* ---- THE single configurable value ----------------------------------------
 * Local dev / this verification:  http://127.0.0.1:8777
 * After the owner deploys to Hugging Face Spaces, set it to the Space URL:
 *   https://<hf-username>-quickframe.hf.space
 * The service derives its own signed-URL base from the forwarded Host header,
 * so this value only needs to be where the browser sends POST/GET /jobs.
 * ------------------------------------------------------------------------ */
var QF_API_BASE = "https://quickframe-t1.onrender.com";

/* Defaults for controls the storefront UI does not expose (so the request is
 * always a valid job contract). All overridable here — one place. */
var QF_DEFAULT_TEMPLATE = "why";   // one of why|compounding|myth|howto|story|inside
var QF_DEFAULT_MUSIC    = "drive"; // one of chalk|drive|lofi|none
var QF_DEFAULT_LENGTH_S = 15;      // target seconds (service clamps 8..120)

/* Map the storefront's human labels to the exact T1 contract keys. */
var QF_CAPTION_MAP = {
  "Bold pop (word-by-word)": "karaoke",
  "Clean lower-third":       "clean",
  "Karaoke highlight":       "karaoke",
  "None":                    "none"
};
var QF_VOICE_MAP = {
  "Friendly narrator":           "calm-01",
  "Fast explainer":              "bright-01",
  "Calm teacher":                "doc-01",
  "Deadpan dry":                 "doc-01",
  "No voiceover (music only)":   "calm-01"   // + silentVoice:true, see buildCfg
};

/* Map the server's 7 stage keys onto the storefront's 7 rail chips.
 * Rail indices in the block are: 0 topic, 1 script, 2 storyboard, 3 animation,
 * 4 captions+music, 5 render, 6 publish. */
var QF_STAGE_TO_RAIL = {
  script: 1, boards: 2, art: 3, voice: 4, captions: 4, encode: 5, publish: 6
};

/* Build the job contract from the visible controls. */
function buildCfg() {
  var voiceLabel = voiceSel.value;
  var cfg = {
    topic: topic.value.trim(),
    template: QF_DEFAULT_TEMPLATE,
    lengthSec: QF_DEFAULT_LENGTH_S,
    aspect: state.aspect,                      // "16:9" | "9:16"
    voice: QF_VOICE_MAP[voiceLabel] || "calm-01",
    captions: QF_CAPTION_MAP[capSel.value] || "blocks",
    music: QF_DEFAULT_MUSIC
  };
  if (voiceLabel === "No voiceover (music only)") cfg.silentVoice = true;
  return cfg;
}

/* ---- startRun(): the real call flow ------------------------------------- */
function startRun() {
  if (state.running) return;
  errBox.hidden = true;

  var t = topic.value.trim();
  if (t.split(/\s+/).length < 3 || t.length < 12) {
    showError('that prompt was too vague &mdash; try naming a specific thing to explain<br>' +
      '<button type="button" class="btn btn-secondary btn-sm" data-qf-retry>Try again</button>');
    topic.focus();
    return;
  }

  var cfg = buildCfg();
  state.running = true;
  genBtn.disabled = true;
  genLabel.textContent = "Rendering your video…";

  clearTimers();
  resetRail();
  logBody.innerHTML = "";
  zone.hidden = true;
  empty.hidden = false;
  document.querySelector("[data-qf-sheet]").hidden = true;
  setRail(0, "run");
  logLine(0, "topic accepted · " + cfg.topic);

  var jid = null, pollTimer = null, deadline = Date.now() + 300000;

  function stop() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null; } }
  function fail(msg) {
    stop();
    state.running = false; genBtn.disabled = false;
    genLabel.textContent = "Start free — make your first video";
    showError(msg);
  }

  fetch(QF_API_BASE + "/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cfg)
  })
    .then(function (res) {
      if (!res.ok) {
        return res.json().then(function (b) {
          var e = (b && b.error) || {};
          fail("Service rejected the job (" + res.status + "): " +
               (e.message || JSON.stringify(e)));
        }).catch(function () { fail("Service rejected the job (" + res.status + ")."); });
      }
      return res.json();
    })
    .then(function (job) {
      if (!job || !job.id) return;            // already failed above
      jid = job.id;
      setRail(0, "done");
      logLine(0, "job " + jid + " queued");
      pollTimer = setInterval(poll, 1500);
    })
    .catch(function (err) { fail("Could not reach the service: " + err); });

  function poll() {
    if (Date.now() > deadline) { fail("Timed out waiting for the render."); return; }
    fetch(QF_API_BASE + "/jobs/" + jid)
      .then(function (r) { return r.json(); })
      .then(function (j) {
        (j.log || []).forEach(function (l) { logLine(QF_STAGE_TO_RAIL[l.stage] != null ? QF_STAGE_TO_RAIL[l.stage] : 0, "[" + l.stage + "] " + l.line); });
        var ss = j.stageState || {};
        Object.keys(ss).forEach(function (k) {
          var rail = QF_STAGE_TO_RAIL[k];
          if (rail != null && chipsFor(rail)) setRail(rail, ss[k]);
        });
        if (j.state === "done")   { stop(); finish(j); }
        if (j.state === "failed" || j.state === "blocked") {
          stop();
          var b = j.blocker || j.error || {};
          fail((j.state === "blocked" ? "Blocked: " : "Failed: ") + (b.message || JSON.stringify(b)));
        }
      })
      .catch(function () { /* transient poll error; next tick retries */ });
  }

  function chipsFor(rail) { return rail >= 0 && rail <= 6; }

  /* finish(): show the REAL signed MP4. */
  function finish(j) {
    var d = j.download || {}, r = j.result || {};
    if (quotaBump) quotaBump();
    empty.hidden = true;
    zone.hidden = false;
    var shell = document.querySelector("[data-qf-shell]");
    if (shell) shell.classList.toggle("is-vertical", cfg.aspect === "9:16");

    if (d.url) {
      video.src = d.url;            // signed, expiring URL served by the service
      video.load();
      var a = document.querySelector("[data-qf-download]");
      if (a) { a.href = d.url; a.setAttribute("download", "quickframe-" + jid + ".mp4"); }
      setRail(6, "done");
      logLine(6, "publish ready · " + (d.durationSec || r.totalSec || "?") + "s · " +
               Math.round((d.sizeBytes || 0) / 1e6 * 100) / 100 + " MB");
    } else {
      fail("Render finished but no download URL was returned.");
      return;
    }
    (r.warnings || []).forEach(function (w) { logLine(6, "note: " + w); });

    state.running = false;
    genBtn.disabled = false;
    genLabel.textContent = "Start free — make your first video";
    state.run = { topic: cfg.topic, aspect: cfg.aspect, url: d.url, id: jid };
    document.dispatchEvent(new CustomEvent("qf-run-complete", { detail: state.run }));
  }
}
