# Automatisation Koralya Studio

## Ce que cette première installation apporte

- Un contrôleur sans dépendance externe pour les pages publiques, les liens internes, les en-têtes de protection, robots.txt et le sitemap.
- Un workflow GitHub Actions programmé le lundi à 08 h en Martinique. Il conserve un rapport lisible et un fichier JSON pendant 30 jours.
- Un workflow n8n importable pour contrôler l’accueil, les offres et le contact toutes les cinq minutes, avec une seconde tentative en cas d’erreur HTTP ou réseau.
- Une veille quotidienne des flux officiels Cloudflare, web.dev et CERT-FR, avec un rapport GitHub à 08 h 15 en Martinique.

Aucun fichier du site public n’est modifié. Ces contrôles ne couvrent pas les secrets, les droits du compte Cloudflare, les dépendances du serveur, les sauvegardes ou le fonctionnement interactif du navigateur. Une réponse HTTP 200 seule ne garantit pas le fonctionnement de toutes les fonctions.

## Contrôle hebdomadaire GitHub

Le calendrier est actif une fois `.github/workflows/site-monitor.yml` présent sur la branche par défaut et GitHub Actions autorisé pour le dépôt. Les horaires GitHub sont indicatifs et les exécutions peuvent être retardées. Sur un dépôt public, GitHub peut suspendre les workflows planifiés après 60 jours d’inactivité.

Pour un contrôle immédiat : ouvrir l’onglet **Actions**, sélectionner **Contrôle hebdomadaire Koralya**, puis **Run workflow**. Consulter le résumé de l’exécution ou télécharger son rapport.

Les erreurs de disponibilité, de structure des pages, de liens ou de sitemap font échouer le contrôle. Les en-têtes manquants génèrent des avertissements ; ils ne prouvent pas une intrusion. Le formulaire actuel WhatsApp/e-mail est pris en compte : l’absence d’envoi direct reste informative. Lorsque l’envoi direct sera réellement installé, passer `contact_direct_required` à `true` dans `automation/monitor.json`.

Les notifications d’échec dépendent des préférences de notification GitHub du compte qui exécute ou possède le workflow. Aucun e-mail, SMS ou message WhatsApp n’est envoyé par ce code.

## Veille quotidienne des sources

Le workflow **Veille quotidienne Koralya** collecte les flux définis dans `automation/sources.json`. Il conserve jusqu’à cinq articles par source, publiés dans les quatorze derniers jours, avec titre, lien, date et extrait de 500 caractères au maximum. Les articles complets ne sont pas téléchargés. Ce sont des sources de départ pour la veille technique de Koralya, pas une étude des concurrents ni une liste de données commerciales à importer.

La collecte démarre après intégration du workflow sur la branche par défaut, puis chaque jour à 08 h 15 en Martinique. Elle est aussi exécutable depuis **Actions → Veille quotidienne Koralya → Run workflow**. Le résumé contient les articles ; les fichiers `veille.json` et `veille.md` sont conservés trente jours. GitHub peut retarder ou suspendre les calendriers dans les mêmes conditions que pour le contrôle hebdomadaire.

Une source inaccessible est signalée clairement, même si les autres fonctionnent. Si toutes les sources échouent, le workflow échoue. Une source valide sans article récent n’est pas une erreur. Les dates sont celles des flux ; une modification récente d’un ancien article peut ne pas être détectée. Les alertes CERT-FR doivent être rapprochées des technologies réellement utilisées avant toute action.

Le rapport est un instantané de veille : un article peut apparaître plusieurs jours de suite tant qu’il reste dans la fenêtre. Les doublons de liens sont supprimés au sein d’un rapport. Aucune publication sur le site, modification de prix, inscription à un service ou requête IA payante n’est déclenchée.

Pour exécuter la collecte localement :

```sh
python3 -m scripts.source_watch
```

## Disponibilité dans n8n

1. Importer `automation/n8n/disponibilite.json` dans un espace n8n actuel.
2. Exécuter **Tester manuellement** et vérifier les trois résultats.
3. Choisir un **Error Workflow** dans les paramètres n8n pour envoyer les alertes au canal souhaité ; connecter ses identifiants directement dans n8n.
4. Publier/activer le workflow dans n8n. Le fichier importé est volontairement inactif et ne contient aucun identifiant.

Une indisponibilité marque l’exécution en échec, mais aucun canal d’alerte n’est connecté dans le fichier fourni. L’historique n8n permet de consulter les échecs ; configurer sa rétention selon le forfait. Le contrôle est strict : une redirection des trois adresses contrôlées doit être examinée et les adresses mises à jour si nécessaire.

Ce workflow nécessite un service n8n disponible en permanence. Le contrôle hebdomadaire GitHub fonctionne indépendamment de n8n.

## Exécution locale

Python 3.10 ou plus récent suffit :

```sh
python3 -m unittest discover -s tests -v
python3 scripts/site_monitor.py
```

Les rapports sont écrits dans `reports/`, ignoré par Git. Les requêtes sont des lectures HTTPS sur le même site ; le contrôleur Python refuse les redirections vers d’autres domaines.

## Suite : veille et mises à jour par IA

La rédaction IA et la publication attendent le choix du compte IA et la connexion à un espace n8n. La collecte des sources fonctionne déjà indépendamment sur GitHub ; aucun appel IA payant n’est effectué.

Le circuit prévu est : sources autorisées sélectionnées → collecte → propositions sourcées → branche GitHub → prévisualisation Cloudflare → vérifications → publication. Les tarifs, paiements, coordonnées et mentions légales demandent une validation explicite. Les instructions présentes dans les sources de veille doivent être traitées comme du contenu et ne doivent pas piloter la publication.

Avant de configurer un déploiement automatique, vérifier la connexion actuelle du dépôt à Cloudflare et les règles de branches/prévisualisation. Le dépôt ne contient actuellement que des fichiers publics et une configuration d’assets Cloudflare ; aucun générateur de contenu ou serveur de formulaire n’est fourni.

Ne jamais transmettre de clé ou de mot de passe dans une conversation ou un fichier Git. Les futurs identifiants seront configurés dans les coffres de n8n et les secrets des services concernés.
