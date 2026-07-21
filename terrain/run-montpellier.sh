#!/bin/bash
# Exécute la boucle terrain pour la campagne Montpellier Cabinets Recrutement Tech

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

export CAMPAIGN_FILE="campaign-montpellier-cabinet.json"

if [ ! -f "$CAMPAIGN_FILE" ]; then
    echo "❌ Fichier campagne introuvable : $CAMPAIGN_FILE"
    exit 1
fi

echo "🚀 Lancement : campagne Montpellier Cabinets Recrutement Tech"
python3 loop.py

echo "✅ Boucle complétée"
