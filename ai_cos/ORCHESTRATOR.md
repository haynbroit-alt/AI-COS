# Cœur d'orchestration multi-IA — le sang d'AI-COS

Un seul point d'entrée. Chaque module demande **un rôle**, jamais un fournisseur.
Le hub porte l'appel au bon modèle, bascule si l'organe est absent, journalise.

```python
from ai_cos import orchestrator as brain

res = brain.route("stratege", "Plan pour X en 3 étapes.", system="Tu es concis.")
print(res.text, "via", res.model, f"({res.provider}) — {res.cost_usd}$")

# Rôles à enjeu : pluralité plutôt qu'un point de défaillance unique.
avis = brain.deliberate("gardien", "Cette action est-elle réversible ?", k=3)
```

## Les 8 rôles (organes)

| Rôle | Force recherchée | Défaut primary → fallbacks |
|---|---|---|
| observateur | veille / web / signaux | gpt-5 → gemini, sonnet-5 |
| stratège | raisonnement long, plans | opus-5 → deepseek-reasoner, sonnet-5 |
| décideur* | décision + éthique | opus-5 → gpt-5, deepseek |
| architecte | archi & code complexe | gpt-5 → opus-5, gemini |
| exécuteur | code + rédaction | sonnet-5 → gpt-5, mistral |
| contrôleur | données, stats, chiffres | deepseek-reasoner → gpt-5, sonnet-5 |
| conservateur | mémoire / très long contexte | gemini → sonnet-5 |
| gardien* | sécurité, éthique, veto | opus-5 → gpt-5, deepseek |

\* rôles « conseil » (`council`) : on interroge plusieurs modèles (`deliberate`).

## Principes (non négociables)

1. **Provider-agnostique.** Les IDs de modèles vivent dans `orchestrator_config.json`,
   jamais dans le code. Nouvelle génération de modèles = on édite la config.
   Le fournisseur est déduit du préfixe (`claude*`→anthropic, `gpt*`/`o*`→openai,
   `gemini*`→google, `deepseek*`→deepseek, `mistral*`→mistral).
2. **Zéro secret en dur.** Chaque clé vient de l'environnement
   (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `DEEPSEEK_API_KEY`,
   `MISTRAL_API_KEY`). **Sans clé, le fournisseur est sauté** — dégradation
   propre, jamais de plantage. `brain.health()` montre l'état du sang.
3. **Réalité > Hypothèse.** Un modèle qui échoue est écarté au profit du suivant ;
   coût et latence réels sont journalisés dans `orchestrator_ledger.jsonl`.
4. **Testable sans réseau.** Toute la logique de routage est pure ; le HTTP réel
   est injectable (`transport=`). 13 tests couvrent bascule, dégradation, coût.

## Honnêteté sur les modèles

Les IDs de la config sont des **défauts à vérifier/éditer**. Les noms et
benchmarks qui circulent (« GPT-5.6 », « Fable 5 80.3 % », « Gemini 3.1 »…)
n'ont **pas** été validés ici et changent vite : ne les traitez pas comme
gravés. Le cœur est conçu exactement pour ça — mettez l'ID auquel vous avez
réellement accès, un ID invalide bascule simplement au fallback.

## Où ça branche (quand il y aura de l'usage réel)

Ce module est **inerte tant qu'aucun module ne l'appelle** (aucune clé → aucun
coût). Le bon premier branchement n'est pas « tous les modules », c'est **un
workflow réel** :
- l'**auto-répondeur** Velyx : `route("executeur", …)` pour personnaliser le
  rapport par ICP au lieu du template figé ;
- **SENTINEL** (si construit) : `route("observateur", …)` pour la veille.

Recommandation : ne câble pas les 8 rôles d'un coup. Branche-en **un**, mesure
le coût réel dans le ledger, puis étends. C'est la Loi du système : une
évolution à la fois, prouvée.
