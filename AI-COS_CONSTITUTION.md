# AI-COS — CONSTITUTION

Source de vérité. Tout constructeur (Claude Code inclus) doit s'y référer
avant chaque mission. Le pipeline de contrôle refuse de fonctionner sans elle.

## Architecture

```
AI-COS (Architecte)
        ↓
Mission claire            (1 mission = 1 objectif)
        ↓
Plan avant le code        (fichiers, risques, stratégie, tests prévus)
        ↓
Claude Code (Constructeur)
        ↓
Tests automatiques        (cas normal + cas erreur + cas limite)
        ↓
Revue humaine
        ↓
Déploiement progressif    (simulation → validation → production)
        ↓
Mesure réelle             (l'écart a-t-il baissé ?)
```

Couches produit : AI-COS Engine, Memory Engine, Claude Code Connector,
Automation Engine, Cosmic View, Operations View.

Boucle V9 : ÉCART → CAUSE → PRIORITÉ → PREMIER PAS → ACTION → MESURE → APPRENTISSAGE.

## Règles

1. **Une mission = un objectif.** Pas de « construis tout ». Un objectif,
   un critère de réussite mesurable.
2. **Plan avant le code.** Fichiers concernés, risques, stratégie, tests
   prévus — approuvé avant la première ligne.
3. **Tests obligatoires.** Chaque fonction importante couvre le cas normal,
   le cas erreur et le cas limite.
4. **Petites modifications.** Une modification → test → validation → suivante.
   Jamais deux missions en vol.
5. **Source de vérité.** Ce fichier. Architecture, règles, interdits, objectifs.
6. **Simulation avant réel.** Aucune action importante ne va en production
   sans passer par la simulation puis la validation.
7. **Mesurer le résultat.** Du code propre mais inutile est un échec.
   La seule question : est-ce que cette modification réduit l'écart ?

## Interdits

- Modifier la boucle V9 (refus automatique — exception : échec mesuré ≥ 30 jours).
- Bascule forcée : le moteur suggère, l'utilisateur choisit.
- Mission multi-objectifs ou « construis tout ».
- Déploiement en production sans simulation ni revue humaine.
- Déclarer une mission réussie sans mesure réelle de l'écart.

## Objectifs

- Prototype : 10 cycles complets en 30 jours, 0 modification de boucle.
- Chaque cycle produit un skill réutilisable dans le Memory Engine.
- L'écart global E converge ; aucune dimension n'est sacrifiée ; énergie > 0.

---

*Claude Code doit être un excellent constructeur, mais AI-COS reste le chef
d'orchestre qui contrôle la direction.*
