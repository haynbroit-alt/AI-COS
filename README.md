# AI-COS V9 — Prototype

Système d'exploitation décisionnel personnel. Un cofondateur IA qui observe,
analyse, **propose**, exécute selon ses permissions, mesure et apprend.

> Suggestion, pas imposition. Prototype, pas perfection. Preuve, pas version.

## Boucle V9 (verrouillée)

```
ÉCART → CAUSE → PRIORITÉ → PREMIER PAS → ACTION → MESURE
  ↑                                                  ↓
  └────────── APPRENTISSAGE (Mémoire #2) ←──────────┘
```

**Règle bloquante** : pas de V10/V11. Toute modification de la boucle est
refusée automatiquement (`LoopLockedError`), sauf échec mesuré sur ≥ 30 jours
de prototype. Le verrou est dans le code (`LoopLock`), pas seulement dans la doc.

## Architecture — 6 couches

| Couche | Module | Rôle |
|---|---|---|
| 1. AI-COS Engine | `ai_cos/engine.py` | Boucle 7 phases, écart pondéré, levier, anti-stagnation, mode suggestion |
| 2. Memory Engine | `ai_cos/memory.py` | Poids dynamiques, world model discret, skills réutilisables, persistance |
| 3. Claude Code Connector | `ai_cos/connectors/claude_code.py` | Missions de développement (format OBJECTIF/PROBLÈME/…) |
| 4. Automation Engine | `ai_cos/connectors/automation.py` | Exécution + mesure post-action (connecteurs enfichables) |
| 5. Cosmic View | `ai_cos/views.py` | Cap : écart global, tendance, énergie, levier |
| 6. Operations View | `ai_cos/views.py` | Détail : dimensions, poids, dernier cycle, skills |

## Modèle mathématique (V9 Dual corrigé)

- **Écart pondéré** : `E_t = √(Σ wᵢ·(sᵢ − oᵢ)²)`
- **Poids dynamiques** : `wᵢ(t+1) = wᵢ + η·(|sᵢ−oᵢ|/oᵢ)·𝟙{sᵢ<oᵢ} − β·wᵢ`
  — une dimension en retard reçoit plus de poids ; l'oubli β empêche la saturation.
- **Énergie** : `R(t+1) = min(cap, R − γ·c(a) + δ·max(0, E_t − E_{t+1}))`
  — dépense obligatoire même au repos, récupération seulement si l'écart baisse, plafonnée.
- **Levier** : `L = μ` seulement si variance de E stable sur 3 cycles ∧ énergie > seuil
  ∧ aucune dimension catastrophiquement en retard. Sinon `L = 1`.
- **Anti-stagnation** : dimension figée (< 1 % de variation sur 3 cycles) et
  sous-objectif → l'action suivante est celle au plus fort gradient pour elle.

## Mode suggestion — contrôle utilisateur

Le moteur ne bascule jamais tout seul : `engine.suggest()` retourne UNE action
recommandée + rationale + alternatives. C'est l'utilisateur (ou le CLI) qui
choisit ; chaque `CycleReport` trace `chosen_by_user`.

## Utilisation

```bash
# Démo prototype : 10 cycles complets, bilan final
python -m ai_cos.demo

# Boucle quotidienne interactive (60 secondes/jour, état persisté dans .ai_cos/)
python -m ai_cos.cli

# Preuve : 24 tests (convergence, équilibre, énergie, verrou V9…)
python -m pytest
```

## Critère de succès du prototype

10 cycles complets, 0 modification de boucle — vérifié par
`tests/test_prototype.py` : l'écart global converge (4200 → 47 sur le scénario
de démo), aucune dimension n'est sacrifiée, l'énergie reste positive, un skill
est stocké à chaque cycle.

## Lois système

1. Réalité > Hypothèse — le world model observé remplace les gradients déclarés
2. Mesure > Intuition — l'Automation Engine mesure les deltas réels post-action
3. Priorité > Dispersion — une seule action par cycle
4. Action > Réflexion infinie — 60 secondes de décision
5. Résultat > Intention — l'énergie ne remonte que si l'écart baisse
6. Apprentissage > Répétition d'erreur — chaque cycle devient un skill
7. Simplicité > Complexité — stdlib uniquement, zéro dépendance
8. Énergie durable > Effort temporaire — coût obligatoire, plafond, seuil de levier
9. Marché > Perfection interne — prototype d'abord, V10 jamais (sans preuve)
10. Puissance contrôlée > Puissance brute — suggestion, verrou, permissions

---

*« AI-COS travaille en silence. Il détecte, prépare, propose, construit avec
Claude Code et apprend des résultats. La puissance vient du contrôle. »*
