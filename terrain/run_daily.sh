#!/usr/bin/env bash
# Rituel quotidien terrain — wrapper mince de la boucle autonome (loop.py).
#
# Toute la fiabilité vit dans terrain/loop.py :
#   - reprise idempotente (une étape 'done' n'est pas rejouée)
#   - retry + backoff par étape
#   - journal complet append (terrain/runs.jsonl)
#   - alerte seulement si intervention humaine nécessaire (sortie stderr)
#   - KPIs de funnel (terrain/metrics.py)
#
# Usage :
#   bash terrain/run_daily.sh            # relevé + cycle + push
#   bash terrain/run_daily.sh --relance  # idem + relance Resend
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
exec python3 terrain/loop.py "$@"
