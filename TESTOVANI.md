# Dolaď-IT v1.0 / 1.0.0 Alpha 1 — ověření vydání

Datum: 25. listopadu 2026. Windows, Python 3.12, PySide6 6.12.0,
FFmpeg / FFprobe 9.0.2 s librubberband. Python závislosti jsou zachycené
v `requirements-lock.txt`.

## Výsledek

- **28 funkčních testů prošlo**. Poslední běh přes nový úklidový spouštěč
  trval 26,43 s.
- Hotové `release/Dolaď-IT-Alpha.exe` se úspěšně spustilo v režimu offscreen
  v novém dočasném profilu. Aplikace dokončila načtení FFmpegu.
  Při této kontrole byla odstraněna proměnná pro externí FFmpeg a na PATH
  zůstaly jen systémové složky Windows; aplikace použila přibalené programy.
- EXE obsahuje verzi `1.0.0a1`, popis `Dolaď-IT — 1.0.0 Alpha 1` a příznak
  předběžného vydání Windows. Verze je také uvedená v okně aplikace.
- Testovací procesy se ukončují v samostatném Windows Job Object;
  pomocný skript počká na jejich ukončení před smazáním dočasných DLL.
- Nové spouštěče sestavení a testů odstranily své dočasné pracovní složky.

Protokoly: `reports/pytest-results.xml`, `reports/verification.json`
a `reports/exe-startup.json`. Identita vydání a kontrolní součet jsou
v `release/release-info.json` a `release/SHA256SUMS.txt`.

## Zpracování médií

Testy používají krátká lokálně generovaná videa a modulovaný harmonický
signál s pauzami a slabým šumem. Testují se i české názvy a mezery v cestách.

| Kontejner | Výstup LUFS | True peak dBTP | Shodné video pakety | Největší změna PTS |
|---|---:|---:|---|---:|
| MP4 | −16,06 | −1,48 | 200/200 | 0 ms |
| MOV | −16,06 | −1,48 | 200/200 | 0 ms |
| MKV | −15,91 | −1,49 | 200/200 | 0 ms |

SHA-256 jednotlivých komprimovaných video paketů jsou shodné před i po
zpracování. Shodují se rozlišení, frekvence a kodek. Samostatný test ověřuje
proměnlivou frekvenci a zachování matice otočení o 90°.

U záměrně posunuté zvukové stopy je A/V začátek ověřován s tolerancí 45 ms,
která zahrnuje zpoždění AAC a zaokrouhlení kontejneru. Naměřená změna metadat
začátku činila 21,334 ms u MP4/MOV a 0 ms u MKV. Test délky používá toleranci
80 ms. Nejde o záruku vzorkově přesného střihu pro libovolný kodek.

Další ověřené chování:

- Mono a stereo mají odpovídající automatický LUFS cíl; výstupní špičky
  nepřekračují −1 dBTP. Digitální ticho zůstává tiché.
- A/B ukázky mají obdobnou délku i hlasitost při změně výšky hlasu:
  původní −16,10 LUFS, upravená −16,17 LUFS, rozdíl 0,07 LUFS.
- Úprava zvolené stopy ve vícestopém MKV zachová druhou stopu bitově shodnou.
- Fungují WAV, MP3 a M4A, načítání podsložek i vyloučení vnořeného výstupu.
- Presety přežijí uložení a restart, přejmenování i smazání. Poškozený JSON
  se zálohuje. Ověřené jsou bezpečné rozsahy a obnova pracovních hodnot.
- Dávka pokračuje po rozbitém souboru, přeskočí video bez zvuku a při zastavení
  dokončí aktuální soubor. Existující výstup se nepřepíše.
- Selhání renderu nevytvoří hotový výstup a odstraní dočasnou složku.
- GUI během práce obsluhuje události. Funguje náhled, přepnutí A/B a chybové
  hlášení po odstranění vstupu mezi načtením a přehráním.

## Opakování kontrol

`Testy.bat` nebo `.venv\Scripts\python.exe tools\run_tests.py` spustí celou
sadu a ponechá pouze malé protokoly v `reports`. Testovací média odstraní.
`.venv\Scripts\python.exe tools\smoke_alpha.py` ověří metadata a start EXE.

Kontrola startu EXE proběhla automaticky v režimu offscreen, nikoli ručním
ovládáním okna. Přirozenost na hlasu uživatele nebyla posouzena; jeho vlastní
nahrávka nebyla dodaná. Testy nepokrývají všechny mobilní kodeky ani dlouhé
vícestopé projekty.
