# Remold

**A fast, private file converter for Windows:** images, audio, video, documents, spreadsheets and archives.
Drop files in, pick a format, done. Everything happens on your computer; nothing is uploaded anywhere.

[Українська версія](README.uk.md)

![Remold — converter screen](docs/screenshots/converter-light-en.png)

## Features

- **Many formats in one place**

  | Type | From | To |
  |---|---|---|
  | Images | png, jpg, webp, avif, heic/heif, gif, bmp, tiff, ico, tga, ppm | png, jpg, webp, avif, gif, bmp, tiff, ico, pdf |
  | Audio | mp3, wav, flac, ogg, m4a, aac, opus, wma, aiff, amr, ac3, mka | mp3, wav, flac, ogg, m4a, opus, aac, aiff, wma |
  | Video | mp4, mkv, mov, webm, avi, flv, wmv, m4v, mpeg, 3gp, ts, ogv | mp4, mkv, mov, webm, avi, **gif**, or audio only |
  | Documents | pdf, docx, txt, md, html | pdf, docx, txt, md, html; PDF pages → png/jpg |
  | Spreadsheets | csv, tsv, json, xlsx, xml | csv, tsv, json, xlsx, xml, html, md |
  | Archives | zip, tar, tar.gz, tar.bz2, tar.xz | zip, tar, tar.gz, tar.bz2, tar.xz |

- **Know the size before you convert.** Remold test-compresses the file with your settings first,
  so the estimated size is close to the real result.
- **Many files at once.** Set a default format for each file type, and convert the whole queue in one click,
  with progress and a Stop button.
- **Right from Explorer.** Right-click files → *Convert to* → a format. The result appears next to the original.
- **Automatic updates**, which you can turn off.
- **English and Ukrainian** interface, light and dark themes.
- Everything is included — no extra programs to install.

## Download and install

1. Download [Remold-windows-x64.zip](https://github.com/DimaN221221/remold/releases/latest/download/Remold-windows-x64.zip).
2. Unzip it into any folder you like (for example, *Documents\Remold*).
3. Run `Remold.exe`. Keep the `_internal` folder next to it — the app needs it.

Requires Windows 10 or 11 (64-bit).
If Windows shows *“Windows protected your PC”*, click **More info → Run anyway**: the app is not signed with a paid
certificate, which is why the warning appears.

All versions and their change notes are on the [Releases](https://github.com/DimaN221221/remold/releases) page.

## Using it

1. Drag files or whole folders into the window (or click **Add files**).
2. Click a file in the queue to choose its format and quality. The estimated size updates as you change them.
3. Choose where to save: next to the originals or a folder of your choice.
4. Click **Convert all**. Originals are never changed.

Other screens:

- **Batch rules** — the default format for each file type, an output folder and a file name pattern.
- **History** — everything you've converted; click a row to open the file in Explorer.
- **Settings** — language, theme, the Explorer menu item, and updates.

### From Explorer

Turn on **Explorer menu** in Settings. Then right-click one or more files → **Convert to** → a format.
A small window shows the progress, and the result appears in the same folder.
On Windows 11 the item is under **Show more options** (or Shift + right-click).

## Good to know

- Documents keep their text and basic formatting (headings, lists, bold and italic); pictures and complex
  layout are not carried over. PDF → DOCX takes the text without the original page layout.

## Updates

With automatic updates on, Remold checks for a new version at startup and downloads it in the background;
it installs when you close the app. You can also check manually in **Settings → Check now**.

## Privacy

Files are converted on your computer and never uploaded. Remold only goes online to check GitHub for updates,
and you can turn that off. Settings and history are kept in `%APPDATA%\Remold`.

## Uninstalling

1. In Settings, turn off **Explorer menu** so the *Convert to* item disappears.
2. Close Remold and delete the folder you unzipped it into.
3. To remove settings and history as well, delete `%APPDATA%\Remold`.

---

Running from source, building the app or curious how it works? See [DEVELOPMENT.md](DEVELOPMENT.md).
