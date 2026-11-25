# Dolaď-IT — Roadmap / Plán vývoje

**Aktuální stav: funkční Alpha 1, další vývoj probíhá.**

Tato roadmapa zpětně skládá vývoj do logických etap podle současného
kódu, dokumentace a testů. **Nejde o tvrzení, že každá etapa měla kdysi
samostatný repozitář, release nebo commit.** Historii Gitu nic nepřepisujeme.

Oficiální Git tag je `v1.0`, ale skutečná verze programu je
**`1.0.0a1` (Alpha 1)**, nikoli stabilní vydání.

## Hotové etapy

- [x] **M0 — Nápad a technický základ.** Návrh osobního offline nástroje
  pro úpravu mluveného hlasu v instruktážních videích. První Windows
  aplikace postavená na Pythonu, PySide6/Qt a FFmpeg.
- [x] **M1 — Zvukový procesor.** Úprava výšky hlasu, basů a srozumitelnosti,
  redukce stálého šumu, komprese, potlačení sykavek, normalizace LUFS a
  omezení špiček. Bez opakované komprese video obrazu.
- [x] **M2 — Praktické ovládání a dávky.** Ukládání presetů, 15sekundový
  poslech **Původní/Upravený**, výběr vstupních a výstupních složek,
  zpracování celých dávek a podsložek, stav souborů, výběr zvukové stopy
  a ochrana originálů před přepsáním.
- [x] **M3 — První Alpha a ověření.** Sestavené Windows EXE s potřebnými
  závislostmi, release `1.0.0a1`, dokumentace, automatizované vydání a
  **28 funkčních testů**, které dle protokolu prošly.

Podklady: [README](README.md) · [Changelog](CHANGELOG.md) ·
[Testy](TESTOVANI.md) · [Poznámky k Alpha 1](docs/releases/v1.0.md).

> Splněno znamená implementováno a ověřeno v popsaném rozsahu. Neznamená
> bezchybnost ve všech reálných nahrávkách.

## Další vývoj

- [ ] **M4 — Hezčí a přehlednější GUI.** Modernizovat vzhled a logické
  seskupení ovládacích prvků, zlepšit klávesnici a škálování DPI. Zachovat
  kompatibilitu presetů a stávajících funkcí.
- [ ] **M5 — Doladění na skutečných hlasech.** Poslechové testy s různými
  mikrofony, typy hlasu, hladinami šumu a délkami nahrávek. Hledat slyšitelné
  artefakty a opravit ověřené chyby. Neodvozovat kvalitu pouze z měření LUFS.
- [ ] **M6 — Pohodlnější workflow.** Zvážit přetažení souborů myší,
  zobrazení zvukové vlny při výběru náhledu, lepší report dávky, podrobné
  chybové protokoly a bezpečné navázání na přerušené dávkové zpracování.
- [ ] **M7 — Doplňkové funkce.** Ověřit, zda mají přínos nové zvukové presety,
  přesnější potlačení obtížného šumu, případně další nástroje pro mluvené
  slovo. Každé rozšíření musí mít měřitelný nebo slyšitelný přínos,
  přijatelné nároky a právně vyhovující závislosti.
- [ ] **M8 — Beta.** Rozšířit testy o dlouhá a neobvyklá média, vyhodnotit
  stabilitu a spotřebu, dokončit dokumentaci, přístupnost a licence
  distribuovaných knihoven. Teprve potom označit aplikaci jako beta.

## Checkpointy pro vývoj s AI

| Milník | Stav | Co musí být splněno |
| --- | --- | --- |
| M0 – M1: základ a audio engine | **Hotovo** | Zpracování hlasu a výstupu funguje v rozsahu Alpha 1 |
| M2: presety, náhled, dávky | **Hotovo** | Funkce jsou implementované a zahrnuté v testech |
| M3: Alpha 1 | **Hotovo** | EXE, dokumentace a 28 funkčních testů |
| M4: nové GUI | Plán | Nové rozhraní, zachované funkce, manuální UI kontrola |
| M5: zvukové ladění | Plán | Záznam poslechových výsledků na reálných hlasech |
| M6: workflow | Plán | Vybraná zlepšení a regresní testy |
| M7: nové audio funkce | Volitelné | Přínos potvrzený proti současnému řešení |
| M8: beta | Plán | Reprezentativní testy, stabilita, licence, dokumentace |

## English summary (for prospective contributors)

**Dolad-IT is a functional but unfinished Windows voice-processing application.**

**Completed:** initial architecture, audio-processing pipeline, saved presets,
a 15-second A/B preview, batch processing, packaged Alpha 1 and 28 automated
functional tests.

**Next:** improve the GUI, test with real voice recordings, refine usability
and batch reporting, evaluate a few optional audio enhancements, then prepare
a properly tested beta release.

This is a retrospective milestone plan, **not a claim of a longer Git
development history than exists**. No delivery date is promised.
