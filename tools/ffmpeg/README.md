Sem patří `ffmpeg.exe` a `ffprobe.exe` ze stejné plné sestavy FFmpeg.
Aplikace je také najde přes PATH, proměnnou VOICE_STUDIO_FFMPEG
nebo tlačítko FFmpeg v hlavním okně.

Oficiální rozcestník pro Windows: https://ffmpeg.org/download.html#build-windows
Pro změnu výšky hlasu musí sestava obsahovat filtr rubberband.
Pro redukci šumu afftdn, pro sykavky deesser.

V tomto pracovním prostředí byly binárky zkopírovány z již dostupné lokální
sestavy v sousedním projektu VideoEnhancer; za běhu na ně aplikace neodkazuje.
Při další distribuci FFmpeg dodržte licenci konkrétní sestavy včetně
licencí vložených knihoven; konfiguraci vypíše `ffmpeg -version`.
