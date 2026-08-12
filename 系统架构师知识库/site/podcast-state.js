(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.PodcastState = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  function emptyProgress() { return { lastChapter: '', chapters: {} }; }
  function validChapter(value) { return typeof value === 'string' && /^(?:[1-9]|1\d|20)$/.test(value); }
  function parseProgress(raw) {
    try {
      const value = typeof raw === 'string' ? JSON.parse(raw) : raw;
      if (!value || typeof value !== 'object' || Array.isArray(value)) return emptyProgress();
      const chapters = {};
      Object.entries(value.chapters || {}).forEach(([chapter, item]) => {
        if (!validChapter(chapter) || !item || typeof item !== 'object') return;
        const position = Number(item.positionSeconds);
        if (!Number.isFinite(position) || position < 0) return;
        chapters[chapter] = { positionSeconds: Math.floor(position), updatedAt: typeof item.updatedAt === 'string' ? item.updatedAt : '' };
        if (item.finished === true) chapters[chapter].finished = true;
      });
      return { lastChapter: validChapter(value.lastChapter) ? value.lastChapter : '', chapters };
    } catch (_) { return emptyProgress(); }
  }
  function savePosition(progress, chapter, positionSeconds, durationSeconds, updatedAt = new Date().toISOString()) {
    const target = parseProgress(progress);
    if (!validChapter(chapter)) return target;
    const duration = Math.max(0, Number(durationSeconds) || 0);
    const position = Math.max(0, Number(positionSeconds) || 0);
    const finished = duration > 0 && duration - position <= 5;
    target.lastChapter = chapter;
    target.chapters[chapter] = { positionSeconds: finished ? 0 : Math.floor(position), updatedAt };
    if (finished) target.chapters[chapter].finished = true;
    return target;
  }
  function savedPosition(progress, chapter) { return parseProgress(progress).chapters[chapter]?.positionSeconds || 0; }
  function isFinished(progress, chapter) { return parseProgress(progress).chapters[chapter]?.finished === true; }
  function formatSeconds(seconds) {
    const value = Math.max(0, Math.floor(Number(seconds) || 0));
    const hours = Math.floor(value / 3600); const minutes = Math.floor(value % 3600 / 60); const rest = value % 60;
    return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}` : `${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`;
  }
  function filterPodcasts(podcasts, progress, onlyIncomplete) {
    if (!onlyIncomplete) return [...podcasts];
    return podcasts.filter(item => !item.available || !isFinished(progress, item.chapter));
  }
  return { emptyProgress, parseProgress, savePosition, savedPosition, isFinished, formatSeconds, filterPodcasts };
}));
