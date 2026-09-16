"""Recompute the rationale intervention Hodges-Lehmann estimates and cluster-bootstrap intervals.

The locked headline bounds in CLAUDE.md section 4 exist only in prose. No frozen
artifact carries them, and rationale_intervention_summary.json carries only Wilcoxon statistics. This
script derives them from the frozen per-event artifact so that Figure 4 can read
numbers rather than transcribe them, and prints a diff against the locked values.

Per the verification protocol: this is a CHECK. Every value that matches and every
value that does not is listed. A discrepancy is a finding, not something to fix.

Sign convention: diff = rank(genuine) - rank(variant). Lower rank is better, so a
POSITIVE value means the genuine rationale produced the WORSE word.

Run: python scripts/rationale_intervention_effect_bounds.py <path to rationale_intervention_paired_differences.csv>
     (the frozen input lives in final_batch_outputs_20260817_1/rationale_intervention_analysis_full/;
     this script was written in the author's paper workspace and migrated here on
     2026-09-09 with the input path made an argument; logic unchanged)
"""
from __future__ import annotations
import collections, csv, json, sys
from pathlib import Path
import numpy as np

import argparse

_parser = argparse.ArgumentParser(
    description="Recompute the rationale-intervention Hodges-Lehmann estimates and cluster-bootstrap intervals."
)
_parser.add_argument(
    "paired_differences_csv",
    help="paired-differences CSV written by rationale_intervention_analysis.py (rq2_paired_differences.csv in the frozen package)",
)
_parser.add_argument("output_json", nargs="?", default="rationale_intervention_effect_bounds.json")
_parser.add_argument(
    "intervention_root", nargs="?", default=None,
    help="directory holding <game>/rationale_intervention_records.json for the identical-word cross-check",
)
_ARGS = _parser.parse_args()
REPO = Path(__file__).resolve().parents[1]
SRC = Path(_ARGS.paired_differences_csv)
OUT = Path(_ARGS.output_json)
BOOT, SEED = 10_000, 20260819
LOCKED = {"wrong": (73, -5, 472), "filler": (0, -253, 122), "absent": (50, 0, 279)}


def hl(d):
    """Hodges-Lehmann one-sample estimate: median of all Walsh averages."""
    d = np.asarray(d, dtype=float)
    i, j = np.triu_indices(d.size, k=0)
    return float(np.median((d[i] + d[j]) / 2.0))


def game_of(trace_file: str) -> str:
    """Game number is encoded in the trace filename: ..._api_<game>_run<k>_..."""
    parts = trace_file.split("_")
    return parts[parts.index("api") + 1]


def main() -> int:
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    byg = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in csv.DictReader(SRC.open(newline="")):
        if r["diff_genuine_minus_variant"] in ("", "None"):
            continue
        v = float(r["diff_genuine_minus_variant"])
        by[r["contrast"]][r["trace_file"]].append(v)
        byg[r["contrast"]][game_of(r["trace_file"])].append(v)

    rng = np.random.default_rng(SEED)
    out, ok = {}, True
    print(f"source {SRC}   {BOOT:,} cluster-bootstrap resamples, seed {SEED}")
    print(f"{'contrast':10}{'n_events':>9}{'n_runs':>8}{'HL':>8}{'95% CI':>18}"
          f"   locked            match?")
    for c in ("wrong", "filler", "absent"):
        runs = list(by[c])
        flat = [x for k in runs for x in by[c][k]]
        point = hl(flat)
        reps = []
        for _ in range(BOOT):
            samp = [x for k in rng.choice(runs, len(runs)) for x in by[c][k]]
            reps.append(hl(samp))
        lo, hi = np.percentile(reps, [2.5, 97.5])
        lp, ll, lh = LOCKED[c]
        agree = (round(point) == lp)
        ok &= agree
        out[c] = {"n_events": len(flat), "n_runs": len(runs), "hl": point,
                  "ci_lo": float(lo), "ci_hi": float(hi), "locked": list(LOCKED[c]),
                  "seed": SEED, "n_boot": BOOT,
                  # replicates are kept so the figure draws the bootstrap density
                  # from this artifact rather than re-resampling at plot time
                  "replicates": [float(v) for v in reps],
                  # raw paired differences, for the swarm
                  "diffs": [float(v) for v in flat]}
        print(f"{c:10}{len(flat):>9}{len(runs):>8}{point:>+8.1f}"
              f"{f'[{lo:+.0f}, {hi:+.0f}]':>18}   "
              f"{f'{lp:+d} [{ll:+d}, {lh:+d}]':<18}{'point OK' if agree else 'POINT DIFFERS'}")

    # Runs nest inside games, so a game-level cluster is the more conservative
    # unit. Reported side by side; nothing downstream switches unit on its own.
    print("\ngame-level clustering, same seed and resample count:")
    print(f"{'contrast':10}{'n_games':>8}{'HL':>8}{'95% CI (games)':>22}"
          f"{'95% CI (runs)':>22}   widening")
    rng2 = np.random.default_rng(SEED)
    for c in ("wrong", "filler", "absent"):
        games = list(byg[c])
        flat = [x for k in games for x in byg[c][k]]
        point = hl(flat)
        reps = []
        for _ in range(BOOT):
            samp = [x for k in rng2.choice(games, len(games)) for x in byg[c][k]]
            reps.append(hl(samp))
        glo, ghi = np.percentile(reps, [2.5, 97.5])
        rlo, rhi = out[c]["ci_lo"], out[c]["ci_hi"]
        out[c]["game_level"] = {"n_games": len(games), "hl": point,
                                "ci_lo": float(glo), "ci_hi": float(ghi)}
        print(f"{c:10}{len(games):>8}{point:>+8.1f}"
              f"{f'[{glo:+.1f}, {ghi:+.1f}]':>22}{f'[{rlo:+.1f}, {rhi:+.1f}]':>22}"
              f"   {(ghi - glo) / (rhi - rlo):.2f}x")

    # Identical-word rate, recomputed per event from the raw intervention records so it
    # and its interval come from ONE estimator, then checked against the frozen
    # aggregate in rationale_intervention_summary.json. rationale_intervention_word_agreement.csv holds only the
    # aggregate, so an interval cannot be derived from it.
    ev = collections.defaultdict(dict)
    # optional cross-check against the raw intervention outputs when a Contexto checkout is given
    intervention_root = Path(_ARGS.intervention_root) if _ARGS.intervention_root else REPO / "traces" / "rationale_intervention"
    for f in sorted(intervention_root.glob("*/rationale_intervention_records.json")):
        for r in json.load(open(f))["records"]:
            ev[(r["trace_file"], r["child_id"], r["generation"])][r["arm"]] = r.get("proposed_word")
    ident = collections.defaultdict(lambda: collections.defaultdict(list))
    for (tf, _cid, _g), arms in ev.items():
        g = arms.get("genuine")
        for c in ("wrong", "filler", "absent"):
            if c in arms:
                ident[c][tf].append(1.0 if arms[c] == g else 0.0)
    wa = {r["contrast"]: r for r in json.load(
        open(SRC.parent / "rationale_intervention_summary.json"))["word_agreement"]}
    print("\nidentical-word rate, recomputed per event, clustered by run:")
    for c in ("wrong", "filler", "absent"):
        runs = list(ident[c]); flat = [x for k in runs for x in ident[c][k]]
        rate = float(np.mean(flat))
        reps = [float(np.mean([x for k in rng.choice(runs, len(runs)) for x in ident[c][k]]))
                for _ in range(BOOT)]
        lo, hi = np.percentile(reps, [2.5, 97.5])
        froz = wa[c]["word_identity_rate"]
        out.setdefault("identity", {})[c] = {"rate": rate, "ci_lo": float(lo),
                                             "ci_hi": float(hi), "n_events": len(flat),
                                             "frozen_rate": froz}
        print(f"  {c:8} {rate*100:5.2f}%  [{lo*100:.2f}, {hi*100:.2f}]  n={len(flat)}"
              f"   frozen {froz*100:.2f}%  {'MATCH' if abs(rate-froz) < 5e-4 else 'DIFFERS'}")
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
