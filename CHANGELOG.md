# Changelog

## 0.2.0 – 2026-11-25

- Interrupteur « Pause » par profil : coupe Internet sans limite de durée, et rend la main au planning une fois éteint.
- Notifications par l'application Companion quand un appareil d'un profil se connecte, réglables dans les options (téléphones, profils, durée minimale de déconnexion).
- Entité événement « Appareil connecté » par profil et événement `freebox_profiles_device_connected`.
- Catégories d'intégration dans `manifest.json`.

## 0.1.0 – 2026-11-07

Première version / First release.

- Configuration depuis l'interface, avec autorisation sur la Freebox.
- Un appareil par profil Freebox OS : mode (Planning / Autorisé / Bloqué), accès Internet actuel, accès prévu, fin de dérogation, prochain changement, appareils connectés.
- Actions `freebox_profiles.set_override` (avec durée) et `freebox_profiles.clear_override`.
- Ajout automatique des profils créés après l'installation.
- Diagnostics avec données personnelles masquées.
- Traductions française et anglaise.
