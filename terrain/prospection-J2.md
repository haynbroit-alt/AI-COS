# Prospection ciblée — Jour 2 (2026-07-20)

Action V9 « prospection ciblée » exécutée. Outreach cold B2B envoyé via Resend
(domaine `velyx.org` vérifié). Registre pour déduplication (1 envoi unique par
cible — ne pas recontacter sans réponse).

## Cibles — 5 agences de prospection / génération de leads B2B (France)

ICP : structures dont le métier est l'outbound → besoin plausible pour Velyx.
Adresses **génériques professionnelles publiques** (liées à leur activité),
opt-out inclus → cold B2B défendable au sens CNIL.

| Société | Email | Statut envoi | ID Resend |
|---|---|---|---|
| Captain Prospect | hello@captainprospect.fr | delivered | 41808e0a-eedc-4e13-b9bf-6413e2c798e8 |
| Biz Agency | contact@biz-agency.fr | delivered | 09248ce1-cd9f-41bc-a732-7ad05dc57e0d |
| HelpIn Agency | contact@helpinagency.com | delivered | b626c29f-27af-41ab-8883-933e9fdcc09b |
| Agence de Prospection | contact@agence-de-prospection.fr | sent (en transit) | 4906c4a7-b1f0-4236-9f24-54ccdb56b44b |
| D2B Consulting | info@d2bconsulting.fr | delivered | 43ec95ef-1a42-4079-a3a9-8dd2e129aabb |

## Garde-fous appliqués

- **Quota** : 5 max (cap respecté).
- **Opt-out** : ligne « répondez stop » + header `List-Unsubscribe` (mailto).
- **Déduplication** : 1 email unique par cible, `idempotencyKey` par envoi.
- **Ciblage** : adresses génériques pro publiques, sujet lié à leur métier.

## Écarté

- `rgpd@leadactiv.fr` — adresse dédiée RGPD, hors périmètre outreach.

## Suivi des réponses

- Boîte relevée par l'utilisateur : **velyx.org@outlook.com**.
- Les 5 envois J2 partent de `hello@velyx.org` sans `replyTo` → réponses sur
  `hello@velyx.org`, relevables via Resend (`list-received-emails`, réception
  activée sur le domaine). À surveiller.
- **Envois suivants** : positionner `replyTo: velyx.org@outlook.com` pour que
  les réponses arrivent directement dans la boîte relevée.

## Mesure

Deltas réels au relevé Stripe de demain (J3, 2026-07-21). Toute réponse
« stop » → retirer définitivement du registre.
