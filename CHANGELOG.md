# Přehled změn

## v1.0 — 1.0.0 Alpha 1 · 25. 11. 2026

První označené vydání Dolaď-IT pro Windows 11. Gitový tag je `v1.0`,
interní verze aplikace `1.0.0a1`; vydání je nadále označené jako Alpha.

### Funkce vydání

- Úprava výšky se zachováním formantů, EQ plnosti a srozumitelnosti,
  potlačení stálého šumu, komprese a de-essing.
- Dvouprůchodová normalizace LUFS a kontrola hotového zvuku do −1 dBTP.
- Krátký A/B náhled s přibližně vyrovnanou hlasitostí.
- Vlastní JSON presety a obnovení posledního pracovního nastavení.
- Dávka souborů i podsložek, výběr zvukové stopy a pokračování po chybě.
- Kopírování obrazu bez rekomprese, ochrana originálů a atomické dokončení výstupu.
- Samostatné EXE s přibaleným FFmpeg a FFprobe, verze a příznak Alpha ve vlastnostech souboru.

### Údržba a dokumentace

- Odstraněné staré sestavy, archivy, cache a dočasná testovací média.
- Sestavení a testy používají automaticky uklízené pracovní složky.
- README, poznámky k vydání, technický popis a screenshot skutečného GUI.
- Automatizované ověření, sestavení, tag a publikace předběžného vydání přes GitHub Actions.
- 28 funkčních testů a samostatná kontrola startu sestaveného EXE.
