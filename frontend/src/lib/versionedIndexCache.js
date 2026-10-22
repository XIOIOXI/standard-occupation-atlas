const DATABASE = 'job-search-local-cache-v1';
const STORE = 'indexes';

function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function read(key) {
  const database = await openDatabase();
  return new Promise((resolve, reject) => {
    const request = database.transaction(STORE, 'readonly').objectStore(STORE).get(key);
    request.onsuccess = () => resolve(request.result || null);
    request.onerror = () => reject(request.error);
  });
}

async function write(key, value) {
  const database = await openDatabase();
  return new Promise((resolve, reject) => {
    const request = database.transaction(STORE, 'readwrite').objectStore(STORE).put(value, key);
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

export async function loadVersionedIndex({ metaUrl, dataUrl, onVersion }) {
  const metaResponse = await fetch(metaUrl, { cache: 'no-store' });
  if (!metaResponse.ok) throw new Error(`index metadata ${metaResponse.status}`);
  const metadata = await metaResponse.json();
  onVersion?.(metadata.content_hash);
  const key = `job-search:${metadata.content_hash}`;
  try {
    const cached = await read(key);
    if (cached) return { payload: cached, source: 'local', version: metadata.content_hash };
  } catch { /* Private mode or storage restrictions: fall back to the network. */ }
  const dataResponse = await fetch(dataUrl, { cache: 'no-store' });
  if (!dataResponse.ok) throw new Error(`search index ${dataResponse.status}`);
  const payload = await dataResponse.json();
  try { await write(key, payload); } catch { /* The loaded index remains usable for this visit. */ }
  return { payload, source: 'network', version: metadata.content_hash };
}
