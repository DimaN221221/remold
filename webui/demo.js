/* Демо-API з даними макета — для перегляду інтерфейсу в браузері (index.html?demo). */
window.DemoApi = function () {
  const MB = 1048576;
  const F = {
    image: ["png", "jpg", "webp", "bmp", "gif", "tiff", "ico", "avif", "pdf"],
    audio: ["mp3", "wav", "flac", "ogg", "m4a", "opus", "aac", "aiff", "wma"],
    video: ["mp4", "mkv", "avi", "mov", "webm", "gif", "mp3", "wav", "flac", "ogg", "m4a", "opus", "aac", "aiff", "wma"],
    document: ["pdf", "txt", "md", "html"],
  };
  const mk = (id, name, category, mb, target, duration) => ({
    id, name, path: "C:\\Users\\demo\\" + name, category, ext: name.split(".").pop().toUpperCase().slice(0, 4),
    size: mb * MB, formats: F[category], target, status: "waiting", progress: 0, error: "",
    result: null, resultSize: null, duration: duration || null,
  });
  const items = [
    mk(1, "відпустка_01.heic", "image", 4.2, "jpg"),
    mk(2, "банер_сайт.png", "image", 1.8, "webp"),
    mk(3, "інтерв’ю.wav", "audio", 48, "mp3", 285),
    mk(4, "подкаст_еп3.flac", "audio", 92, "mp3", 1740),
    mk(5, "демо.mov", "video", 310, "mp4", 95),
    mk(6, "договір.docx", "document", 0.8, "pdf"),
  ];
  const day = 86400000, now = Date.now();
  const H = [["відпустка_00.heic", "HEIC", "JPG", 0.28, 0], ["лекція_12.wav", "WAV", "MP3", 0.12, 0],
    ["звіт_Q3.docx", "DOCX", "PDF", 0.9, 1], ["трейлер.mkv", "MKV", "MP4", 0.66, 1],
    ["логотип.tiff", "TIFF", "PNG", 0.42, 2], ["збірка.flac", "FLAC", "AAC", 0.19, 3]];
  const history = H.map(([name, from, to, k, d]) => ({
    name, from, to, srcSize: 10 * MB, outSize: 10 * MB * k, date: new Date(now - d * day).toISOString(), path: "",
  }));
  const settings = {
    lang: null, theme: null, quality: 80, out_dir: "", name_template: "{name}_{format}", auto_update: true, video_height: 0, image_max_size: 0,
    rules: { image: "jpg", audio: "mp3", video: "mp4", document: "pdf", data: "xlsx", archive: "zip" },
  };
  let timer = null, cancelled = false;
  const push = (k, d) => setTimeout(() => window.app.onEvent(k, JSON.parse(JSON.stringify(d))), 0);

  return {
    init: async () => ({
      settings, history, items: JSON.parse(JSON.stringify(items)),
      categories: {
        image: { formats: F.image }, audio: { formats: F.audio },
        video: { formats: ["mp4", "mkv", "avi", "mov", "webm", "gif", "mp3", "wav", "flac", "m4a"] },
        document: { formats: ["pdf", "docx", "txt", "md", "html"] },
        data: { formats: ["csv", "tsv", "json", "xlsx", "xml", "html", "md"] },
        archive: { formats: ["zip", "tar", "tar.gz", "tar.bz2", "tar.xz"] },
      },
      lossy: ["jpg", "webp", "avif", "mp3", "ogg", "m4a", "aac", "opus", "wma", "mp4", "mkv", "mov", "webm", "avi"],
      audioFormats: F.audio, bitrates: [[25, 96], [45, 128], [65, 192], [85, 256], [100, 320]], running: false,
      lang: location.search.includes("en") ? "en" : "uk", version: "2.0.0", repoUrl: "", update: { source: "release" },
    }),
    pick_files: async () => ({ added: [], skipped: ["нотатки.xyz"] }),
    add_paths: async () => ({ added: [], skipped: [] }),
    set_target: async (id, t) => { const it = items.find((x) => x.id === id); if (it) it.target = t; },
    apply_rules: async (rules) => { items.forEach((it) => { if (it.formats.includes(rules[it.category])) it.target = rules[it.category]; }); return JSON.parse(JSON.stringify(items)); },
    remove: async (id) => { const i = items.findIndex((x) => x.id === id); if (i >= 0) items.splice(i, 1); },
    clear: async () => { items.length = 0; },
    save_settings: async (p) => Object.assign(settings, p),
    choose_out_dir: async () => "C:\\Users\\demo\\Конвертовано",
    reveal_item: async () => {}, reveal_path: async () => {}, clear_history: async () => { history.length = 0; },
    cancel: async () => { cancelled = true; },
    check_updates: async () => ({ source: "release", available: true, latest: "2.1.0" }),
    install_update: async () => ({ ready: true, latest: "2.1.0" }),
    restart_to_update: async () => {}, open_repo: async () => {},
    set_shell_menu: async (on) => ({ ok: true, enabled: on }),
    estimate: async (id) => { const it = items.find((x) => x.id === id); return { bytes: it ? it.size * 0.3 : null }; },
    start: async (ids) => {
      const todo = items.filter((it) => (ids ? ids.includes(it.id) : it.status !== "done"));
      if (!todo.length) return false;
      cancelled = false;
      push("running", true);
      let i = 0;
      const step = () => {
        const it = todo[i];
        if (!it) { push("running", false); return; }
        if (cancelled) { todo.slice(i).forEach((x) => { x.status = "cancelled"; x.progress = 0; push("item", x); }); push("running", false); return; }
        if (it.status !== "running") { it.status = "running"; it.progress = 0; push("item", it); }
        it.progress = Math.min(1, it.progress + 0.07);
        push("progress", { id: it.id, progress: it.progress });
        if (it.progress >= 1) {
          Object.assign(it, { status: "done", resultSize: it.size * 0.35, result: it.path });
          push("item", it);
          push("history", { name: it.name, from: it.ext, to: it.target.toUpperCase(), srcSize: it.size, outSize: it.size * 0.35, date: new Date().toISOString(), path: "" });
          i++;
        }
        timer = setTimeout(step, 60);
      };
      step();
      return true;
    },
  };
};
