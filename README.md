# Dolaď-IT

Malá lokální aplikace pro Windows 11: jednou nastavíte hlas, uložíte preset,
potom vyberete složku a stisknete **Zpracovat složku**. Rozhraní je v češtině.
Za běhu nepotřebuje internet, účet ani API. Zpracovává celou vybranou zvukovou
stopu, tedy i případnou hudbu nebo jiné zvuky, které jsou s hlasem smíchané.

Pokud máte složku `release`, můžete rovnou spustit `release\Dolaď-IT.exe`
bez instalace Pythonu. Spouštěcí BAT upřednostní toto EXE, pokud existuje.
Archiv `VoiceStudio-zdroje.zip` obsahuje zdrojové kódy a testy, nikoli Python
prostředí či velké binárky FFmpeg; ty jsou součástí samostatného EXE.

## Spuštění

1. Nainstalujte 64bitový Python 3.11 nebo novější z [python.org](https://www.python.org/downloads/windows/)
   (včetně Python Launcheru `py`). Ověřeno na Pythonu 3.12 / PySide6 6.12.0.
2. Spusťte **Instalace.bat**. Vytvoří vlastní `.venv` a nainstaluje PySide6.
   Pouze tato první instalace stahuje knihovny z internetu.
3. Zpřístupněte FFmpeg podle následujícího odstavce, pokud ještě není přiložen.
4. Spusťte **Spustit_Voice_Studio.bat**.

Přímo z terminálu: `.venv\Scripts\python.exe -m voicestudio`.

## FFmpeg a FFprobe

Oba programy musí být ze stejné sestavy. Pořadí hledání:

1. Složka vybraná tlačítkem **FFmpeg…** (zapamatuje se).
2. Složka v proměnné prostředí `VOICE_STUDIO_FFMPEG`.
3. `tools\ffmpeg` vedle zdrojů/EXE, případně přímo vedle EXE.
4. Binárky vložené do EXE při sestavení PyInstallerem.
5. Složka obsahující `ffmpeg` na `PATH`, pokud obsahuje také `ffprobe`.

Použijte plnou sestavu z [oficiálního rozcestníku FFmpeg](https://ffmpeg.org/download.html#build-windows).
`ffmpeg.exe` a `ffprobe.exe` můžete vložit do `tools\ffmpeg`.
Filtr `rubberband` umožňuje skutečnou změnu výšky při zachování formantů a tempa;
bez něj je nutné nastavit Hloubku na 0. Totéž platí pro `afftdn` (Čistota) a
`deesser` (Sykavky). Aplikace chybějící filtr oznámí a neprovádí náhradní,
skrytou změnu rychlosti. Schopnosti ověří příkaz `ffmpeg -hide_banner -filters`.

V dodané pracovní kopii jsou oba programy již přiloženy z místní instalace.

## Běžné použití

1. Vyberte vstupní a jinou výstupní složku. Můžete zahrnout podsložky.
2. Stiskněte **Načíst soubory**, vyberte nahrávku a případně zvukovou stopu.
3. Vyberte preset Přirozený, Hlubší nebo Dokumentární a upravte posuvníky.
4. **Přehrát ukázku** připraví 15 sekund od zadaného času. Tlačítko
   **Poslech: Upravený / Původní** přepíná verzi na přibližně stejné pozici.
   Původní ukázka má pouze vyrovnanou hlasitost pro spravedlivé porovnání.
5. Použijte **Uložit jako nový…**. Posuvníky nemění uložený preset;
   poslední pracovní hodnoty se také obnoví při příštím spuštění.
6. **Zpracovat složku** vždy znovu načte aktuální obsah složky a spustí dávku.
   Po chybě jednotlivého souboru pokračuje. Výsledek a úplný text chyby jsou
   v tabulce (tooltip nad stavem); pod tabulkou je souhrn.
7. **Zastavit po aktuálním souboru** dokončí a uloží současný soubor.
   Zavření okna během práce rovněž počká na dokončení aktuální úlohy.

U více zvukových stop aplikace zvolí jedinou stopu označenou jako výchozí,
nebo využije váš výběr u označeného souboru. Pokud je výběr nejednoznačný,
zobrazí před začátkem dávky dialog pro každý takový soubor. Ostatní stopy
zachová bitově kopírováním. Dialog dovoluje soubor přeskočit nebo celou přípravu zrušit.
Podporovaná upravovaná stopa je mono nebo stereo; prostorový zvuk se bez souhlasu
nepřevádí a takový soubor skončí se srozumitelnou chybou.

## Co se skutečně provádí

- Jemný horní propust na 65 Hz, EQ plnosti (do +3,5 dB na 150 Hz, mírné ubrání 320 Hz)
  a srozumitelnosti (do +3 dB na 3 kHz).
- Konzervativní komprese s měkkým kolenem, bez automatického makeup gainu.
- Stálý šum: FFT filtr `afftdn`, maximálně 12 dB redukce, adaptivní sledování šumu.
  Nejde o AI izolaci hlasu; neodstraní spolehlivě ozvěnu, vítr ani jiného mluvčího.
- Sykavky: skutečný filtr `deesser`, omezená intenzita a maximální útlum.
- Výška: `rubberband`, rozsah ±2 půltóny, zachování formantů, tempo 1.
- Dvouprůchodový `loudnorm`, automaticky −16 LUFS mono / −14 LUFS stereo,
  volitelně pevně −14/−16/−18 LUFS. Tichu nebo velmi krátkým klipům nelze přiřadit
  spolehlivou integrovanou LUFS hodnotu; i tehdy se použije ochrana špiček.
- Interní true peak cíl −1,5 dBTP ponechává rezervu pro AAC/MP3. Hotový výstup
  se znovu změří. Při překročení −1 dBTP se vyrenderuje s větší rezervou, nejvýše
  třikrát. Pokud špičky stále nevyhoví, soubor se nepublikuje.
- A/B náhledy jsou nezávisle normalizované ke stejné cílové LUFS hodnotě.
  U krátkých, velmi dynamických nebo převážně tichých ukázek může být shoda méně přesná.

Filtry vycházejí z [oficiální dokumentace FFmpeg](https://ffmpeg.org/ffmpeg-filters.html).
Přirozenost barvy hlasu je subjektivní: před první dávkou si poslechněte ukázku.

## Výstupy a bezpečnost souborů

- Přípony a struktura podsložek zůstávají, název dostane `_voice`.
- Kolize: číselná přípona `_2`, `_3` atd., nebo přeskočení podle volby.
- Vstup a výstup nesmějí být stejné; výstup nesmí být nadřazený vstupu.
  Výstup uvnitř vstupu je při hledání vyloučen. Symbolické odkazy se nesledují.
- Veškeré video se mapuje s `-c:v copy`; žádný videoenkodér se nepoužívá.
  Kopírují se ostatní zvukové stopy, metadata, kapitoly, titulky i datové stopy.
  U nekompatibilního streamu/kontejneru se vypíše chyba, nic se tiše nezahodí.
- Časová razítka se zachovávají společným posunem (`-copyts -start_at_zero`),
  nikoli samostatným nulováním zvuku. Nepoužívá se `-shortest` ani změna FPS.
  AAC/MP3 mají běžné zpoždění kodeku; podporované kontejnery ho kompenzují.
- MP4/MOV/MKV/M4A: AAC 192 kb/s mono nebo 256 kb/s stereo, 48 kHz;
  WAV: 24bit PCM, 48 kHz; MP3: MP3 192/256 kb/s, 48 kHz.
  Obraz včetně rozlišení a frekvence se nepřepočítává.
- Render je v dočasné složce na výstupním disku. Teprve po úspěchu a kontrole
  se atomicky přesune pod finální název bez přepsání existujícího souboru.
  Při normální chybě se dočasná složka odstraní. Po výpadku proudu může zůstat
  skrytá složka `.voice-studio-*`; není hotovým výstupem a lze ji smazat při zavřené aplikaci.

## Uložená nastavení

`%APPDATA%\VoiceStudio\presets.json` a `settings.json`, UTF-8 JSON, atomický zápis.
Poškozený JSON se zálohuje jako `.damaged-*` a použijí se výchozí hodnoty.
Log je `%APPDATA%\VoiceStudio\voice-studio.log` (rotace, nejvýše 3 × 2 MB).
Logy obsahují lokální cesty a chyby FFmpeg, nikam se neodesílají.

## Samostatné EXE

Před opakovaným sestavením zavřete běžící Dolaď-IT.
Spusťte **Vytvorit_EXE.bat**. Výsledkem je `release\Dolaď-IT.exe` bez potřeby
instalovat Python. Pokud jsou binárky FFmpeg v `tools\ffmpeg` při sestavení,
budou vložené do jediného EXE. První start proto chvíli rozbaluje knihovny do
dočasné složky. Bez vložených binárek je možné FFmpeg dodat vedle EXE či přes PATH.
Sestavení se provádí na Windows; postup odpovídá [dokumentaci PyInstalleru](https://pyinstaller.org/en/stable/usage.html).

Při distribuci respektujte licence PySide6/Qt, FFmpeg a knihoven konkrétní
sestavy (zejména Rubber Band). Zdroj aplikace je v `voicestudio`.

## Testy

Spusťte **Testy.bat**, nebo nainstalujte `requirements-dev.txt` a spusťte
`.venv\Scripts\python.exe -m pytest -q`. Integrační testy vyžadují FFmpeg/FFprobe.
Generují krátká lokální videa a zvuk, porovnávají SHA-256 komprimovaných video
paketů, časová razítka a A/V offset, měří LUFS a true peak, kontrolují presety,
kolize, zastavení i pokračování dávky po chybě. GUI testy běží v režimu offscreen.
Konkrétní provedené ověření je v `TESTOVANI.md`.
