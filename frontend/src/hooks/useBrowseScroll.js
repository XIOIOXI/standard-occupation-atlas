import { useEffect } from 'react';
import { readBrowseState, writeBrowseState } from '../lib/browseStorage.js';

export function useBrowseScroll(key, ref, ready = true) {
  useEffect(() => {
    if (!ready) return;
    const node = ref?.current;
    const target = node || window;
    const position = readBrowseState(`scroll:${key}`, 0, value => Number.isFinite(value) && value >= 0);
    const frame = requestAnimationFrame(() => node ? node.scrollTo(0, position) : window.scrollTo(0, position));
    const save = () => writeBrowseState(`scroll:${key}`, node ? node.scrollTop : window.scrollY);
    target.addEventListener('scroll', save, { passive:true });
    window.addEventListener('pagehide', save);
    return () => { cancelAnimationFrame(frame); target.removeEventListener('scroll', save); window.removeEventListener('pagehide', save); };
  }, [key, ref, ready]);
}
