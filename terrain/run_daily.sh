#!/usr/bin/env bash
# Rituel quotidien terrain — 100 % API directes, zéro dépendance MCP.
#
# Relevé Stripe (StripeSource, clé STRIPE_API_KEY) → cycle V9 → log → push.
# Avec --relance : envoi de la relance via Resend (RESEND_API_KEY).
#
# FILET : chaque étape qui dépend d'un secret vérifie sa présence ; si absent,
# elle le signale et passe (jamais d'action à l'aveugle), le script continue.
#
# Usage :
#   bash terrain/run_daily.sh              # relevé + cycle + push
#   bash terrain/run_daily.sh --relance    # idem + relance Resend
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1
BRANCH="claude/system-architect-rules-9zz9v1"
RELANCE=0
[ "${1:-}" = "--relance" ] && RELANCE=1

echo "=== Rituel terrain $(date -u +%F' '%T)Z ==="

# 1) Relevé Stripe + cycle V9 (connector-free)
if [ -n "${STRIPE_API_KEY:-}" ]; then
  echo "[Stripe] relevé + cycle…"
  echo "a" | python3 -m ai_cos.cli --source stripe --data-dir terrain \
    || echo "[Stripe] FILET : le cycle a échoué (voir erreur ci-dessus)."
else
  echo "[Stripe] FILET : STRIPE_API_KEY absent → relevé sauté (voir terrain/SETUP-SECRETS.md)."
fi

# 2) Relance Resend (jour J+2 seulement), connector-free
if [ "$RELANCE" -eq 1 ]; then
  if [ -n "${RESEND_API_KEY:-}" ]; then
    echo "[Resend] relance des cibles 'pending'…"
    python3 terrain/outreach.py --relance \
      || echo "[Resend] FILET : au moins un envoi a échoué (voir sortie)."
  else
    echo "[Resend] FILET : RESEND_API_KEY absent → relance sautée (voir terrain/SETUP-SECRETS.md)."
  fi
fi

# 3) Persistance git (le token GITHUB_TOKEN est déjà dans l'environnement)
if ! git diff --quiet -- terrain/ || ! git diff --cached --quiet -- terrain/; then
  echo "[git] commit + push terrain/…"
  git add terrain/
  git commit -q -m "terrain: rituel quotidien automatisé ($(date -u +%F))" || true
  for i in 1 2 3 4; do
    git push -u origin "$BRANCH" && break || sleep $((2 ** i))
  done
else
  echo "[git] rien à committer."
fi

echo "=== Fin rituel ==="
