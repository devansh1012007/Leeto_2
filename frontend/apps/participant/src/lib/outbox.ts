/**
 * Offline outbox (T-5.8): IndexedDB queue with stable Idempotency-Key, in-order flush on
 * reconnect, debounced offline banner (3 s), never marks a queued submit accepted.
 */
export interface OutboxItem {
  id: string;
  route: string;
  idempotencyKey: string;
  body: unknown;
  queuedAt: number;
  attempts: number;
}

const DB_NAME = "bhctf";
const STORE = "outbox";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE)) {
        req.result.createObjectStore(STORE, { keyPath: "id" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function enqueue(item: Omit<OutboxItem, "queuedAt" | "attempts">): Promise<void> {
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).put({ ...item, queuedAt: Date.now(), attempts: 0 });
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function drain(send: (item: OutboxItem) => Promise<boolean>): Promise<number> {
  const db = await openDb();
  const items: OutboxItem[] = await new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readonly");
    const req = tx.objectStore(STORE).getAll();
    req.onsuccess = () => resolve(req.result as OutboxItem[]);
    req.onerror = () => reject(req.error);
  });
  let sent = 0;
  // in-order flush (WS-08): oldest first
  for (const item of items.sort((a, b) => a.queuedAt - b.queuedAt)) {
    const ok = await send(item);
    if (!ok) break; // stop at first failure; keep order
    await new Promise<void>((resolve) => {
      const tx = db.transaction(STORE, "readwrite");
      tx.objectStore(STORE).delete(item.id);
      tx.oncomplete = () => resolve();
    });
    sent += 1;
  }
  return sent;
}

export async function outboxSize(): Promise<number> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readonly");
    const req = tx.objectStore(STORE).count();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

/** Debounced offline detection (3 s) so flappy networks do not flash the banner. */
export function watchOnline(onChange: (offline: boolean) => void, debounceMs = 3000): () => void {
  let timer: number | undefined;
  let currentlyOffline = !navigator.onLine;
  const apply = () => {
    const next = !navigator.onLine;
    if (next !== currentlyOffline) {
      currentlyOffline = next;
      onChange(next);
    }
  };
  const goOffline = () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => onChange(true), debounceMs);
  };
  const goOnline = () => {
    window.clearTimeout(timer);
    onChange(false);
  };
  window.addEventListener("offline", goOffline);
  window.addEventListener("online", goOnline);
  onChange(currentlyOffline);
  return () => {
    window.clearTimeout(timer);
    window.removeEventListener("offline", goOffline);
    window.removeEventListener("online", goOnline);
  };
}
