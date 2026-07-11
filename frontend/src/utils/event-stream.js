// サーバーの SSE (/api/event) への接続を 1 本に集約するモジュール。
// 各コンポーネントが個別に EventSource を張ると接続が増え、
// unmount 後の再接続タイマーがリークするため、ここで一元管理する。

const RECONNECT_DELAY_MS = 10000;

let eventSource = null;
let reconnectTimer = null;
let endpointUrl = null;

// eventType ("log" / "schedule" など) → Set<callback>
const subscribers = new Map();

function hasSubscribers() {
    for (const callbacks of subscribers.values()) {
        if (callbacks.size > 0) {
            return true;
        }
    }
    return false;
}

function connect() {
    if (eventSource !== null || endpointUrl === null) {
        return;
    }
    eventSource = new EventSource(endpointUrl);
    eventSource.addEventListener("message", (e) => {
        const callbacks = subscribers.get(e.data);
        if (!callbacks) {
            return;
        }
        callbacks.forEach((callback) => callback());
    });
    eventSource.onerror = () => {
        if (eventSource !== null && eventSource.readyState === EventSource.CLOSED) {
            eventSource.close();
            eventSource = null;
            if (hasSubscribers()) {
                reconnectTimer = setTimeout(() => {
                    reconnectTimer = null;
                    connect();
                }, RECONNECT_DELAY_MS);
            }
        }
    };
}

function disconnect() {
    if (reconnectTimer !== null) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }
    if (eventSource !== null) {
        eventSource.close();
        eventSource = null;
    }
}

/**
 * サーバーイベントを購読する。
 *
 * @param {string} url SSE エンドポイント URL
 * @param {string} eventType 購読するイベント種別（サーバーが e.data として送る文字列）
 * @param {Function} callback イベント受信時に呼ばれる関数
 * @returns {Function} 購読解除関数（コンポーネントの unmounted で必ず呼ぶこと）
 */
export function subscribeEvent(url, eventType, callback) {
    endpointUrl = url;
    if (!subscribers.has(eventType)) {
        subscribers.set(eventType, new Set());
    }
    subscribers.get(eventType).add(callback);
    connect();

    return () => {
        const callbacks = subscribers.get(eventType);
        if (callbacks) {
            callbacks.delete(callback);
        }
        if (!hasSubscribers()) {
            disconnect();
        }
    };
}
