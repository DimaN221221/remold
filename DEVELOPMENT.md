# Remold for developers

How to run Remold from source, build it, release it, and where things are in the code.
The user guide is in the [README](README.md).

## Run from source

```bash
git clone https://github.com/DimaN221221/remold.git
```

```bash
pip install -r requirements.txt
```

```bash
python main.py
```

Or double-click `Remold.bat`. A source checkout updates itself with `git pull --ff-only`
when automatic updates are on.

## Command line

```bash
python main.py video.mp4 -t mp3
```

```bash
python main.py photo1.heic photo2.heic -t jpg --quality 85 -o converted
```

```bash
python main.py --formats document.pdf
```

Other options: `--bitrate 320k`, `--video-quality high|medium|low`, `--height 720`, `--register-menu`, `--unregister-menu`.
The built `Remold.exe` accepts the same arguments, but it is a windowed app, so it prints nothing.

## Building and releasing

```bash
pip install pyinstaller
```

```bash
python build.py --zip
```

This produces `dist/Remold/Remold.exe` plus `dist/Remold-windows-x64.zip` and its `.sha256`.

To publish a release, bump `__version__` in `version.py`, commit, then push a matching tag
(for example `v2.1.0`). The [release workflow](.github/workflows/release.yml) builds the app on
GitHub Actions and attaches the zip and checksum to the release. The in-app updater downloads
that zip, verifies the SHA-256 and installs it when the app closes.

If you fork the project, change `REPO` in `version.py` so updates come from your repository.

## Project layout

```
main.py          entry point (window or command line)
desktop.py       app backend for the window: queue, workers, settings, updates
webui/           interface (HTML/CSS/JS), i18n.js holds the UA/EN strings
core.py          format registry, type detection, output naming, dispatcher
converters/      images (Pillow), media (ffmpeg), documents (PyMuPDF, python-docx),
                 data (csv/json/xlsx/xml), archives (zip/tar)
updater.py       GitHub Releases / git updates
shell_menu.py    Explorer context menu (HKCU, no admin rights needed)
quick.py         quick conversion from the context menu with a small progress window
store.py         settings and history in %APPDATA%\Remold
i18n.py          strings used by the Python side (menu, progress window, errors)
version.py       app name, version, update repository
```
