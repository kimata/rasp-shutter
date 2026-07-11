// シャッターメトリクス ダッシュボードの初期化と DOM 描画
// DOM への挿入は textContent / createElement のみを使用する（innerHTML 不使用）

"use strict";

function initMetricsDashboard(dataUrl) {
    fetch(dataUrl)
        .then((response) => {
            if (!response.ok) {
                throw new Error("HTTP " + response.status);
            }
            return response.json();
        })
        .then((data) => {
            renderDataPeriod(data.data_period);
            renderStatsCards(data.stats);
            renderShutterBreakdownTable(data.shutter_breakdown || []);
            renderPostponeSummary((data.postpone || {}).summary);
            renderPostponeTable((data.postpone || {}).events || [], data.reason_labels || {});
            renderThresholdText(data.current_thresholds);
            renderSensorSampleCount((data.charts || {}).sensor_samples);
            renderAllCharts(data);
            initializePermalinks();
        })
        .catch((error) => {
            console.error("Failed to load metrics data:", error);
            showDashboardError();
        });
}

function showDashboardError() {
    const errorDiv = document.getElementById("dashboard-error");
    if (errorDiv) errorDiv.classList.remove("hidden");
    setText("data-period-text", "データの読み込みに失敗しました");
}

function setText(elementId, text) {
    const element = document.getElementById(elementId);
    if (element) element.textContent = text;
}

function formatCount(value) {
    return Number(value || 0).toLocaleString();
}

function renderDataPeriod(dataPeriod) {
    const displayText = dataPeriod && dataPeriod.display_text ? dataPeriod.display_text : "データなし";
    setText("data-period-text", displayText + "のシャッター操作統計");
}

function renderStatsCards(stats) {
    if (!stats) return;
    setText("stat-manual-open", formatCount(stats.manual_open_total));
    setText("stat-manual-close", formatCount(stats.manual_close_total));
    setText("stat-auto-open", formatCount(stats.auto_open_total));
    setText("stat-auto-close", formatCount(stats.auto_close_total));
    setText("stat-failure", formatCount(stats.failure_total));
    setText("stat-total-days", formatCount(stats.total_days));
}

function appendCell(row, text, className) {
    const cell = document.createElement("td");
    cell.className = className;
    cell.textContent = text;
    row.appendChild(cell);
    return cell;
}

function appendEmptyRow(tbody, colspan, message) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = colspan;
    cell.className = "text-center text-gray-500 py-4";
    cell.textContent = message;
    row.appendChild(cell);
    tbody.appendChild(row);
}

function renderShutterBreakdownTable(breakdown) {
    const tbody = document.getElementById("shutter-breakdown-body");
    if (!tbody) return;
    tbody.replaceChildren();

    if (breakdown.length === 0) {
        appendEmptyRow(tbody, 7, "シャッター個体別の記録はまだありません。");
        return;
    }

    for (const entry of breakdown) {
        const row = document.createElement("tr");
        row.className = "border-b";
        const name =
            entry.shutter_name === null || entry.shutter_name === undefined ? "(記録前)" : entry.shutter_name;
        appendCell(row, name, "px-2 py-2 text-sm whitespace-nowrap");
        appendCell(row, formatCount(entry.manual_open), "px-2 py-2 text-sm text-right");
        appendCell(row, formatCount(entry.manual_close), "px-2 py-2 text-sm text-right");
        appendCell(row, formatCount(entry.auto_open), "px-2 py-2 text-sm text-right");
        appendCell(row, formatCount(entry.auto_close), "px-2 py-2 text-sm text-right");
        appendCell(row, formatCount(entry.operation_total), "px-2 py-2 text-sm text-right font-semibold");
        appendCell(row, formatCount(entry.failure_total), "px-2 py-2 text-sm text-right text-red-600");
        tbody.appendChild(row);
    }
}

function renderPostponeSummary(summary) {
    if (!summary) return;
    setText("postpone-total", formatCount(summary.total));
    setText("postpone-open", formatCount(summary.open_count));
    setText("postpone-close", formatCount(summary.close_count));
    setText("postpone-resolved", formatCount(summary.resolved_count));
    setText("postpone-resolve-rate", Number(summary.resolve_rate || 0).toFixed(1) + "%");
}

function formatDateTime(isoText) {
    if (!isoText) return "-";
    // ISO 形式 "YYYY-MM-DDTHH:MM:SS..." → "YYYY-MM-DD HH:MM"
    const match = String(isoText).match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/);
    return match ? match[1] + " " + match[2] : String(isoText);
}

function formatTimeOnly(isoText) {
    if (!isoText) return "-";
    const match = String(isoText).match(/T(\d{2}:\d{2})/);
    return match ? match[1] : String(isoText);
}

function formatSensorValue(value) {
    return typeof value === "number" ? value.toFixed(1) : "-";
}

function renderPostponeTable(events, reasonLabels) {
    const tbody = document.getElementById("postpone-table-body");
    if (!tbody) return;
    tbody.replaceChildren();

    if (events.length === 0) {
        appendEmptyRow(tbody, 7, "直近30日の見合わせ記録はありません。");
        return;
    }

    for (const event of events) {
        const row = document.createElement("tr");
        row.className = "border-b";

        appendCell(row, formatDateTime(event.timestamp), "px-2 py-2 text-sm whitespace-nowrap");
        appendCell(row, event.intended_action === "open" ? "☀️ 開け" : "🌙 閉め", "px-2 py-2 text-sm");
        appendCell(row, event.trigger === "schedule" ? "スケジュール" : "自動", "px-2 py-2 text-sm");
        appendCell(row, formatTimeOnly(event.scheduled_time), "px-2 py-2 text-sm whitespace-nowrap");
        appendCell(row, reasonLabels[event.reason] || event.reason, "px-2 py-2 text-sm");
        appendCell(
            row,
            "lux: " +
                formatSensorValue(event.lux) +
                " / solar: " +
                formatSensorValue(event.solar_rad) +
                " / alt: " +
                formatSensorValue(event.altitude),
            "px-2 py-2 text-xs text-gray-600 whitespace-nowrap"
        );

        let resolvedLabel = "未解消";
        let resolvedClass = "text-amber-600";
        if (event.resolved_at) {
            resolvedClass = "text-green-600";
            if (typeof event.lag_minutes === "number") {
                resolvedLabel =
                    Math.round(event.lag_minutes) + " 分後 (" + formatTimeOnly(event.resolved_at) + ")";
            } else {
                resolvedLabel = "解消済み";
            }
        }
        appendCell(row, resolvedLabel, "px-2 py-2 text-sm " + resolvedClass + " whitespace-nowrap");

        tbody.appendChild(row);
    }
}

function formatThresholdValue(value) {
    return value === null || value === undefined ? "-" : String(value);
}

function renderThresholdText(currentThresholds) {
    if (!currentThresholds) {
        setText("threshold-text", "-");
        return;
    }
    const open = currentThresholds.open || {};
    const close = currentThresholds.close || {};
    const openText =
        "開け閾値: lux≥" +
        formatThresholdValue(open.lux) +
        ", solar_rad≥" +
        formatThresholdValue(open.solar_rad) +
        ", alt≥" +
        formatThresholdValue(open.altitude);
    const closeText =
        "閉め閾値: lux<" +
        formatThresholdValue(close.lux) +
        ", solar_rad<" +
        formatThresholdValue(close.solar_rad) +
        ", alt<" +
        formatThresholdValue(close.altitude);
    setText("threshold-text", openText + " ／ " + closeText);
}

function renderSensorSampleCount(sensorSamples) {
    const count = sensorSamples && sensorSamples.sample_count ? sensorSamples.sample_count : 0;
    setText("sensor-sample-count", Number(count).toLocaleString());
}

function initializePermalinks() {
    // ページ読み込み時にハッシュがある場合はスクロール
    if (window.location.hash) {
        const element = document.querySelector(window.location.hash);
        if (element) {
            setTimeout(() => {
                element.scrollIntoView({ behavior: "smooth", block: "start" });
            }, 500); // チャート描画完了を待つ
        }
    }
}

function copyPermalink(sectionId) {
    const url = window.location.origin + window.location.pathname + "#" + sectionId;

    // Clipboard APIを使用してURLをコピー
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard
            .writeText(url)
            .then(() => {
                showCopyNotification();
            })
            .catch((err) => {
                console.error("Failed to copy: ", err);
                fallbackCopyToClipboard(url);
            });
    } else {
        // フォールバック
        fallbackCopyToClipboard(url);
    }

    // URLにハッシュを設定（履歴には残さない）
    window.history.replaceState(null, null, "#" + sectionId);
}

function fallbackCopyToClipboard(text) {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.left = "-999999px";
    textArea.style.top = "-999999px";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();

    try {
        document.execCommand("copy");
        showCopyNotification();
    } catch (err) {
        console.error("Fallback: Failed to copy", err);
        // 最後の手段として、プロンプトでURLを表示
        prompt("URLをコピーしてください:", text);
    }

    document.body.removeChild(textArea);
}

function showCopyNotification() {
    // 通知要素を作成
    const notification = document.createElement("div");
    notification.textContent = "パーマリンクをコピーしました！";
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #23d160;
        color: white;
        padding: 12px 20px;
        border-radius: 4px;
        z-index: 1000;
        font-size: 14px;
        font-weight: 500;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        transition: opacity 0.3s ease-in-out;
    `;

    document.body.appendChild(notification);

    // 3秒後にフェードアウト
    setTimeout(() => {
        notification.style.opacity = "0";
        setTimeout(() => {
            if (notification.parentNode) {
                document.body.removeChild(notification);
            }
        }, 300);
    }, 3000);
}
