# Provedené ověření

## Aktualizace 6. listopadu 2026 — Dolaď-IT

Aktuální název aplikace je **Dolaď-IT**. Spouštějte `release/Dolaď-IT.exe`.
Byl ověřen titulek hlavního okna, viditelné záhlaví a aplikační název.
Nové EXE bylo sestaveno a úspěšně spuštěno v režimu offscreen s novým
odděleným profilem; po inicializaci zůstalo aktivní a log neobsahoval chyby.
Spouštěcí BAT a archiv zdrojů jsou aktualizované. Následuje původní protokol
ověření zvukového zpracování z 4. listopadu.

Datum: 4. listopadu 2026. Windows, Python 3.12, PySide6 6.12.0,
FFmpeg / FFprobe 9.0.2 (lokální sestava s librubberband).
Přesné Python závislosti jsou v `requirements-lock.txt`.

## Automatické testy

Celá sada: **28 úspěšných testů**, 39,38 s.
Po doplnění ošetření souboru odstraněného před náhledem byl znovu úspěšně
proveden příslušný GUI test (5,61 s). Tato změna se netýká audio pipeline.
Výstup celé sady: `test-output/pytest-results.xml`.

Testovací média jsou osmivteřinové lokálně generované klipy s obrazcem
a modulovaným harmonickým signálem podobným řeči, pauzami a slabým šumem.
Použity jsou české názvy s diakritikou a mezery v cestách.

Ověřeno:

- MP4, MOV a MKV: 200 komprimovaných video paketů před/po, každý SHA-256 shodný.
  PTS i DTS zůstávají stejné v toleranci 2 ms; skutečný největší rozdíl PTS byl 0 ms.
  Shodné rozlišení 256 × 144, frekvence 25 fps a kodek H.264.
- Samostatný klip s proměnlivou frekvencí a metadaty otočení o 90°:
  shodné video pakety, PTS a matice otočení.
- Záměrně posunutá zvuková stopa: rozdíl A/V začátku v toleranci 45 ms
  (zahrnuje zpoždění AAC enkodéru a zaokrouhlení kontejneru).
  Největší zjištěná změna metadat začátku byla 21,334 ms u MP4/MOV,
  u MKV 0 ms. Nejde o tvrzení o vzorkově přesném střihu u libovolného kodeku.
- Délka výstupu v toleranci 80 ms; délka a tempo se systematicky nemění.
- Mono i stereo: odpovídající automatický LUFS cíl; hotové špičky ≤ −1 dBTP.
- Druhá zvolená stopa ve dvoustopém MKV se upraví, první zůstane
  bitově shodná včetně názvu stopy.
- WAV, MP3, M4A lze načíst a exportovat.
- Ticho zůstává tiché; ošetřena neplatná integrovaná LUFS hodnota.
- A/B náhledy mají podobnou hlasitost a délku i při změně výšky o −2 půltóny.
- Presety: UTF-8 JSON, nové jméno, přejmenování, smazání, poslední preset,
  obnovení pracovních hodnot, neplatné rozsahy a záloha poškozeného JSON.
- Dávka s rozbitým MP4, platným WAV a videem bez zvuku: 1 hotovo,
  1 chyba, 1 přeskočeno; po chybě se pokračuje.
- Zastavení vyžádané během prvního souboru dokončí první a druhý už nespustí.
- Existující výstup se nepřepíše; funguje přípona i přeskočení.
- Chyba během renderu nepublikuje výstup a odstraní dočasnou složku.
- Podsložky fungují, vnořený výstup se z hledání vyloučí.
- GUI offscreen: načtení, výběr stopy, příprava A/B, přepnutí obou zdrojů
  přehrávače, dávka, obnova nastavení a srozumitelná chyba po smazání vstupu.
  Během práce běží časovač GUI; FFmpeg ani načítání neběží v GUI vlákně.

## Naměřené hodnoty

| Kontejner | Výstup LUFS | True peak dBTP | Shoda video paketů | Největší změna PTS |
|---|---:|---:|---|---:|
| MP4 | −16,06 | −1,48 | 200/200 | 0 ms |
| MOV | −16,06 | −1,48 | 200/200 | 0 ms |
| MKV | −15,91 | −1,49 | 200/200 | 0 ms |

Šestivteřinový A/B náhled: původní −16,10 LUFS, upravený −16,17 LUFS,
tedy rozdíl **0,07 LUFS**.
Podrobná data a SHA-256 jsou v `test-output/verification.json`.
Report lze po opakování testů vytvořit příkazem:

```powershell
.venv\Scripts\python.exe -m tools.verification_report test-output/pytest-report
```

## Vzhled a EXE

Okno bylo vykresleno a vizuálně zkontrolováno v režimu offscreen.
Obrázek: `test-output/VoiceStudio.png`. Pro offscreen kontrolu byl explicitně
načten místní Segoe UI; tento testovací krok není součástí běžného spuštění.
PyInstaller úspěšně sestavil **`release/VoiceStudio.exe`**, včetně FFmpeg a FFprobe.
Velikost výsledného EXE je přibližně 138 MB.

Samotné výsledné EXE bylo navíc spuštěno s `QT_QPA_PLATFORM=offscreen`
v novém odděleném profilu APPDATA. Vytvořilo nový aplikační log, po inicializaci
zůstalo spuštěné a log neobsahoval chyby. Testovací procesy byly ukončeny
přes vlastní Windows Job Object. Výsledek: `test-output/exe-startup.json`.

Tento test odhalil a vedl k opravě balení: PyInstaller původně přibalil
nekompatibilní `icuuc.dll` z jiné aplikace nalezené na PATH. Specifikace sestavení
ji nyní vyřadí a Qt používá ICU dodávané s Windows 11. Změna je v `VoiceStudio.spec`.

Interaktivní spuštění EXE přes automatizačního pomocníka Windows nebylo
potvrzeno: pomocník vrátil `accessibility window-opened handler did not become ready`
a při opakování `computer-use request timed out: launch_app`.
Automatický GUI test ze zdrojů i popsaný test startu konečného EXE jsou úspěšné.
Interaktivní ovládání konečného EXE tímto pomocníkem nebylo ověřeno.
Starší soubor v `dist` je pouze dřívější neplatný pokus; používejte `release`.

Subjektivní přirozenost nebyla ověřena na hlasu uživatele: jeho nahrávka
nebyla součástí zadání. Před první velkou dávkou je vhodné poslechnout ukázku
a doladit mírné hodnoty presetu. Testy nepokrývají všechny mobilní kodeky,
poškozené kontejnery ani dlouhé vícestopé projekty.
