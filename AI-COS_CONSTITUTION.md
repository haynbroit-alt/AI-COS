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

Ces règles gouvernent la **construction d'AI-COS** (pipeline en mode
« complet »). Pour l'usage quotidien, le mode « leger » rend plan, revue
humaine et simulation optionnels — mais les invariants ne se désactivent
jamais : une mission à la fois, un objectif, tests verts, mesure réelle.

## Interdits

- Modifier la boucle V9 (refus automatique — exception : échec mesuré ≥ 30 jours).
- Bascule forcée : le moteur suggère, l'utilisateur choisit.
- Mission multi-objectifs ou « construis tout ».
- Déploiement en production sans simulation ni revue humaine.
- Déclarer une mission réussie sans mesure réelle de l'écart.

## Mandat permanent (2026-07-19, décision utilisateur)

L'utilisateur a accordé une **autorisation permanente d'agir** : plus de
demandes de validation avant d'exécuter. Conséquences opérationnelles :

- Agir d'abord, rendre compte après — sur tout ce qui est accessible
  (code, PR, merges, configs, déploiements, relevés, corrections).
- Les PR de l'assistant sont mergées par l'assistant dès que les tests
  sont verts.
- Les seuls messages restants en forme de demande sont des **passages de
  main** : un secret, un clic ou un accès qui n'existe que côté
  utilisateur (registrar, dashboards tiers, secrets CI). Ce ne sont pas
  des demandes d'autorisation.
- Les actions à exposition juridique ou irréversibles vers des tiers
  (envois externes en masse, dépenses) sont **signalées au moment où
  elles partent**, pas soumises à validation préalable — les garde-fous
  techniques restent en place (quotas, opt-out, déduplication).

## Objectifs

- Prototype : 10 cycles complets en 30 jours, 0 modification de boucle.
- Chaque cycle produit un skill réutilisable dans le Memory Engine.
- L'écart global E converge ; aucune dimension n'est sacrifiée ; énergie > 0.

---

*Claude Code doit être un excellent constructeur, mais AI-COS reste le chef
d'orchestre qui contrôle la direction.*
