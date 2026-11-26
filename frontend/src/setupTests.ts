import '@testing-library/jest-dom/vitest';

// jsdom has no layout engine — scrollIntoView is a not-implemented stub there.
Element.prototype.scrollIntoView = function scrollIntoView() { /* noop */ };

// This jsdom build exposes no localStorage (verified: typeof undefined) —
// App.tsx persists the theme through it, so provide an in-memory stand-in.
// defineProperty (not vi.stubGlobal) so per-test unstubAllGlobals() can't remove it.
if (typeof globalThis.localStorage === 'undefined') {
  const store = new Map<string, string>();
  const storage: Storage = {
    get length() { return store.size; },
    clear: () => store.clear(),
    getItem: (k) => (store.has(k) ? store.get(k)! : null),
    key: (i) => [...store.keys()][i] ?? null,
    removeItem: (k) => void store.delete(k),
    setItem: (k, v) => void store.set(k, String(v)),
  };
  Object.defineProperty(globalThis, 'localStorage', { value: storage, configurable: true });
}
