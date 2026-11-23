"""Run all three T3 acceptance checks in one process and write the report via
Python (not shell redirection, which corrupts under this box's memory pressure).
gc.collect() between phases keeps peak memory low on the ~0.4 GB-free box."""
import os, sys, gc, json
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
import t3_images as t3

TOPICS = [
    ("how contactless payment works", "why"),
    ("why do bonds lose value when rates rise", "compounding"),
    ("the story of the transatlantic cable", "story"),
]

rep = t3.run_test(*TOPICS[0]); gc.collect()
rer = t3.run_reroll_demo(*TOPICS[0]); gc.collect()
ser = t3.run_series_check(TOPICS); gc.collect()

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_report.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump({"boards": rep, "reroll": rer, "series": ser}, f, indent=2)

def pick(d, *ks):
    return {k: d.get(k) for k in ks}
print("boards :", pick(rep, "pass", "boards_pairwise_mean_diff", "min_accent_chroma",
                        "accents_vivid_at_phone_size", "accents_cool",
                        "background_identical_across_cuts"))
print("reroll :", pick(rer, "pass", "stage_region_mean_diff",
                       "glyphs_faithful_to_script", "illustration_changed"))
print("series :", pick(ser, "pass", "each_topic_boards_pass",
                       "character_background_identical", "boards_differ_across_topics",
                       "ink_paper_rule_locked_to_T1"))
