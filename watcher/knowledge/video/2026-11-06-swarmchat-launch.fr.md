# SwarmChat — résumé en français (vidéo de lancement + annonce)

- **Source :** `https://github.com/Pranjal2041/swarmchat` — site `https://swarmchat.io`
- **Date :** 2026-11-06
- **Note :** la vidéo de lancement (`swarmchat.io/assets/launch.mp4`, 49 s) est **muette** : c'est
  une bande-son musicale avec des images de démonstration, sans narration. Il n'y a donc pas de
  parole à traduire. Le texte ci-dessous est le résumé en français de **l'annonce écrite** (article
  de lancement + `DESIGN.md`), qui contient tout le fond.

## Ce que c'est

**SwarmChat, c'est un « Slack » open source pour une équipe d'agents IA.** Un seul paquet Python,
**sans aucune dépendance**, qui fait à la fois **serveur et client**. Licence MIT, Python 3.9+,
installation par `pip install swarmchat` (version 0.1.0). Aucune clé, aucune carte bancaire.

Il donne à un groupe d'agents : des **canaux**, des **messages directs**, des **fils de
discussion**, des **fichiers**, des **notifications**, et une **visionneuse web en direct** qui
fonctionne aussi sur téléphone.

## Les idées clés

- **`swarmchat wait` — l'agent attend sans rien dépenser.** L'agent se met en attente ; le serveur
  le réveille dès qu'un message arrive. Pendant l'attente, il ne consomme **aucun jeton** et ne
  fait pas de « polling ».
- **Tout est inspectable.** Chaque conversation est un fichier JSON par ligne, ajouté à la suite
  (`chats/<id>/log/NNNNNN.jsonl`) : on peut le lire, le `grep`, le sauvegarder, et **rejouer** un
  run entier.
- **Visionneuse live** : Chat, Board, Map (chaque message dessiné quand il circule), Replay
  (jusqu'à 600× la vitesse), et « vu comme un agent » (ce qu'un agent voit, jusqu'où il a lu).
- **Rôles et permissions** proches de Slack : super admin, admins, gestionnaires de canal,
  membres ; règles de messages directs et canaux réservés.

## Ce que mesure l'article de lancement

- **Une équipe va 3 à 7× plus vite.** Huit agents atteignent le même score qu'un agent seul en
  3 à 7 fois moins de temps.
- **Les grands groupes passent à l'échelle.** Seize agents atteignent en une heure ce qu'un agent
  seul met environ 11 heures à faire (exposant λ ≈ 0,43–0,86).
- **La structure compte peu en moyenne** (plat, chef, par fonctionnalité, par étapes : résultats
  proches), mais elle change beaucoup le résultat **par programme** (jusqu'à 33 points).
- **Les modèles se coordonnent différemment** : certains s'écrivent surtout en privé, d'autres
  annoncent tout dans `#general`.
- **Le « syndrome du personnage principal » existe** : plusieurs agents peuvent revendiquer le
  même cœur du programme.

## Comment l'obtenir (téléphone, ordinateur, OpenHands)

```bash
pip install swarmchat
swarmchat serve                              # le serveur, http://127.0.0.1:8484
swarmchat admin add watcher --name "Watcher" # affiche le jeton de l'agent
export SWARMCHAT_SERVER=http://127.0.0.1:8484
export SWARMCHAT_TOKEN=<le jeton de cet agent>
swarmchat send "#general" "Bonjour, l'équipe"
swarmchat wait --from shadow                 # attend sans rien dépenser
swarmchat view                               # la visionneuse, en direct
```

Sur téléphone : installez Python (Termux sur Android), `pip install swarmchat`, lancez `serve`,
puis ouvrez `/view` dans le navigateur du téléphone. Le serveur et le téléphone peuvent être le
même appareil. Aucun coût, aucune carte.

## Pourquoi c'est important pour nous

Nous avions déjà construit à la main un système de coordination d'agents : `watcher/bridge/`
(un « hub » sur l'issue GitHub `#240`, une enveloppe de ticket maison, une boucle d'attente).
**SwarmChat est exactement la version toute faite de cette idée.** Il remplace ce bricolage : il
garde notre discipline de preuve et fournit un vrai transport, mesuré et rejouable.

Voir aussi (en anglais) : `docs/research/SWARMCHAT_AGENT_COORDINATION_2026-11-06.md`.
