#!/bin/bash
# After the Stage B jobs: completeness report, the two analyses for every
# condition that has traces, and one archive for the Windows machine.
#
#     bash experiments/stage_b/analyse_stage_b.sh            # from the repository root, venv active
#
# Writes out/stage_b/<model>/<condition>_calibration and _selection, prints
# the checker's report (it ends with a "gaps" list; "none" means complete),
# and leaves $HOME/stage_b_<date>.tgz with traces/stage_b, out/stage_b, logs
# and the job list.

set -uo pipefail
cd "$(dirname "$0")/../.."

python scripts/check_stage_b.py | tee out/stage_b_check.txt
echo

for model_dir in traces/stage_b/*/; do
    model=$(basename "$model_dir")
    for cond_dir in "$model_dir"*/; do
        cond=$(basename "$cond_dir")
        case "$cond" in *intervention*) continue ;; esac            # intervention outputs are already analysed
        case "$cond" in *_noreport) continue ;; esac                # no self-reports to score
        if ! compgen -G "${cond_dir}ea_*_run*_*.json" > /dev/null; then continue; fi
        echo "=== $model / $cond"
        python scripts/environment_calibration.py "${cond_dir}*.json" --output-dir "out/stage_b/$model/${cond}_calibration" || echo "calibration failed for $model/$cond"
        python scripts/environment_selection_response.py "${cond_dir}*.json" --output-dir "out/stage_b/$model/${cond}_selection" --permutations 1000 || echo "selection response failed for $model/$cond"
    done
done

mkdir -p out/stage_b
ARCHIVE="$HOME/stage_b_$(date +%F).tgz"
tar czf "$ARCHIVE" traces/stage_b out/stage_b out/stage_b_check.txt logs experiments/stage_b/submitted_jobs.txt
ls -lh "$ARCHIVE"
echo "archive: $ARCHIVE"
