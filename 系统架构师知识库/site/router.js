(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AppRouter = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  const names = new Set(['today', 'knowledge', 'practice', 'questions', 'training', 'podcasts', 'records']);

  function parseHash(hash) {
    const path = String(hash || '').replace(/^#\/?/, '').split('?')[0];
    const parts = path.split('/').filter(Boolean).map(decodeURIComponent);
    if (!parts.length) return { name: 'today', params: {} };
    if (parts[0] === 'questions' && parts[1]) return { name: 'question-detail', params: { id: parts[1] } };
    return names.has(parts[0]) ? { name: parts[0], params: {} } : { name: 'today', params: {} };
  }

  function toHash(name, params = {}) {
    if (name === 'question-detail') return `#/questions/${encodeURIComponent(params.id || '')}`;
    return `#/${names.has(name) ? name : 'today'}`;
  }

  function subscribe(listener, target = window) {
    const notify = () => listener(parseHash(target.location.hash));
    target.addEventListener('hashchange', notify);
    return () => target.removeEventListener('hashchange', notify);
  }

  return { parseHash, toHash, subscribe };
}));
