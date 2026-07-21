# Campagne Montpellier — Cabinets Recrutement Tech

## Vue d'ensemble

Campagne autonome ciblant 21 cabinets de recrutement IT en Montpellier/Occitanie.

**Fichier campagne** : `campaign-montpellier-cabinet.json`  
**Démarrage** : 2026-07-21  
**Cibles** : 5 HOT + 11 WARM + 5 ESN (total 21)  
**Modèle** : `cabinet` (positioning "radar commercial, pas IA de prospection")  
**Livrable** : `velyx-rapport-montpellier.md` (6 opportunités, gratuit au 1er oui)  
**Engagement** : Au résultat si opportunité génère RDV; sinon 0 engagement; Radar 199€/mois après validation

---

## Architecture

### Priorités de file

1. **HOT (5 cibles)** — semaine 1, envoi immédiat
   - Externatic (contact@externatic.fr) — 300+ recrutements/an IT
   - Seyos (contact@seyos.fr) — 900 clients, 2700 recrutements
   - Bureau des Talents (contact@bureaudestalents.com) — tech/startups + profils rares
   - LEA Recrutement (contact@le-a.fr) — cabinet local Montpellier
   - Factoriel (contact@factoriel.fr) — consultants SI/IA

2. **WARM (11 cibles)** — après traction sur HOT
   - Silkhom, Winsearch Montpellier, Work'in, Talent:Program, Florian Mantione
   - CA RH, Le Carré RH, Opt'in, Potentiel Humain, Strattitude, TAC

3. **ESN (5 cibles)** — cycle plus long, dernier
   - FASEYA, Meritis, Alteca, Scalian, Viveris
   - Angle adapté : « anticiper les besoins tech de vos futurs clients »

### Règles d'engagement

- **Cap quotidien** : 5 emails/jour (initiaux + relances combinées)
- **Envoi initial** : mail un seul avec subject + hook personnalisés, template « cabinet »
- **Relance unique J+2** : si silence, un seul relance 2 jours après
- **Opt-out** : « stop » → exclusion définitive
- **Bounce** : exclusion automatique après détection Resend
- **Pas de double** : chaque contact sera contacté au maximum 2x (initial + relance J+2)

### Signaux détectés

Depuis `velyx-rapport-montpellier.md` (6 opportunités échantillon générées le 2026-07-21) :

1. **Synanto** — recrutements mobiles multiples (iOS, Android) → urgence produit
2. **Team.is** — 5 familles de postes ouvertes → croissance structurelle
3. **Startup DeepTech Santé** — IA spécialisée rare → timing critique
4. **TSS** — postes dirigeants IA → anticipation avant annonce
5. **Startup TravelTech** — fullstack FastAPI/React → fenêtre courte
6. **Quantum Surgical** — expansion IA médicale → besoins invisibles

---

## Lancement

### Option 1 : Script bash (recommandé)

```bash
cd terrain
./run-montpellier.sh
```

Cela :
- définit `CAMPAIGN_FILE=campaign-montpellier-cabinet.json`
- exécute la boucle complète
- envoie jusqu'à 5 emails (HOT prioritaires)
- met à jour le statut livré/bounce/réponse en temps réel

### Option 2 : Direct Python

```bash
cd terrain
export CAMPAIGN_FILE="campaign-montpellier-cabinet.json"
python3 loop.py
```

### Option 3 : Boucle autonome (GitHub Actions)

Dans `.github/workflows/terrain-loop.yml`, remplacer :
```yaml
- name: run loop
  env:
    CAMPAIGN_FILE: campaign-montpellier-cabinet.json
  run: cd terrain && python3 loop.py
```

Cron : tous les jours à 08:37 UTC (13:37 Paris l'été, 14:37 en hiver)

---

## Suivi

### État du jour

Consulter `terrain/loop_state.json` :
```json
{
  "date": "2026-07-22",
  "steps": {
    "read_cycle": "done",
    "check_status": "done", 
    "relance": "done",
    "outreach_initial": "done"
  }
}
```

### Logs de la boucle

Consulter `terrain/runs.jsonl` (append-only) — dernier run = 5 dernières lignes :
```bash
tail -20 terrain/runs.jsonl | jq .
```

Événements clés :
- `"step": "outreach_initial"` + `"ok": true` → emails partis
- `"step": "check_status"` + changement → bounce/reply/delivered détecté
- `"needs_human": true` → intervention requise (secret absent, réponse à traiter, échec persistant)

### Métriques funnel

Consulter `terrain/metrics.py` :
```bash
python3 -c "from metrics import report; import json; print(json.dumps(report()['funnel'], indent=2))"
```

Taux observés :
- `delivery_rate` : % des emails livrés (vs bounces)
- `reply_rate` : % des livrés qui ont répondu
- `positive_rate` : % des réponses positives (« oui », pas « non »)
- `report_request_rate` : % des positives qui demandent le rapport
- `meeting_rate` : % des reports qui convertissent en RDV
- `sign_rate` : % des RDV qui signent (Radar 199€/mois ou Pack Découverte)

Objectif : atteindre le premier paiement Velyx = une seule opportunité génère RDV → signature

---

## Prochaines actions

### J+1 (2026-07-22)

- Boucle auto lance vers 08:37 UTC
- Envoie 1-5 HOT + 0-4 relances J+2 (cap quotidien)
- Délivre `velyx-rapport-montpellier.md` aux premiers « oui »

### J+2 (2026-07-23)

- Relance unique des HOT silencieux → envoi max 5

### Semaine 1 (J+0 à J+7)

- HOT : envoi initial + relance J+2
- WARM : en attente (relâche si traction HOT, engagement si urgence)
- ESN : silencieuse jusqu'au signal

### Pivot décisionnel

- **Si 1+ RDV généré par une opportunité** → « pour vous le prouver » fonctionne → Radar 199€/mois valide
- **Si 0 RDV / 3+ rejets** → signal de marché : repositionner ou pivoter cible

---

## Contrôle qualité

### Pre-launch

- [x] 21 cibles sourced (emails vérifiés sur sources publiques)
- [x] 5 HOT avec phone contact confirmé (relance téléphonique réservée J+3 si silence)
- [x] Rapport échantillon généré (`velyx-rapport-montpellier.md`)
- [x] Template « cabinet » adapté à chaque segment (HOT/WARM/ESN)
- [x] Campaign JSON valide (21 contacts, priorities OK)
- [x] Loop.py accepte CAMPAIGN_FILE
- [x] Relance rules : MAX_RELANCES=1, DAILY_SEND_CAP=5

### Post-launch monitoring

- Jour 1 : 0-5 initiaux envoyés, statut Resend confirmé
- Jour 3 : relances J+2 parties, premiers rejets/silences enregistrés
- Jour 7 : 1ère réponse positive attendue (probabilité HOT ≈ 40-60%)
- Jour 10 : 1er RDV généré ou pivotage décisionnel

---

## Contact & escalade

- **Responsable campagne** : Charfa / Velyx
- **Réponses prospects** : hello@velyx.org (réponses taguées auto → replied flag)
- **Escalade RDV** : appel direct cabinets HOT (phone dans notes du campaign.json) si silence J+3
- **Analyse taux de réponse** : metrics.py, funnel par segment (HOT/WARM/ESN)
