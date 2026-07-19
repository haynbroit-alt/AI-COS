# Modèle mathématique V9 Dual (référence)

Ce document est la référence formelle du moteur. L'utilisateur n'a jamais
besoin de le lire : l'interface répond à « quel est le problème, que faire,
pourquoi, avec quelle confiance ».

## Écart pondéré

`E_t = √(Σ wᵢ·(sᵢ − oᵢ)²)`

État `S_t = (s₁, …, s_n)`, objectif `O`, poids dynamiques `wᵢ(t)`.

## Poids dynamiques

`wᵢ(t+1) = wᵢ + η·(|sᵢ−oᵢ|/oᵢ)·𝟙{sᵢ<oᵢ} − β·wᵢ`

Une dimension en retard reçoit plus de poids (renforcement proportionnel à
l'écart relatif, seulement sous-objectif) ; l'oubli β empêche la saturation.
Plancher à 0,1.

## Énergie

`R(t+1) = min(cap, R − γ·c(a) + δ·max(0, E_t − E_{t+1}))`

Dépense obligatoire même au repos (`c(a) ≥ 1`), récupération seulement si
l'écart baisse réellement, plafonnée (`cap`, défaut 100) — pas d'énergie
fantôme dans aucun sens.

## Levier

`L_t = 1 + (μ−1)·𝟙{Var(E_{t−2:t}) < ε ∧ R_t > R_seuil ∧ ∀i, |sᵢ−oᵢ|/oᵢ < δ_max}`

Amplification (μ, défaut 2) seulement si trois cycles stables, énergie
au-dessus du seuil, et aucune dimension catastrophiquement en retard.

## Anti-stagnation

Si `∃i : |sᵢ(t) − sᵢ(t−3)| < τ·oᵢ` et `sᵢ < oᵢ`, alors
`a_t = argmax_a (∂sᵢ/∂a)` — l'action au plus fort gradient pour la
dimension figée, indépendamment du score global.

## Confiance (base de connaissances)

`confiance(a) = (réussites + 1) / (essais + 2)` (lissage de Laplace)

Une action jamais testée vaut 50 % ; seuls des essais réels répétés
l'en éloignent. Le world model observé (moyenne mobile des deltas mesurés,
lissage 0,5) remplace les gradients déclarés dès la première observation.

## Priorité

`score(a) = impact_projeté(a, L) / (coût + risque)` — l'impact projeté est
calculé avec les effets prédits par le world model (observé d'abord,
déclaré sinon).
