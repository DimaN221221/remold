/* Remold — рядки інтерфейсу українською та англійською. */
"use strict";

const I18N = {
  uk: {
    "nav.conv": "Конвертер", "nav.batch": "Пакетна обробка", "nav.hist": "Історія", "nav.settings": "Налаштування",
    "side.note": "Усе обробляється на цьому комп'ютері. Файли нікуди не надсилаються.",

    "conv.title": "Черга",
    "conv.summary": "{files} · {done} готово",
    "conv.add": "Додати файли",
    "drop.title": "Перетягніть файли або папки",
    "drop.browse": "або виберіть у провіднику",
    "drop.types": "зображення · аудіо · відео · документи · таблиці · архіви",
    "drop.release": "Відпустіть, щоб додати",
    "col.file": "Файл", "col.size": "Розмір", "col.to": "У формат", "col.status": "Стан",
    "status.waiting": "Очікує", "status.queued": "Очікує", "status.done": "Готово",
    "status.error": "Помилка", "status.cancelled": "Скасовано",
    "row.remove": "Прибрати з черги",
    "out.label": "Зберегти в", "out.same": "Поруч з оригіналом", "out.pick": "Клацніть, щоб вибрати папку",
    "out.change": "Клацніть, щоб змінити папку", "out.reset": "Зберігати поруч з оригіналом",
    "btn.clear": "Очистити", "btn.run": "Конвертувати все", "btn.stop": "Зупинити",

    "insp.file": "Файл", "insp.none": "Виберіть файл у черзі, щоб налаштувати його конвертацію.",
    "insp.to": "Конвертувати в", "insp.audioOnly": "Лише звук", "insp.quality": "Якість",
    "insp.resolution": "Роздільність", "insp.imageSize": "Зменшити до, px", "insp.now": "Зараз: {w} × {h} px",
    "insp.original": "Оригінал", "insp.noChange": "Без змін",
    "est.label": "Орієнтовний розмір", "est.result": "Розмір результату", "est.pending": "оцінюю…",
    "est.unknown": "невідомо", "est.noDuration": "не вдалося прочитати тривалість",
    "est.failed": "не вдалося оцінити", "est.slow": "пробне кодування фрагмента, кілька секунд",
    "est.depends": "Розмір результату залежить від вмісту файлу.",
    "est.pcm": "без стиснення", "est.lossless": "стиснення без втрат", "est.kbps": "{fmt} · {k} кбіт/с",
    "est.gif": "480 px · 12 кадр/с", "est.sample": "за пробним фрагментом відео",
    "insp.errTitle": "Помилка конвертації", "btn.retry": "Повторити", "btn.reveal": "Показати в папці",

    "batch.title": "Пакетна обробка",
    "batch.desc": "Формат за замовчуванням для кожного типу файлів. Застосовується до файлів у черзі та до нових.",
    "batch.all": "Усі: {type}", "batch.outDir": "Папка збереження", "batch.nameTpl": "Шаблон назви",
    "batch.tokens": "{name} · {format} · {date}", "batch.apply": "Застосувати до черги",

    "hist.title": "Історія", "hist.clear": "Очистити історію",
    "hist.empty": "Тут з'являтимуться сконвертовані файли.",
    "hist.today": "сьогодні", "hist.yesterday": "учора",

    "set.title": "Налаштування",
    "set.lang": "Мова", "set.langDesc": "Мова інтерфейсу та контекстного меню.",
    "set.theme": "Тема", "set.themeDesc": "Системна тема стежить за налаштуванням Windows.",
    "set.light": "Світла", "set.dark": "Темна", "set.system": "Системна",
    "set.menu": "Меню провідника", "set.menuDesc": "Пункт «Конвертувати в» у контекстному меню файлів.",
    "set.updates": "Оновлення", "set.auto": "Оновлювати автоматично",
    "set.autoDesc": "Перевіряти нову версію під час запуску й завантажувати її у фоні.",
    "set.version": "Версія {v}", "set.source.release": "оновлення з GitHub Releases",
    "set.source.git": "оновлення з git-репозиторію", "set.source.none": "оновлення недоступні для цієї копії",
    "set.check": "Перевірити зараз", "set.checking": "Перевіряю…", "set.latest": "Встановлено найновішу версію.",
    "set.available": "Доступна версія {v}.", "set.install": "Встановити", "set.installing": "Встановлюю…",
    "set.checkFailed": "Не вдалося перевірити: {err}", "set.repo": "Сторінка проєкту на GitHub",
    "on": "Увімкнено", "off": "Вимкнено",

    "upd.ready": "Оновлення {v} завантажено.", "upd.readyGit": "Код оновлено до {v}.",
    "upd.restart": "Перезапустити", "upd.later": "Пізніше", "upd.available": "Доступна версія {v}.",
    "upd.install": "Оновити",

    "toast.skipped": "Непідтримуваний формат — пропущено {files}: {names}",
    "toast.more": " і ще {n}", "toast.addFirst": "Спочатку додайте файли в чергу.",
    "toast.allDone": "Усі файли вже сконвертовано. Виберіть інший формат, щоб сконвертувати ще раз.",
    "toast.stopped": "Конвертацію зупинено.",
    "toast.errors": "Готово, але з помилками: {n}. Виберіть файл, щоб побачити деталі.",
    "toast.menuOn": "Готово: клацніть правою кнопкою на файлі → «Конвертувати в».",
    "toast.menuOff": "Пункт прибрано з меню провідника.", "toast.menuFail": "Не вдалося змінити меню провідника: {err}",
    "empty.title": "Черга порожня",

    "tip.shared": "<br><br>Налаштування спільне для всіх файлів у черзі.",
    "tip.format": "Формат, у який буде перетворено <b>вибраний</b> файл. Щоб задати формат одразу всім файлам одного типу — «Пакетна обробка».",
    "tip.audioOnly": "Витягнути з відео лише звукову доріжку. Результат — аудіофайл без зображення.",
    "tip.quality_image": "Ступінь стиснення для JPG, WebP та AVIF: більше — краща якість і більший файл. 80–90% зазвичай не відрізнити від оригіналу.",
    "tip.quality_audio": "Бітрейт звуку: більше — краще звучання й більший файл.",
    "tip.quality_video": "Стиснення відео: від 85% — висока якість, 55–84% — середня, нижче — низька (найменший файл). Також визначає бітрейт звуку.",
    "tip.resolution": "Зменшує відео до вибраної висоти, ширина змінюється пропорційно. Менші відео <b>не збільшуються</b>.",
    "tip.imageSize": "Зменшує зображення так, щоб довша сторона не перевищувала вибране число пікселів; пропорції зберігаються.<br><br><b>Це не збільшення (апскейл):</b> менші зображення лишаються як є.",
    "tip.estimate": "Пробне стиснення з поточними налаштуваннями ще до конвертації. Реальний розмір може трохи відрізнятися.",
    "tip.outDir": "Куди записувати результати. «Поруч з оригіналом» — у ту саму папку, де лежить вихідний файл.<br><br>Наявні файли не перезаписуються: до назви додається (1), (2)…",
    "tip.nameTpl": "Як назвати результат:<br><b>{name}</b> — ім'я вихідного файлу<br><b>{format}</b> — новий формат<br><b>{date}</b> — сьогоднішня дата<br><br>Напр., «{name}_{format}»: photo.png → photo_jpg.jpg",
    "tip.menu": "Клацніть правою кнопкою на файлі (або кількох) у провіднику → «Конвертувати в» → формат. Результат з'явиться в тій самій папці, оригінал не змінюється.<br><br>У Windows 11 пункт — у «Показати додаткові параметри».",
    "tip.auto": "Коли ввімкнено, Remold під час запуску перевіряє нову версію й завантажує її у фоні; встановлення — після перезапуску. Коли вимкнено — лише ручна перевірка.",
    "tip.history": "Зміна розміру: <b>−72%</b> — результат менший на 72%, <b>+15%</b> — більший, <b>×5</b> — у 5 разів більший.<br><br>Клацніть рядок, щоб відкрити файл у провіднику.",
    "kbps": "кбіт/с",
  },

  en: {
    "nav.conv": "Converter", "nav.batch": "Batch rules", "nav.hist": "History", "nav.settings": "Settings",
    "side.note": "Everything runs on this computer. Files never leave it.",

    "conv.title": "Queue",
    "conv.summary": "{files} · {done} done",
    "conv.add": "Add files",
    "drop.title": "Drop files or folders",
    "drop.browse": "or browse your computer",
    "drop.types": "images · audio · video · documents · spreadsheets · archives",
    "drop.release": "Release to add",
    "col.file": "File", "col.size": "Size", "col.to": "To", "col.status": "Status",
    "status.waiting": "Waiting", "status.queued": "Waiting", "status.done": "Done",
    "status.error": "Failed", "status.cancelled": "Cancelled",
    "row.remove": "Remove from queue",
    "out.label": "Save to", "out.same": "Next to the original", "out.pick": "Click to choose a folder",
    "out.change": "Click to change the folder", "out.reset": "Save next to the original",
    "btn.clear": "Clear", "btn.run": "Convert all", "btn.stop": "Stop",

    "insp.file": "File", "insp.none": "Select a file in the queue to set up its conversion.",
    "insp.to": "Convert to", "insp.audioOnly": "Audio only", "insp.quality": "Quality",
    "insp.resolution": "Resolution", "insp.imageSize": "Shrink to, px", "insp.now": "Now: {w} × {h} px",
    "insp.original": "Original", "insp.noChange": "Keep",
    "est.label": "Estimated size", "est.result": "Result size", "est.pending": "estimating…",
    "est.unknown": "unknown", "est.noDuration": "couldn't read the duration",
    "est.failed": "couldn't estimate", "est.slow": "test-encoding a short clip, a few seconds",
    "est.depends": "The result size depends on the file contents.",
    "est.pcm": "uncompressed", "est.lossless": "lossless compression", "est.kbps": "{fmt} · {k} kbps",
    "est.gif": "480 px · 12 fps", "est.sample": "based on a test clip",
    "insp.errTitle": "Conversion failed", "btn.retry": "Retry", "btn.reveal": "Show in folder",

    "batch.title": "Batch rules",
    "batch.desc": "Default format for each file type. Applies to files in the queue and to new ones.",
    "batch.all": "All {type}", "batch.outDir": "Output folder", "batch.nameTpl": "File name pattern",
    "batch.tokens": "{name} · {format} · {date}", "batch.apply": "Apply to queue",

    "hist.title": "History", "hist.clear": "Clear history",
    "hist.empty": "Converted files will show up here.",
    "hist.today": "today", "hist.yesterday": "yesterday",

    "set.title": "Settings",
    "set.lang": "Language", "set.langDesc": "Interface and Explorer menu language.",
    "set.theme": "Theme", "set.themeDesc": "System follows your Windows setting.",
    "set.light": "Light", "set.dark": "Dark", "set.system": "System",
    "set.menu": "Explorer menu", "set.menuDesc": "“Convert to” in the right-click menu of files.",
    "set.updates": "Updates", "set.auto": "Update automatically",
    "set.autoDesc": "Check for a new version on startup and download it in the background.",
    "set.version": "Version {v}", "set.source.release": "updates from GitHub Releases",
    "set.source.git": "updates from the git repository", "set.source.none": "updates aren't available for this copy",
    "set.check": "Check now", "set.checking": "Checking…", "set.latest": "You're on the latest version.",
    "set.available": "Version {v} is available.", "set.install": "Install", "set.installing": "Installing…",
    "set.checkFailed": "Couldn't check: {err}", "set.repo": "Project page on GitHub",
    "on": "On", "off": "Off",

    "upd.ready": "Update {v} is downloaded.", "upd.readyGit": "Code updated to {v}.",
    "upd.restart": "Restart", "upd.later": "Later", "upd.available": "Version {v} is available.",
    "upd.install": "Update",

    "toast.skipped": "Unsupported format — skipped {files}: {names}",
    "toast.more": " and {n} more", "toast.addFirst": "Add some files to the queue first.",
    "toast.allDone": "Everything is already converted. Pick another format to convert again.",
    "toast.stopped": "Conversion stopped.",
    "toast.errors": "Done, with {n} failed. Select a file to see why.",
    "toast.menuOn": "Done: right-click a file in Explorer → “Convert to”.",
    "toast.menuOff": "Removed from the Explorer menu.", "toast.menuFail": "Couldn't change the Explorer menu: {err}",
    "empty.title": "The queue is empty",

    "tip.shared": "<br><br>This setting is shared by all files in the queue.",
    "tip.format": "The format the <b>selected</b> file will be converted to. To set one format for every file of a type, use Batch rules.",
    "tip.audioOnly": "Extract just the audio track from the video. The result is an audio file with no picture.",
    "tip.quality_image": "Compression for JPG, WebP and AVIF: higher means better quality and a bigger file. 80–90% usually looks identical to the original.",
    "tip.quality_audio": "Audio bitrate: higher means better sound and a bigger file.",
    "tip.quality_video": "Video compression: 85% and up is high quality, 55–84% medium, lower is low (smallest file). Also sets the audio bitrate.",
    "tip.resolution": "Scales the video down to the chosen height, width follows proportionally. Smaller videos are <b>not enlarged</b>.",
    "tip.imageSize": "Scales the image down so its longer side fits the chosen number of pixels; proportions are kept.<br><br><b>This is not upscaling:</b> smaller images stay as they are.",
    "tip.estimate": "A test compression with the current settings, before converting. The real size may differ slightly.",
    "tip.outDir": "Where results are written. “Next to the original” means the same folder as the source file.<br><br>Existing files are never overwritten: (1), (2)… is added to the name.",
    "tip.nameTpl": "How to name the result:<br><b>{name}</b> — the source file name<br><b>{format}</b> — the new format<br><b>{date}</b> — today's date<br><br>E.g. “{name}_{format}”: photo.png → photo_jpg.jpg",
    "tip.menu": "Right-click one or more files in Explorer → “Convert to” → a format. The result appears in the same folder; the original is untouched.<br><br>On Windows 11 it's under “Show more options”.",
    "tip.auto": "When on, Remold checks for a new version on startup and downloads it in the background; it installs on restart. When off, only manual checks.",
    "tip.history": "Size change: <b>−72%</b> — the result is 72% smaller, <b>+15%</b> — bigger, <b>×5</b> — five times bigger.<br><br>Click a row to open the file in Explorer.",
    "kbps": "kbps",
  },
};

const MONTHS = {
  uk: ["січ.", "лют.", "бер.", "квіт.", "трав.", "черв.", "лип.", "серп.", "вер.", "жовт.", "лист.", "груд."],
  en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
};
const UNITS = { uk: ["Б", "КБ", "МБ", "ГБ"], en: ["B", "KB", "MB", "GB"] };
const CAT_LABELS = {
  uk: { image: "Зображення", audio: "Аудіо", video: "Відео", document: "Документи", data: "Таблиці", archive: "Архіви" },
  en: { image: "Images", audio: "Audio", video: "Video", document: "Documents", data: "Spreadsheets", archive: "Archives" },
};

let LANG = "uk";

function t(key, params) {
  let s = (I18N[LANG] && I18N[LANG][key]) ?? I18N.uk[key] ?? key;
  if (params) for (const [k, v] of Object.entries(params)) s = s.split(`{${k}}`).join(v);
  return s;
}

function filesWord(n) {
  if (LANG === "en") return `${n} ${n === 1 ? "file" : "files"}`;
  const m10 = n % 10, m100 = n % 100;
  const form = m10 === 1 && m100 !== 11 ? "файл" : m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14) ? "файли" : "файлів";
  return `${n} ${form}`;
}

/* Статичні тексти: data-i18n="ключ" (textContent), data-i18n-title, data-i18n-ph */
function applyStatic(root = document) {
  root.querySelectorAll("[data-i18n]").forEach((el) => (el.textContent = t(el.dataset.i18n)));
  root.querySelectorAll("[data-i18n-title]").forEach((el) => (el.title = t(el.dataset.i18nTitle)));
  document.documentElement.lang = LANG;
}
