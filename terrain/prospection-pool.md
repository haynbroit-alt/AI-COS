# Pool de prospection — extension 2026-07-21 (14 nouvelles cibles)

Même ICP que J2 : agences de prospection / génération de leads B2B (France) —
structures dont le métier est l'outbound → besoin plausible pour Velyx.

## Garde-fous (identiques à prospection-J2.md)

- **Adresses génériques professionnelles publiques uniquement** — chaque email
  vérifié à la source (page contact ou mentions légales du site), aucune
  adresse nominative, aucune adresse devinée, aucune adresse RGPD dédiée.
- **Cap global 5 envois/jour** (initiaux + relances confondus), appliqué par
  `relance_rules.DAILY_SEND_CAP` dans la boucle.
- **Opt-out** : ligne « répondez stop » + header `List-Unsubscribe` (mailto).
- **Déduplication** : registre unique `campaign.json`, `idempotencyKey` par envoi.
- **Relance unique à J+2** sans réponse ; bounce/réponse/« stop » → exclusion
  définitive (`relance_rules`).

## Cibles ajoutées (emails vérifiés le 2026-07-21)

| Société | Email | Source de vérification |
|---|---|---|
| Cognito | contact@hellocognito.fr | hellocognito.fr/contact |
| Oltega | contact@oltega.fr | oltega.fr/mentions-legales |
| ReCom | contact@re-com.fr | re-com.fr/mentions-legales |
| GoWithIA | agence@gowithia.fr | gowithia.fr/mentions-legales |
| Sodigix | contact@sodigix.com | sodigix.com/mentions-legales |
| WebConversion | contact@webconversion.fr | webconversion.fr/mentions-legales |
| Sales Odyssey | contact@salesodyssey.fr | salesodyssey.fr/mentions-legales |
| Citizen Call | contact@citizencall.fr | citizencall.fr/mentions-legales |
| Force Plus | forceplus@forceplus.com | forceplus.com/mentions-legales |
| Fox On Line | commercial@fox-online.fr | fox-online.fr/mentions-legales |
| Lalaleads | contact@lalaleads.io | lalaleads.io/mentions-legales |
| Rerow | contact@rerow.fr | rerow.fr/mentions-legales |
| BeYourSales | contact@beyoursales.com | beyoursales.com/mentions-legales |
| Messor | hello@messor.fr | messor.fr/mentions-legales |

## Écartés (garde-fou adresses génériques)

- Scal-IA (chloe@…), Monsieur Lead (fahimehassani@…), Junto (etienne@…),
  EraB2B (louis@…), Let's Growth (flavien@…), Europhone (mdesurmont@…),
  Hook Agency (adresses nominatives uniquement) — **nominatives**.
- Seventic, Magileads, LevelUp Sales — email obfusqué, non vérifiable.
- Acceor, Growth Room, Deux.io, Oliverlist, Dolead, Hacquisition, Agence
  Nova — formulaire uniquement, aucun email public.
- LeadActiv — adresse RGPD dédiée uniquement (décision J2 maintenue).

## Déroulé prévisionnel (cap 5/jour, automatique via terrain-daily)

- **2026-07-22** : 4 relances J+2 (lot J2) + 1 envoi initial.
- **2026-07-23 → 25** : 5, 5, 3 envois initiaux.
- **2026-07-24+** : relances J+2 des nouveaux envois, au fil de l'eau.
