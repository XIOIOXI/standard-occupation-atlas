import { useCallback, useState } from 'react';
import { readBrowseState, writeBrowseState } from '../lib/browseStorage.js';

export function useBrowseState(key, fallback, valid) {
  const [value, update] = useState(() => readBrowseState(key, fallback, valid));
  const setValue = useCallback(next => update(current => {
    const resolved = typeof next === 'function' ? next(current) : next;
    writeBrowseState(key, resolved);
    return resolved;
  }), [key]);
  return [value, setValue];
}
