# Freebox Profiles pour Home Assistant

*[English version](README.en.md)*

Intégration Home Assistant pour les **profils (contrôle parental) de Freebox OS** : voir si Internet est autorisé ou bloqué pour chaque profil, mettre un profil en pause (avec ou sans durée), le remettre sur son planning, et automatiser tout cela.

> Projet communautaire, **non affilié à Free / Iliad**.

## Fonctionnalités

Chaque profil de Freebox OS devient un appareil dans Home Assistant, avec :

| Entité | Type | Rôle |
|---|---|---|
| Mode | Sélecteur | *Planning*, *Autorisé* ou *Bloqué* (sans limite de durée) |
| Pause | Interrupteur | Comme le bouton « Pause » de l'app Freebox : allumé, Internet est coupé pour le profil sans limite de durée ; éteint, le profil revient à son planning |
| Accès Internet | Capteur | État réel : autorisé, bloqué ou web uniquement |
| Accès prévu par le planning | Capteur | Ce que prévoit le planning en ce moment |
| Fin de la dérogation | Capteur (date) | Fin de la pause ou de l'autorisation temporaire |
| Prochain changement prévu | Capteur (date) | Prochaine bascule du planning |
| Appareils connectés | Capteur | Nombre d'appareils du profil joignables ; la liste détaillée (nom, connexion, bande Wi-Fi, signal) est en attributs |
| Appareil connecté | Événement | Se déclenche quand un appareil du profil se connecte (nom et adresse MAC en attributs) |

Deux actions sont disponibles pour les automatisations :

- `freebox_profiles.set_override` : bloquer ou autoriser Internet, pour une durée en minutes (ou sans limite) ;
- `freebox_profiles.clear_override` : revenir au planning.

Les profils créés plus tard dans Freebox OS apparaissent automatiquement. L'état est rafraîchi toutes les 30 secondes.

## Compatibilité

| Freebox | État |
|---|---|
| Delta | Fonctionnement de l'API vérifié |
| Ultra, Pop, Revolution à jour | Non testé : l'API Profils (Freebox OS API v8 et plus) devrait être la même. Vos retours sont bienvenus. |

L'intégration nécessite **Home Assistant 2025.2 ou plus récent** et un Home Assistant situé **sur le réseau local de la Freebox**.

Si vous l'essayez sur un autre modèle, ouvrez un ticket « Compatibilité », même si tout fonctionne : cela aide les autres utilisateurs.

## Installation

### Marketplace (Home Assistant 2026.11 et plus récent)

1. Ouvrez **Paramètres > Marketplace**.
2. Menu ⋮ > **Dépôts personnalisés**, ajoutez `https://github.com/elem-bee/ha-freebox-profiles` en type **Intégration**.
3. Recherchez **Freebox Profiles**, installez-la, puis redémarrez Home Assistant.

### HACS (Home Assistant 2025.2 à 2026.10)

Même démarche dans HACS : **Dépôts personnalisés**, type **Intégration**, puis installation et redémarrage.

### Manuelle

Copiez le dossier `custom_components/freebox_profiles` dans le dossier `config/custom_components/` de Home Assistant, puis redémarrez. Les mises à jour ne seront alors pas proposées automatiquement.

## Configuration

1. **Paramètres > Appareils et services > Ajouter une intégration > Freebox Profiles.**
2. Gardez l'adresse proposée (`mafreebox.freebox.fr`, port `443`) et validez.
3. **Acceptez la demande d'accès sur la Freebox** quand Home Assistant vous le demande (afficheur en façade de la box, ou selon votre modèle). Vous avez environ 2 minutes.
4. **Accordez la permission « Profils »** : dans Freebox OS, ouvrez **Paramètres de la Freebox > Gestion des accès > Applications**, modifiez **« Home Assistant - Freebox Profiles »** et cochez **Profils** (contrôle parental).

Sans l'étape 4, l'intégration affiche une alerte dans **Paramètres > Réparations** et réessaie régulièrement. Elle disparaît d'elle-même une fois la permission accordée.

### Notifications de connexion

Pour être prévenu sur votre téléphone chaque fois qu'un appareil d'un profil se connecte : **Paramètres > Appareils et services > Freebox Profiles > Configurer**, puis choisissez :

- **Téléphones à notifier** : les téléphones qui ont l'application Home Assistant (Companion) ;
- **Profils** : ceux qui vous intéressent (vide : tous) ;
- **Durée minimale de déconnexion** (5 minutes par défaut) : un appareil doit être resté déconnecté au moins ce temps pour qu'une reconnexion soit signalée. Cela évite d'être notifié chaque fois qu'un téléphone sort de veille. Mettez 0 pour être notifié à chaque reconnexion.

Les appareils déjà connectés au démarrage de Home Assistant, ou ajoutés à un profil alors qu'ils sont connectés, ne déclenchent rien. La détection suit le rafraîchissement : la notification arrive dans les 30 secondes.

Chaque connexion déclenche aussi l'entité *Appareil connecté* du profil et l'événement `freebox_profiles_device_connected` (`profile_id`, `profile_name`, `device_name`, `mac`), pour vos propres automatisations.

## Exemples d'automatisations

Couper Internet sur un profil à 22 h, pour 8 heures :

```yaml
automation:
  - alias: "Coupure Internet le soir"
    triggers:
      - trigger: time
        at: "22:00:00"
    actions:
      - action: freebox_profiles.set_override
        target:
          entity_id: select.chambre_ado_mode
        data:
          mode: denied
          duration: 480
```

Rendre l'accès quand un bouton est pressé, en revenant au planning :

```yaml
actions:
  - action: freebox_profiles.clear_override
    target:
      entity_id: select.chambre_ado_mode
```

Être prévenu quand un profil bloqué a un appareil qui tente de se connecter :

```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.chambre_ado_appareils_connectes
    above: 0
conditions:
  - condition: state
    entity_id: sensor.chambre_ado_acces_internet
    state: denied
actions:
  - action: notify.notify
    data:
      message: "Un appareil du profil Chambre ado est connecté pendant le blocage."
```

Notification personnalisée quand un appareil précis se connecte :

```yaml
triggers:
  - trigger: event
    event_type: freebox_profiles_device_connected
    event_data:
      mac: "AA:BB:CC:DD:EE:FF"
actions:
  - action: notify.mobile_app_mon_telephone
    data:
      message: "{{ trigger.event.data.device_name }} vient de se connecter."
```

Remplacez les identifiants d'entités par les vôtres (ils dépendent du nom de vos profils).

## Fonctionnement

- L'intégration dialogue **uniquement en local** avec la Freebox, en HTTPS, en validant le certificat avec les certificats racines publiés par Free.
- Elle s'enregistre comme une application Freebox OS : vous pouvez révoquer son accès à tout moment dans **Gestion des accès > Applications**.
- Elle utilise l'API Profils de Freebox OS (`network_control`). Pour modifier un profil, elle renvoie le profil complet avec sa liste d'appareils, comme le fait Freebox OS, afin de ne jamais vider un profil.
- Les plannings se modifient toujours dans Freebox OS ; l'intégration gère les dérogations (pauses et autorisations temporaires).

## Dépannage

- **« Impossible de joindre la Freebox »** : vérifiez que Home Assistant est sur le réseau local de la box. En cas d'erreur de certificat, réessayez en décochant « Vérifier le certificat de la Freebox » (déconseillé à long terme).
- **Alerte « permission manquante »** : voir l'étape 4 de la configuration.
- **La demande d'accès n'apparaît pas sur la box** : relancez l'ajout de l'intégration ; une demande expire au bout de 2 minutes environ.
- **Accès révoqué** : Home Assistant propose de se réauthentifier ; acceptez de nouveau la demande sur la box.
- **Journaux détaillés** :

```yaml
logger:
  logs:
    custom_components.freebox_profiles: debug
```

Les **diagnostics** (page de l'intégration > ⋮ > Télécharger les diagnostics) masquent les jetons, adresses MAC et noms : vous pouvez les joindre à un ticket.

## Contribuer

Les tickets et propositions de modification sont bienvenus, en particulier les retours de compatibilité sur d'autres modèles de Freebox.

## Licence

MIT, voir [LICENSE](LICENSE).
