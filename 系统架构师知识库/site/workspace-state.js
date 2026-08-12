(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.WorkspaceState = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  const clone = value => JSON.parse(JSON.stringify(value ?? {}));

  function createStore(seed = {}) {
    const values = new Map(Object.entries(clone(seed)));
    return {
      read(name) { return clone(values.get(name) || {}); },
      patch(name, next) { values.set(name, { ...clone(values.get(name) || {}), ...clone(next) }); },
      clear(name) { values.delete(name); },
    };
  }

  return { createStore };
}));
