#!/usr/bin/env bash
set -euo pipefail

# Shared by the Resolver follow-up job and the scheduled/manual fallback so both
# paths execute the same report-only research evidence pipeline.
export RESEARCH_REFRESH_AT_UTC="${RESEARCH_REFRESH_AT_UTC:-$(python -c 'from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())')}"

echo "research_refresh_at_utc=${RESEARCH_REFRESH_AT_UTC}"

PYTHONPATH=. pytest -q \
  tests/test_handedness_matchup_lineage_guard.py \
  tests/test_handedness_matchup_audit.py \
  tests/test_catcher_prior_maturity.py \
  tests/test_pitch_arsenal_capture.py \
  tests/test_batter_pitch_whiff_capture.py \
  tests/test_pitch_mix_readiness_audit.py \
  tests/test_pitch_mix_whiff_score_capture.py \
  tests/test_pitch_mix_whiff_forward_evaluation.py \
  tests/test_umpire_k_up_cap_shadow.py \
  tests/test_umpire_context_review_snapshot.py \
  tests/test_umpire_context_review_pipeline.py \
  tests/test_confirmed_lineup_review_snapshot.py \
  tests/test_confirmed_lineup_review_pipeline.py \
  tests/test_research_review_snapshot_freshness.py \
  tests/test_research_evidence_command_center.py \
  tests/test_research_evidence_history.py \
  tests/test_research_evidence_transition_digest.py \
  tests/test_research_manual_review_packet.py \
  tests/test_research_multicell_review_injector.py \
  tests/test_research_manual_review_queue.py \
  tests/test_research_pipeline_freshness_audit.py \
  tests/test_research_context_readiness_workflow.py \
  tests/test_research_context_readiness_runner.py

PYTHONPATH=. python -m training.handedness_matchup_lineage_guard
PYTHONPATH=. python -m training.handedness_matchup_audit \
  --context-log data/handedness_matchup_effective_context.csv
PYTHONPATH=. python -m training.pitch_arsenal_capture
PYTHONPATH=. python -m training.batter_pitch_whiff_capture
PYTHONPATH=. python -m training.pitch_mix_readiness_audit
PYTHONPATH=. python -m training.pitch_mix_whiff_score_capture
PYTHONPATH=. python -m training.pitch_mix_whiff_forward_evaluation
PYTHONPATH=. python -m training.catcher_prior_maturity
PYTHONPATH=. python -m training.umpire_k_up_cap_shadow
PYTHONPATH=. python -m training.umpire_context_review_snapshot
PYTHONPATH=. python -m training.confirmed_lineup_review_snapshot
PYTHONPATH=. python -m training.research_review_snapshot_freshness
PYTHONPATH=. python -m training.research_evidence_command_center
PYTHONPATH=. python -m training.research_evidence_history \
  --observed-at-utc "${RESEARCH_REFRESH_AT_UTC}"
PYTHONPATH=. python -m training.research_evidence_transition_digest \
  --refresh-at-utc "${RESEARCH_REFRESH_AT_UTC}"
PYTHONPATH=. python -m training.research_manual_review_packet \
  --refresh-at-utc "${RESEARCH_REFRESH_AT_UTC}"
PYTHONPATH=. python -m training.research_multicell_review_injector \
  --refresh-at-utc "${RESEARCH_REFRESH_AT_UTC}"
PYTHONPATH=. python -m training.research_manual_review_queue \
  --queued-at-utc "${RESEARCH_REFRESH_AT_UTC}"
PYTHONPATH=. python -m training.research_pipeline_freshness_audit

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add \
  data/handedness_matchup_effective_context.csv \
  data/handedness_matchup_lineage_gate.csv \
  data/handedness_matchup_audit_detail.csv \
  data/handedness_matchup_audit_segments.csv \
  data/handedness_matchup_audit_gate.csv \
  data/catcher_prior_maturity.csv \
  data/catcher_prior_maturity_summary.csv \
  data/pitch_arsenal_context_log.csv \
  data/batter_pitch_whiff_context_log.csv \
  data/pitch_mix_readiness_fields.csv \
  data/pitch_mix_readiness_summary.csv \
  data/pitch_mix_whiff_score_log.csv \
  data/pitch_mix_whiff_forward_detail.csv \
  data/pitch_mix_whiff_forward_summary.csv \
  data/pitch_mix_whiff_forward_gate.csv \
  data/umpire_k_up_cap_shadow_detail.csv \
  data/umpire_k_up_cap_shadow_summary.csv \
  data/umpire_context_review_snapshot.csv \
  data/umpire_context_review_summary.csv \
  data/confirmed_lineup_review_snapshot.csv \
  data/confirmed_lineup_review_summary.csv \
  data/research_review_snapshot_freshness.csv \
  data/research_review_snapshot_freshness_summary.csv \
  data/research_evidence_command_center.csv \
  data/research_evidence_command_center_summary.csv \
  data/research_evidence_history.csv \
  data/research_evidence_history_summary.csv \
  data/research_evidence_transition_digest.csv \
  data/research_evidence_transition_digest_summary.csv \
  data/research_manual_review_packet.csv \
  data/research_manual_review_packet_summary.csv \
  data/research_manual_review_queue.csv \
  data/research_manual_review_queue_summary.csv \
  data/research_pipeline_freshness_audit.csv \
  data/research_pipeline_freshness_summary.csv

if git diff --cached --quiet; then
  echo "No research context readiness changes to commit."
  exit 0
fi

git commit -m "Automate projection capture and game resolution: refresh research context readiness"

for attempt in 1 2 3; do
  git fetch origin main
  if git rebase origin/main; then
    if git push origin HEAD:main; then
      exit 0
    fi
  else
    git rebase --abort || true
    echo "Rebase conflict while refreshing research context readiness; refusing to overwrite main."
    exit 1
  fi
  echo "Push race on attempt ${attempt}; retrying against latest main."
  sleep $((attempt * 2))
done

echo "Research context readiness push failed after 3 attempts."
exit 1
