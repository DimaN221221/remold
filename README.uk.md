# Remold

**Швидкий і приватний конвертер файлів для Windows**: зображення, аудіо, відео, документи, таблиці та архіви.
Перетягніть файли, виберіть формат, готово. Усе обробляється на вашому комп'ютері, нічого нікуди не надсилається.

[English version](README.md)

![Remold — екран конвертера](docs/screenshots/converter-dark-uk.png)

## Можливості

- **Багато форматів в одному місці**

  | Тип | З | У |
  |---|---|---|
  | Зображення | png, jpg, webp, avif, heic/heif, gif, bmp, tiff, ico, tga, ppm | png, jpg, webp, avif, gif, bmp, tiff, ico, pdf |
  | Аудіо | mp3, wav, flac, ogg, m4a, aac, opus, wma, aiff, amr, ac3, mka | mp3, wav, flac, ogg, m4a, opus, aac, aiff, wma |
  | Відео | mp4, mkv, mov, webm, avi, flv, wmv, m4v, mpeg, 3gp, ts, ogv | mp4, mkv, mov, webm, avi, **gif** або лише звук |
  | Документи | pdf, docx, txt, md, html | pdf, docx, txt, md, html; сторінки PDF → png/jpg |
  | Таблиці | csv, tsv, json, xlsx, xml | csv, tsv, json, xlsx, xml, html, md |
  | Архіви | zip, tar, tar.gz, tar.bz2, tar.xz | zip, tar, tar.gz, tar.bz2, tar.xz |

- **Справжня оцінка розміру**: Remold пробно стискає файл з поточними налаштуваннями ще до конвертації
  (зображення — у пам'яті, відео — фрагмент 3 с), тож цифра близька до реального результату.
- **Пакетна конвертація** з правилами для кожного типу, паралельною обробкою, прогресом і скасуванням.
- **Меню провідника**: правий клік на файлах → «Конвертувати в» → формат. Результат з'являється поруч з оригіналом.
- **Автоматичні оновлення** з GitHub Releases (або `git pull`, якщо запускати з вихідного коду), їх можна вимкнути.
- Інтерфейс **українською та англійською**, світла й темна теми.
- ffmpeg уже всередині, нічого додатково встановлювати не треба.

## Завантаження

Завантажте `Remold-windows-x64.zip` з [останнього релізу](../../releases/latest), розпакуйте будь-куди
й запустіть `Remold.exe`. Папка `_internal` має лежати поруч з exe. Потрібна Windows 10/11
(програма використовує Edge WebView2, який уже є в Windows).

## Запуск з вихідного коду

```bash
git clone https://github.com/DimaN221221/remold.git
```

```bash
pip install -r requirements.txt
```

```bash
python main.py
```

Або подвійний клік на `Remold.bat`. Копія з git оновлюється через `git pull --ff-only`,
коли ввімкнено автоматичні оновлення.

## Командний рядок

```bash
python main.py video.mp4 -t mp3
```

```bash
python main.py photo1.heic photo2.heic -t jpg --quality 85 -o converted
```

```bash
python main.py --formats document.pdf
```

Зібраний `Remold.exe` приймає ті самі аргументи. Інші параметри: `--bitrate 320k`,
`--video-quality high|medium|low`, `--height 720`, `--register-menu`, `--unregister-menu`.

## Збірка й випуск

```bash
pip install pyinstaller
```

```bash
python build.py --zip
```

Результат: `dist/Remold/Remold.exe`, а також `dist/Remold-windows-x64.zip` і його `.sha256`.

Щоб випустити реліз, збільште `__version__` у `version.py`, зробіть коміт і запуште відповідний тег
(наприклад, `v2.1.0`). [Робочий процес](.github/workflows/release.yml) збере програму на GitHub Actions
і прикріпить архів з контрольною сумою до релізу. Вбудований оновлювач завантажує цей архів,
перевіряє SHA-256 і встановлює його після закриття програми.

Якщо робите форк, змініть `REPO` у `version.py`, щоб оновлення приходили з вашого репозиторію.

## Обмеження

- Конвертація документів переносить текст і базове форматування (заголовки, списки, жирний/курсив);
  картинки й складна верстка не переносяться. PDF → DOCX бере текст без збереження макета.
- У Windows 11 пункт меню провідника знаходиться в «Показати додаткові параметри» (або Shift + правий клік).
