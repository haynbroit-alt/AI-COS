# Secrets d'environnement — robustesse des Routines (passage de main)

Les Routines programmées (relevé quotidien, relance J+2) ne dépendent **plus**
de la reconnexion des connecteurs MCP. Elles passent par les **API directes**
(`curl`/stdlib) avec des clés lues dans l'environnement — jamais committées.

## À faire une seule fois : ajouter 2 secrets à l'environnement

Dans les réglages de l'environnement Claude Code (mêmes réglages où vit déjà
`GITHUB_TOKEN`), ajouter :

| Variable | Rôle | Où l'obtenir |
|---|---|---|
| `STRIPE_API_KEY` | Relevé quotidien (customers + charges) | Dashboard Stripe → Développeurs → Clés API. **Clé restreinte lecture** (customers:read, charges:read) suffit pour le relevé. |
| `RESEND_API_KEY` | Envoi de la relance | Dashboard Resend → API Keys → clé avec permission d'envoi. |

`GITHUB_TOKEN` est **déjà** présent → le push git fonctionne sans MCP.

## Pourquoi c'est plus robuste que les connecteurs MCP

- Les secrets d'environnement sont injectés dans **chaque** session de
  l'environnement, dès le réveil — pas de handshake MCP à réussir.
- Les clés ne sont **pas** committées (lues via `os.environ` / `$VAR`),
  exactement comme `StripeSource` l'a toujours fait.

## Vérifier

    bash terrain/run_daily.sh            # relevé + cycle + push
    bash terrain/run_daily.sh --relance  # idem + relance Resend

Sans les clés, chaque étape concernée affiche `FILET : … absent → sauté` et le
script continue — aucune action à l'aveugle.

## Tant que les clés ne sont pas posées

Les Routines se réveillent quand même mais **sautent** les étapes Stripe/Resend
en le signalant. Le relevé et la relance devront alors se faire à la main (via
les connecteurs MCP de la session interactive) — c'est le mode dégradé, pas le
mode cible.
