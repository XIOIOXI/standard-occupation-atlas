const PREFIX = 'job-workbench:browse:v1:';
export function readBrowseState(key, fallback, valid = () => true, storage) {
  try {
    const value = JSON.parse((storage || globalThis.localStorage).getItem(PREFIX + key));
    return value !== null && valid(value) ? value : fallback;
  } catch { return fallback; }
}
export function writeBrowseState(key, value, storage) {
  try { (storage || globalThis.localStorage).setItem(PREFIX + key, JSON.stringify(value)); } catch { /* Browsing remains usable when storage is unavailable. */ }
}
