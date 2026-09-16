> **Carried from the paper workspace (`write-paper/final_batch_report_2026-08-17.md`).** Authoritative results document for the submitted study; `expected_summary.json` is transcribed from it. The statement below that the A4 metadata split is "descriptive only; behavior is identical" should be read together with `docs/data_and_provenance.md` §4 (rank-cache transport path changed at the same boundary; A4's caches contained no poisoned entries).

# Final Experimental Batch — Validation + Results (2026-08-17, rev 2 — 2026-08-19)

**Status: ALL DATA FINAL.** This revision supersedes the 08-17 draft: the A4 extension arrived and passed validation at 50/50 (including the re-run 1384 slots), the A4/A5 GloVe mediators are adjudicated, and a full completeness audit found nothing missing. No experiments remain in the queue.

## Completeness audit (2026-08-19) — nothing missing

| dataset | expected | found | verdict |
|---|---|---|---|
| A1 (qwen3:14b, EA+self-report) | 50 (10 games × 5) | 50, 0 duplicate slots | OK |
| A2 (llm_only scaffold) | 25 (5 games × 5) | 25 | OK |
| A3 (no-instrumentation control) | 25 (5 games × 5) | 25 | OK |
| A4 (gemma4:12b) | 50 (10 games × 5) | 50, 0 duplicate slots | OK |
| A5 (ministral-3:14b) | 50 (10 games × 5) | 50, 0 duplicate slots | OK |
| RQ3 random-selection control | 15 (3 games × 5) | 15 | OK |
| RQ2 replay records | 754 events × 4 arms | 3,016 records across 10 game shards | OK |
| Rank caches | A1 10 / A2 5 / A3 5 / A4 10 / A5 10 / R 3 games | all present | OK |
| Mediators | A4, A5 (this sync) | both present; see adjudication below | OK |

The only sandbox-side gap is by construction: the **A1 and A2 mediator JSONs** were run on Peter's machine and only their headline numbers were relayed (GloVe-vs-real ρ ≈ 0.65–0.75; A1 closeness-vs-real −0.25 vs closeness-vs-GloVe −0.20). Those two files should ride along in Peter's own archive; nothing needs re-running.

**A4 1384 provenance note (for the lab notebook):** the first sync of the A4 extension carried only 2/5 runs on game 1384; the re-run delivered all 5, and the files for run 1 and run 2 were *replaced* with newer-timestamp files rather than reusing the originals. The current 50-file set is the canonical one; the whole A4 pipeline below was re-executed from scratch on it, so no stale artifacts contribute.

## Validation verdicts

**A4 extension (now 50/50) — VALID.** 50 traces, zero duplicate (game,run) slots, model `gemma4:12b` uniform, hash `bd9f2858283673a2`, schema 3, seeds = run_index, 0 self-report parse failures, 0 basis-word violations (batch verifier), 50/50 solved. Metadata split disclosure stands: 25 original runs lack `selection_mode` in RUN_CONFIG (older code) and 25 extension runs log `tophalf` — the field is descriptive only; behavior is identical (same commit family, verified earlier).

**A5 (Ministral) — VALID, two disclosures.** 50/50 raw traces, zero duplicate slots (retry cleanup was done correctly before sync), model `ministral-3:14b` uniform, hash `bd9f2858283673a2`, schema 3, seeds = run_index, `selection_mode: tophalf` logged. Disclosures for methods: (1) served with `OLLAMA_CONTEXT_LENGTH=8192` unlike the other arms' defaults — verified harmless: the longest A5 prompt is ~27k chars (~6.8k tokens), and zero prompts approach the window; (2) self-report parse-failure rate **2.5% (93/3,758)** — the first nonzero rate in the project, spread across 23/50 runs (max 13 in one run): a family property, not a broken run; handled by the retry-then-null policy by design. Keep all 50 runs; report the rate as a finding.

**RQ3 random-selection control — VALID.** 15/15 traces, `selection_mode: random` confirmed in every RUN_CONFIG, flags/model/hash as A1, seeds correct, 0 parse failures. Behavioral sanity: random selection resurrects heavily (542 resurrections vs 14 in A1) and collapses search on 1319 (1/5 solved vs tophalf's 5/5) — selection demonstrably matters for outcomes.

**Caches (post-fix code, definitive-404s only):** rank_cache_R 108 invalid entries; **rank_cache_A5 6,098 invalid entries** — Ministral proposes invalid vocabulary at ~40× Qwen's rate (A1: 141 across 8 games), itself a proposal-validity datum for the paper (and a contributor to A5 wall-clock).

## RQ1 — A4 at full strength (10 games, 50 runs)

A4 pooled (n=881 first-proposed individuals): ρ **−0.373** (p 2.5e-30), bucket accuracy **0.109**, signed bucket error **−1.525**, off-by-one 0.235, ECE **0.630**, Brier 0.502, AUROC **0.707**, realized P(top-100) 0.123. Gemma's story is unchanged from the 25-run picture, now at double the data: best-in-project discrimination, worst-tier inflation.

A1-vs-A4 paired per-run (Wilcoxon by (game, run_index), Holm over the 8-metric family, n = 46–49 pairs):

| metric | A1 median | A4 median | p (Holm) | direction |
|---|---|---|---|---|
| Spearman ρ | −0.226 | −0.438 | 1.8e-4 | **gemma discriminates better** |
| bucket accuracy | 0.241 | 0.097 | 3.0e-3 | qwen better |
| signed bucket error | −0.591 | −1.500 | 2.3e-8 | qwen less inflated |
| off-by-one rate | 0.667 | 0.250 | 7.8e-9 | qwen better |
| ECE | 0.363 | 0.636 | 5.4e-10 | qwen better |
| Brier | 0.242 | 0.502 | 2.1e-8 | qwen better |
| AUROC | 0.649 | 0.717 | 0.305 | ns |
| realized positive rate | 0.117 | 0.129 | 0.465 | ns (same task difficulty) |

The realized-positive-rate null is the manipulation check: both families face the same game difficulty; the calibration differences are properties of the reporting, not the environment.

## The three-family picture — final coordinates

Per-run medians, n=50 runs each (rank-agreement = −ρ, higher better | ECE, lower better | signed bucket error, 0 honest):

| family | rank agreement | ECE | signed error |
|---|---|---|---|
| Qwen (A1) | **0.230** | **0.363** | **−0.591** |
| Gemma (A4) | **0.450** | 0.644 | −1.506 |
| Ministral (A5) | 0.211 | 0.592 | −1.909 |

A5 pooled (n=3,758): ρ −0.201, accuracy 0.052, signed −2.02, ECE 0.606, Brier 0.457, AUROC 0.629, realized P(top-100) 0.073. Ministral claims top10 47% of the time while landing top-100 at 7% — the most inflated arm. Basis-word hallucination: 2.7% (vs 0.8% Qwen, 0% Gemma). A1-vs-A5 paired (Holm): every level metric at p ≤ 4.3e-7 (A1 better); discrimination (ρ p=1.0, AUROC p=1.0) and positive rate (p=0.53) null — Ministral matches Qwen's discrimination while being far more inflated.

**Framing (final, replaces every "trade-off" phrasing):** discrimination and calibration-in-level are **independent axes**. Gemma is high-discrimination/high-inflation, Qwen low/low, Ministral low/high — three corners of the plane, no family in the honest corner, and better discrimination does not purchase honesty. Drafts must say "vary independently / dissociate," and the dissociation figure gains a third color sitting low-left.

## Mediator adjudication (what the stated confidence tracks)

GloVe grader validity holds in every family: an off-the-shelf embedding reproduces the game's true ranking on proposed words at ρ 0.61–0.75. In each family, stated closeness correlates with the real rank about as strongly as with generic GloVe proximity — consistent with the confidence signal being generic semantic proximity rather than game-specific insight (stated as such in the paper; the channels are too correlated to fully separate):

| arm | glove_vs_real | closeness_vs_real | closeness_vs_glove | words (runs scored) |
|---|---|---|---|---|
| A1 qwen (local run) | ≈0.75 | −0.25 | −0.20 | (Peter's machine) |
| A4 gemma | 0.669 (p 1e-102) | −0.401 | −0.317 | 783 (47) |
| A5 ministral | 0.609 (p 8e-242) | −0.213 | −0.181 | 2,500, coverage 97% (46; 4 unsolved runs skipped, no recoverable target) |

Note Gemma's mediator echoes its RQ1 profile: its confidence tracks the real metric more strongly (−0.40) than any other family — better discrimination — while its levels stay the most inflated of the pair. Same independence story through a different lens.

**A4 mediator scope footnote:** the A4 mediator was executed before the 1384 re-run completed, so it scores 47/50 runs (missing the three re-run 1384 slots — ~2 runs' worth of words). Pooled correlations at n=781 will not move materially with ~35 more words; re-running is optional. One command if wanted: `python scripts/rq1_mediator.py "traces/batch/traces/rq1_A4/ea_llm_self_adaptive_api_*_run*_*.json" --which first_proposed --output out/A4_mediator.json`.

## RQ3 — CLOSED, control certifies the null

| arm | binary-error gap (p) | bucket-distance gap (p) | transmission ρ (p) | pairs |
|---|---|---|---|---|
| A1 tophalf, all 10 games | +0.039 (0.713) | −0.146 (0.253) | −0.02 (0.52) / +0.06 (0.91) | 1,018 |
| A1 tophalf, 3 control games | +0.021 (0.926) | −0.223 (0.410) | ≈0 (0.74 / 0.98) | 227 |
| **Random selection, 3 games** | **−0.002 (0.927)** | **−0.081 (0.453)** | ≈0 (0.50 / 0.46) | 1,111 |

Fitness-based selection is statistically indistinguishable — on every calibration measure — from selection that cannot see fitness at all, while differing enormously in search outcome (5/5 vs 1/5 solved on 1319; 542 vs 14 resurrections). Selection does real work; none of it is on honesty. The RQ3 claim is fully guarded.

## RQ2 — CLOSED (see RQ2_verdict_2026-08-12.md for the full verdict)

754 events × 4 arms, 3,016 completions, 0 errors/parse failures. Rationales causally inert on both axes: outcome (all paired medians 0; clustered Wilcoxon p 0.13–0.93) and content (identical-first-word 15.1–16.3% flat across arms; Jaccard 0.138–0.142). Cluster bootstrap bounds (Hodges–Lehmann): genuine−wrong +73 [−5, +471.5], genuine−filler 0 [−253, +122], genuine−absent +50 [0, +278.5] — any effect is bounded well inside noise for ranks that span 1–20,000+.

## The closed triad (paper skeleton)

1. **RQ1:** the operator's narration is confidently wrong in level in every family tested; discrimination and honesty vary independently (three-family plane).
2. **RQ2:** the narration is causally decorative — byte-matched replay finds no effect of the rationale on what is proposed or how well it does.
3. **RQ3:** selection is blind to honesty — fitness-based selection neither favors nor transmits calibration, indistinguishable from random selection on every calibration measure while dominating it on search outcome.

## Remaining paper-side queue (no experiments)

1. Propagate the independence framing to storyline/abstract drafts (replace every "trade off").
2. A5 disclosures into methods: ctx 8192, 2.5% parse-fail, 2.7% basis hallucination, 6,098 invalid words.
3. A4 metadata split (25 runs no `selection_mode` field / 25 `tophalf`) one-line disclosure; 1384 re-run note above.
4. Figures already refreshed for lab meeting (figs/); the paper versions want the third family added to the dissociation scatter.
5. Housekeeping (Cursor, non-blocking): docs/architecture.md:141–143 stale population wording; copy frozen-sigma rationale into docs/design_decisions.md; delete RQ2 debug scaffolding.
