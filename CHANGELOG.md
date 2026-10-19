# Changelog

## [Unreleased]
### Changed
- Documented verified backup/startup settings and read-only failure/disk diagnostics, including the uptime-based 24-hour backup interval and monitoring limitations.
- Backed up and migrated all four desktop records into the web workspace at the user's request, preserving the original database, app and existing web records; verified authenticated calendar display.
- Allow administrator passwords of at least 10 characters at the user's request; passwords are still entered privately through the terminal.
### Added
- Structured resume registration with names, address, military dates, education and grades, top three courses, repeatable certificates/careers/awards/activities, calendar inputs, calculated periods and grouped detail cards; preserves legacy notes and supports search, validated backup/import. [#2](https://github.com/Gitcatho/idea_note/issues/2).
- Initialized GitHub source publication with an ignore-only first commit and a separate existing-source import; excludes personal data, backups, secrets, AI instructions and build/QA artifacts. [#1](https://github.com/Gitcatho/idea_note/issues/1).
- Approved ARM64 Raspberry Pi deployment and separate public HTTPS Funnel on port8443, preserving existing services and port443. Verified server APIs, public relay mobile browser, restart/persistence and locked empty production storage; administrator password awaits direct user setup. Linux process address-space cap replaces unsupported Docker memory limits.
- Single-admin web workspace with scrypt passwords, persistent revocable sessions, CSRF/origin checks and login throttling; authenticated data/backup APIs and responsive mobile layout.
- Independent web storage, daily/startup JSON backups, additive migration, Raspberry Pi Docker Compose and deployment/rollback guide. Local Python and browser checks passed (no GitHub remote; commit pending).
- Korean local AI career workspace with five tabs, CRUD, search, filters and soft-delete recovery.
- KST calendar with multiple deadlines and explicit rolling/unknown dates.
- SQLite persistence, startup JSON backups, export and additive import.
- Official-source personal bookmarks with confirmation timestamps and eligibility caveats.
- macOS Apple Silicon app bundle using pywebview and PyInstaller.

Earlier feature history predates the GitHub connection. Source registration: [#1](https://github.com/Gitcatho/idea_note/issues/1); import commit pending. Server deployment is tracked separately.
