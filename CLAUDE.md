# Contexte du projet pour Claude Code

Intégration Home Assistant `freebox_profiles` : profils (contrôle parental) de Freebox OS.
Dépôt GitHub : https://github.com/elem-bee/ha-freebox-profiles (public, licence MIT).
Le mainteneur échange en français ; le code et les commentaires sont en anglais.

## API Freebox (capturée sur une Freebox Delta)

- Découverte : `GET https://mafreebox.freebox.fr/api_version` → `api_base_url`, `api_version`, `uid`.
- Freebox OS lui-même utilise `/api/latest/` ; l'intégration utilise `/api/v{major}/` (v8 minimum).
- Authentification : `login/authorize/` (validation sur la box), puis `login/` (challenge) et
  `login/session/` avec `password = HMAC-SHA1(app_token, challenge)`. En-tête `X-Fbx-App-Auth`.
- Permission d'application nécessaire : `profile`.
- `GET network_control/` : liste des profils, avec `profile_id`, `profile_name`, `current_mode`,
  `rule_mode`, `override`, `override_mode`, `override_until`, `next_change`, `macs`, `hosts`.
- `PUT network_control/{id}` : Freebox OS renvoie l'objet complet
  (`profile_id`, `profile_name`, `profile_icon`, `override`, `override_mode`, `override_until`,
  `current_mode`, `macs`, `cdayranges`). Toujours renvoyer `macs` pour ne pas vider le profil.
  - Retour au planning : `override: false`.
  - Pause sans limite : `override: true`, `override_mode: "denied"`, `override_until: 0`.
  - Pause avec durée : `override_until` = horodatage Unix (secondes) de fin.
  - Autoriser : idem avec `override_mode: "allowed"`.
- `next_change` peut contenir une date passée : à ignorer.

## État au 2026-11-07

- Client API testé contre une Freebox simulée (autorisation, session expirée, permission
  manquante, jeton invalide, PUT) : OK.
- Jamais exécuté dans un vrai Home Assistant ni face à une vraie box : la première
  installation sur la Delta du mainteneur sert de test réel.
- Minimum : Home Assistant 2025.2. Distribution via le Marketplace (HA 2026.11+) et HACS.

## Publication

- `hacs.json` à la racine, icônes dans `custom_components/freebox_profiles/brand/`.
- Publier une version GitHub `vX.Y.Z` : le workflow `release.yml` écrit la version dans
  `manifest.json` et joint `freebox_profiles.zip`.
- Mettre à jour `CHANGELOG.md` à chaque version.
