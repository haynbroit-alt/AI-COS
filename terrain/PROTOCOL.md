# Campagne terrain — 30 jours sur données Stripe réelles

**Début : 2026-07-19. Fin : 2026-08-18.**
**Objectif : 10 clients payants, 5000 de revenus, qualité 8/10.**
**Critère de bilan : l'écart a-t-il baissé significativement sur au moins une
dimension clé ? (spec V9, jours 22-30)**

## Source de données

Compte Stripe réel « Charfa » (`acct_1TSWyvFx9dRNalKW`), relevé via le
connecteur Stripe de la session Claude (pont MCP — aucune clé API stockée) :

- `clients` = nombre de customers Stripe
- `revenus` = somme des charges réussies non remboursées (en unités monétaires)
- `qualite` = auto-déclarée par l'utilisateur (mettre à jour dans le journal)

## Rituel quotidien (automatisé par une Routine, ~08:00 Paris)

1. **Relever** Stripe via MCP → écrire `terrain/journal.json`.
2. **Mesurer** : `echo "a" | python3 -m ai_cos.cli --source terrain/journal.json --data-dir terrain`
   — le relevé solde l'action décidée la veille (deltas réels → Memory Engine),
   puis la suggestion du jour est enregistrée comme action en attente.
3. **Journaliser** : ajouter la ligne du jour à `terrain/log.md`.
4. **Committer et pousser** `terrain/` — l'état doit survivre aux
   environnements éphémères.
5. **Présenter** la suggestion du jour à l'utilisateur dans la session.

## Contrôle utilisateur (suggestion, pas imposition)

La suggestion du moteur est enregistrée par défaut pour que la boucle ne
s'arrête jamais, mais l'utilisateur peut **la remplacer à tout moment avant le
relevé du lendemain** en le disant dans la session : l'action en attente
(`pending_action` dans `terrain/state.json`) est alors remplacée par son choix
— sans exécuter de cycle. Ne rien faire vaut acceptation ; demander « repos »
est toujours possible.

## Fin de campagne

Au 30ᵉ relevé (ou le 2026-08-18), produire le bilan dans `terrain/BILAN.md` :
trajectoire de l'écart par dimension, actions les plus efficaces selon le
world model, skills appris, verdict (règle 7 : l'écart a-t-il baissé ?).
Puis supprimer la Routine quotidienne. Le bilan — et lui seul — peut
débloquer une discussion V10 (échec mesuré sur 30 jours) ou valider la boucle.
