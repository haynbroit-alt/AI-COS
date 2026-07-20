# Couche fiabilité & autonomie de la boucle terrain

Réponse aux 4 exigences « 10/10 ». Cœur : `terrain/loop.py` (stdlib, testé).

| Exigence | Où | Comment |
|---|---|---|
| **Reprise après panne** | `loop.py` : `loop_state.json` + `reset_if_new_day` | État par jour ; une étape `done` n'est jamais rejouée (pas de double cycle, pas de double envoi), une étape `failed` est retentée à l'exécution suivante. |
| **Retry temporaire** | `loop.py` : `run_step` | Backoff exponentiel (2, 4, 8… s) par étape ; GitHub/réseau indisponible → réessai automatique. |
| **Journal complet** | `terrain/runs.jsonl` | Chaque étape et chaque résumé d'exécution écrits en append (rejouable, auditable). |
| **Alerte seulement si besoin humain** | `loop.py` : `classify_alert` | Silence par défaut. Drapeau uniquement pour : secret absent, réponse prospect à traiter, échec persistant (≥ 3×). |
| **KPIs de campagne** | `terrain/metrics.py` + `campaign.json` | Délivrance, réponse, RDV, signature, revenu — division par zéro → `n/a` (pas de faux 0 %). |

## Autonomie « sans session de chat »

`loop.py` est **auto-suffisant** : sur le chemin heureux, aucune décision LLM
n'est requise. La commande unique `bash terrain/run_daily.sh [--relance]` fait
tout et ne remonte quelque chose que si `needs_human` est vrai.

- **Scheduler** : les Routines Claude réveillent l'exécution (21/07, 22/07…).
  Elles lancent la commande et ne relaient que l'alerte.
- **Dépendance résiduelle honnête** : le *déclencheur* reste la Routine (ou un
  cron si disponible). Le *travail*, lui, ne dépend plus d'un connecteur MCP ni
  d'un raisonnement : scripts + secrets d'environnement (`SETUP-SECRETS.md`).
- Pour une autonomie multi-semaines totale : poser `STRIPE_API_KEY` +
  `RESEND_API_KEY` (une fois), et laisser les Routines réveiller `run_daily.sh`.

## Funnel courant

    python3 terrain/metrics.py    # KPIs live depuis campaign.json

Mettre à jour `campaign.json` quand un contact répond / prend RDV / signe :
les taux se recalculent seuls, et une réponse déclenche l'alerte humaine.
