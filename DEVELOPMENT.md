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

To publish a release:

1. Bump `__version__` in `version.py`.
2. Add an entry for that version at the top of [`changelog.json`](changelog.json), in Ukrainian and English.
   Each change has a `type`: `new`, `improved` or `fix`.
3. Commit, then push a matching tag (for example `v2.1.0`).

The [release workflow](.github/workflows/release.yml) builds the app on GitHub Actions, writes the
release description from `changelog.json` (`python changelog.py --release-notes 2.1.0`) and attaches
the zip and checksum to the release. The release fails if `changelog.json` has no entry for the tag.

The same file feeds the "What's new" window in the app. It opens on its own the first time a new
version starts, and before updating the app downloads `changelog.json` from the new tag to show what
the update changes. The in-app updater downloads
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
instance.py      one window: later launches (several files from Explorer) hand their files to it
changelog.py     changelog.json: "What's new" window and GitHub release notes
quick.py         quick conversion from the context menu with a small progress window
store.py         settings and history in %APPDATA%\Remold
i18n.py          strings used by the Python side (menu, progress window, errors)
version.py       app name, version, update repository
```
