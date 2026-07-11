// シャッターメトリクス ダッシュボードのチャート描画定義
// data は /api/metrics/data のレスポンス全体を受け取る

"use strict";

const METRICS_COLOR = {
    open: { bg: "rgba(255, 206, 84, 0.7)", border: "rgba(255, 206, 84, 1)" },
    close: { bg: "rgba(153, 102, 255, 0.7)", border: "rgba(153, 102, 255, 1)" },
    openLine: { border: "rgba(255, 206, 84, 1)", bg: "rgba(255, 206, 84, 0.1)" },
    closeLine: { border: "rgba(153, 102, 255, 1)", bg: "rgba(153, 102, 255, 0.1)" },
    postponeOpen: { bg: "rgba(251, 191, 36, 0.7)", border: "rgba(251, 191, 36, 1)" },
    postponeClose: { bg: "rgba(59, 130, 246, 0.7)", border: "rgba(59, 130, 246, 1)" },
    failure: { bg: "rgba(239, 68, 68, 0.7)", border: "rgba(239, 68, 68, 1)" },
    whatIf: { bg: "rgba(16, 185, 129, 0.7)", border: "rgba(16, 185, 129, 1)" },
};

// センサーサンプルの context 別スタイル
const SENSOR_CONTEXT_STYLE = {
    auto_open_window: {
        label: "開け自動制御時間帯",
        bg: "rgba(251, 191, 36, 0.5)",
        border: "rgba(245, 158, 11, 0.8)",
    },
    auto_close_window: {
        label: "閉め自動制御時間帯",
        bg: "rgba(99, 102, 241, 0.5)",
        border: "rgba(79, 70, 229, 0.8)",
    },
    off_hours: {
        label: "時間帯外",
        bg: "rgba(107, 114, 128, 0.4)",
        border: "rgba(75, 85, 99, 0.7)",
    },
    unknown: {
        label: "時間帯記録なし",
        bg: "rgba(209, 213, 219, 0.5)",
        border: "rgba(156, 163, 175, 0.7)",
    },
};

// ヒストグラム生成のヘルパー関数（最後のビンは最大値も含める）
function createHistogram(data, bins) {
    const hist = Array(bins.length - 1).fill(0);
    data.forEach((value) => {
        for (let i = 0; i < bins.length - 1; i++) {
            const isLastBin = i === bins.length - 2;
            if (value >= bins[i] && (isLastBin ? value <= bins[i + 1] : value < bins[i + 1])) {
                hist[i]++;
                break;
            }
        }
    });
    return hist;
}

// 値の範囲を 20 分割してヒストグラム（%）を計算
function calcHistPercent(data) {
    if (!data || data.length === 0) return { bins: [], histPercent: [], maxPercent: 0 };
    const minVal = Math.min(...data);
    const maxVal = Math.max(...data);
    const bins = Array.from({ length: 21 }, (_, i) => minVal + ((maxVal - minVal) * i) / 20);
    const hist = createHistogram(data, bins);
    const total = data.length;
    const histPercent = hist.map((count) => (total > 0 ? (count / total) * 100 : 0));
    const maxPercent = Math.max(...histPercent);
    return { bins, histPercent, maxPercent };
}

// 頻度（%）を縦軸にした棒グラフの共通 options
function percentBarOptions(xLabel, yMax) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            y: {
                beginAtZero: true,
                max: yMax,
                title: { display: true, text: "頻度（%）" },
                ticks: {
                    callback: function (value) {
                        return value + "%";
                    },
                },
            },
            x: { title: { display: true, text: xLabel } },
        },
    };
}

// 件数を縦軸にした棒グラフの共通 options
function countBarOptions(xLabel, stacked) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            x: { stacked: Boolean(stacked), title: xLabel ? { display: true, text: xLabel } : undefined },
            y: {
                stacked: Boolean(stacked),
                beginAtZero: true,
                title: { display: true, text: "件数" },
            },
        },
    };
}

// 時系列折れ線グラフの共通 options
function timeSeriesLineOptions(yScale) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        scales: {
            y: yScale,
            x: { title: { display: true, text: "日付" } },
        },
    };
}

// 数値のヒストグラム（件数）を 1 データセットで描画する共通関数
function renderSimpleHistogram(canvasId, values, label, xLabel, color, formatBin) {
    const ctx = document.getElementById(canvasId);
    if (!ctx || !values || values.length === 0) return;
    const minVal = Math.min(...values, 0);
    const maxVal = Math.max(...values, 0);
    const span = maxVal - minVal || 1;
    const binCount = 20;
    const bins = Array.from({ length: binCount + 1 }, (_, i) => minVal + (span * i) / binCount);
    const hist = createHistogram(values, bins);
    const format = formatBin || ((b) => b.toFixed(1));
    new Chart(ctx, {
        type: "bar",
        data: {
            labels: bins.slice(0, -1).map(format),
            datasets: [
                {
                    label: label,
                    data: hist,
                    backgroundColor: color.bg,
                    borderColor: color.border,
                    borderWidth: 1,
                },
            ],
        },
        options: countBarOptions(xLabel, false),
    });
}

// 時刻ヒストグラム（開/閉の 2 個）
function generateTimeCharts(chartData) {
    const configs = [
        {
            canvasId: "openTimeHistogramChart",
            values: chartData.open_times || [],
            label: "☀️ 開操作頻度",
            color: METRICS_COLOR.open,
        },
        {
            canvasId: "closeTimeHistogramChart",
            values: chartData.close_times || [],
            label: "🌙 閉操作頻度",
            color: METRICS_COLOR.close,
        },
    ];

    for (const config of configs) {
        const ctx = document.getElementById(config.canvasId);
        if (!ctx || config.values.length === 0) continue;

        const bins = Array.from({ length: 24 }, (_, i) => i);
        const hist = Array(24).fill(0);
        config.values.forEach((time) => {
            const hour = Math.floor(time);
            if (hour >= 0 && hour < 24) hist[hour]++;
        });
        const total = config.values.length;
        const histPercent = hist.map((count) => (total > 0 ? (count / total) * 100 : 0));

        new Chart(ctx, {
            type: "bar",
            data: {
                labels: bins.map((h) => h + ":00"),
                datasets: [
                    {
                        label: config.label,
                        data: histPercent,
                        backgroundColor: config.color.bg,
                        borderColor: config.color.border,
                        borderWidth: 1,
                    },
                ],
            },
            options: percentBarOptions("時刻", 100),
        });
    }
}

// 時系列チャート（操作時刻・照度・日射・太陽高度の 4 個）
function generateTimeSeriesCharts(chartData) {
    const timeSeries = chartData.time_series;
    if (!timeSeries || !timeSeries.dates || timeSeries.dates.length === 0) return;

    const configs = [
        {
            canvasId: "timeSeriesChart",
            openKey: "open_times",
            closeKey: "close_times",
            openLabel: "☀️ 開操作時刻",
            closeLabel: "🌙 閉操作時刻",
            yScale: {
                beginAtZero: true,
                max: 24,
                title: { display: true, text: "時刻" },
                ticks: {
                    callback: function (value) {
                        const hour = Math.floor(value);
                        const minute = Math.round((value - hour) * 60);
                        return hour + ":" + (minute < 10 ? "0" : "") + minute;
                    },
                },
            },
        },
        {
            canvasId: "luxTimeSeriesChart",
            openKey: "open_lux",
            closeKey: "close_lux",
            openLabel: "☀️ 開操作時照度",
            closeLabel: "🌙 閉操作時照度",
            yScale: {
                beginAtZero: true,
                title: { display: true, text: "照度（lux）" },
                ticks: {
                    callback: function (value) {
                        return value.toLocaleString();
                    },
                },
            },
        },
        {
            canvasId: "solarRadTimeSeriesChart",
            openKey: "open_solar_rad",
            closeKey: "close_solar_rad",
            openLabel: "☀️ 開操作時日射",
            closeLabel: "🌙 閉操作時日射",
            yScale: { beginAtZero: true, title: { display: true, text: "日射（W/m²）" } },
        },
        {
            canvasId: "altitudeTimeSeriesChart",
            openKey: "open_altitude",
            closeKey: "close_altitude",
            openLabel: "☀️ 開操作時太陽高度",
            closeLabel: "🌙 閉操作時太陽高度",
            yScale: { title: { display: true, text: "太陽高度（度）" } },
        },
    ];

    for (const config of configs) {
        const ctx = document.getElementById(config.canvasId);
        if (!ctx) continue;
        new Chart(ctx, {
            type: "line",
            data: {
                labels: timeSeries.dates,
                datasets: [
                    {
                        label: config.openLabel,
                        data: timeSeries[config.openKey],
                        borderColor: METRICS_COLOR.openLine.border,
                        backgroundColor: METRICS_COLOR.openLine.bg,
                        tension: 0.1,
                        spanGaps: true,
                    },
                    {
                        label: config.closeLabel,
                        data: timeSeries[config.closeKey],
                        borderColor: METRICS_COLOR.closeLine.border,
                        backgroundColor: METRICS_COLOR.closeLine.bg,
                        tension: 0.1,
                        spanGaps: true,
                    },
                ],
            },
            options: timeSeriesLineOptions(config.yScale),
        });
    }
}

// センサーヒストグラム（自動/手動 × 開/閉 × 照度/日射/太陽高度の 12 個）
function generateSensorHistogramCharts(chartData) {
    const sensors = [
        {
            key: "lux",
            canvas: "Lux",
            title: "照度",
            axis: "照度（lux）",
            format: (b) => Math.round(b).toLocaleString(),
        },
        {
            key: "solar_rad",
            canvas: "SolarRad",
            title: "日射",
            axis: "日射（W/m²）",
            format: (b) => Math.round(b).toLocaleString(),
        },
        {
            key: "altitude",
            canvas: "Altitude",
            title: "太陽高度",
            axis: "太陽高度（度）",
            format: (b) => Math.round(b * 10) / 10,
        },
    ];
    const actions = [
        { key: "open", canvas: "Open", icon: "☀️", name: "開", color: METRICS_COLOR.open },
        { key: "close", canvas: "Close", icon: "🌙", name: "閉", color: METRICS_COLOR.close },
    ];
    // 自動は開/閉で y 軸最大値を共有、手動は固定 100%
    const groups = [
        { prefix: "auto", icon: "🤖", name: "自動", data: chartData.auto_sensor_data, sharedMax: true },
        { prefix: "manual", icon: "👆", name: "手動", data: chartData.manual_sensor_data, sharedMax: false },
    ];

    for (const group of groups) {
        if (!group.data) continue;
        for (const sensor of sensors) {
            const hists = {};
            for (const action of actions) {
                hists[action.key] = calcHistPercent(group.data[action.key + "_" + sensor.key] || []);
            }
            let yMax = 100;
            if (group.sharedMax) {
                const maxPercent = Math.max(hists.open.maxPercent, hists.close.maxPercent, 10);
                yMax = Math.ceil(maxPercent / 10) * 10;
            }
            for (const action of actions) {
                const hist = hists[action.key];
                const ctx = document.getElementById(group.prefix + action.canvas + sensor.canvas + "Chart");
                if (!ctx || hist.bins.length === 0) continue;
                new Chart(ctx, {
                    type: "bar",
                    data: {
                        labels: hist.bins.slice(0, -1).map(sensor.format),
                        datasets: [
                            {
                                label:
                                    group.icon +
                                    action.icon +
                                    " " +
                                    group.name +
                                    action.name +
                                    "操作時" +
                                    sensor.title +
                                    "頻度",
                                data: hist.histPercent,
                                backgroundColor: action.color.bg,
                                borderColor: action.color.border,
                                borderWidth: 1,
                            },
                        ],
                    },
                    options: percentBarOptions(sensor.axis, yMax),
                });
            }
        }
    }
}

// 手動操作データの有無に応じて表示を切り替え
function toggleManualSensorSection(chartData) {
    const manualData = chartData.manual_sensor_data;
    const hasManualData =
        manualData &&
        [
            "open_lux",
            "close_lux",
            "open_solar_rad",
            "close_solar_rad",
            "open_altitude",
            "close_altitude",
        ].some((key) => manualData[key] && manualData[key].length > 0);

    const noDataDiv = document.getElementById("manual-no-data");
    const chartsDiv = document.getElementById("manual-charts");
    if (noDataDiv) noDataDiv.classList.toggle("hidden", Boolean(hasManualData));
    if (chartsDiv) chartsDiv.classList.toggle("hidden", !hasManualData);
    return Boolean(hasManualData);
}

// 見合わせチャート（理由×方向、日別件数の 2 個）
function generatePostponeCharts(postponeChart, reasonLabels) {
    const postpone = postponeChart || {};
    const labels = reasonLabels || {};

    const reasonCtx = document.getElementById("postponeReasonChart");
    if (reasonCtx) {
        const matrix = postpone.reason_action_matrix || {};
        const reasons = Object.keys(matrix);
        new Chart(reasonCtx, {
            type: "bar",
            data: {
                labels: reasons.map((reason) => labels[reason] || reason),
                datasets: [
                    {
                        label: "☀️ 開け",
                        data: reasons.map((reason) => matrix[reason].open || 0),
                        backgroundColor: METRICS_COLOR.postponeOpen.bg,
                        borderColor: METRICS_COLOR.postponeOpen.border,
                        borderWidth: 1,
                    },
                    {
                        label: "🌙 閉め",
                        data: reasons.map((reason) => matrix[reason].close || 0),
                        backgroundColor: METRICS_COLOR.postponeClose.bg,
                        borderColor: METRICS_COLOR.postponeClose.border,
                        borderWidth: 1,
                    },
                ],
            },
            options: countBarOptions(null, true),
        });
    }

    const dailyCtx = document.getElementById("postponeDailyChart");
    if (dailyCtx) {
        new Chart(dailyCtx, {
            type: "bar",
            data: {
                labels: postpone.daily_labels || [],
                datasets: [
                    {
                        label: "☀️ 開け",
                        data: postpone.daily_open || [],
                        backgroundColor: METRICS_COLOR.postponeOpen.bg,
                    },
                    {
                        label: "🌙 閉め",
                        data: postpone.daily_close || [],
                        backgroundColor: METRICS_COLOR.postponeClose.bg,
                    },
                ],
            },
            options: countBarOptions(null, true),
        });
    }
}

function minutesToHHMM(minutes) {
    const h = Math.floor(minutes / 60);
    const m = Math.floor(minutes % 60);
    return ("0" + h).slice(-2) + ":" + ("0" + m).slice(-2);
}

// センサー日内推移（context 別色分け散布図 + 閾値線）
function renderSensorProfile(canvasId, seriesByContext, thresholds, yLabel) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    const datasets = [];
    for (const [context, style] of Object.entries(SENSOR_CONTEXT_STYLE)) {
        const points = (seriesByContext || {})[context] || [];
        if (points.length === 0) continue;
        datasets.push({
            label: style.label,
            data: points,
            backgroundColor: style.bg,
            borderColor: style.border,
            pointRadius: 1.5,
            showLine: false,
        });
    }
    if (thresholds && thresholds.open !== null && thresholds.open !== undefined) {
        datasets.push({
            type: "line",
            label: "開け閾値",
            data: [
                { x: 0, y: thresholds.open },
                { x: 1440, y: thresholds.open },
            ],
            borderColor: "rgba(220, 38, 38, 0.7)",
            borderWidth: 2,
            borderDash: [4, 4],
            pointRadius: 0,
            fill: false,
        });
    }
    if (thresholds && thresholds.close !== null && thresholds.close !== undefined) {
        datasets.push({
            type: "line",
            label: "閉め閾値",
            data: [
                { x: 0, y: thresholds.close },
                { x: 1440, y: thresholds.close },
            ],
            borderColor: "rgba(37, 99, 235, 0.7)",
            borderWidth: 2,
            borderDash: [4, 4],
            pointRadius: 0,
            fill: false,
        });
    }

    new Chart(ctx, {
        type: "scatter",
        data: { datasets: datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    type: "linear",
                    min: 0,
                    max: 1440,
                    ticks: {
                        stepSize: 120,
                        callback: function (value) {
                            return minutesToHHMM(value);
                        },
                    },
                    title: { display: true, text: "時刻" },
                },
                y: {
                    beginAtZero: true,
                    title: { display: true, text: yLabel },
                },
            },
        },
    });
}

function generateSensorProfileCharts(sensorSamples) {
    const data = sensorSamples || {};
    const series = data.series || {};
    const thresholds = data.thresholds || {};
    renderSensorProfile("sensorProfileLuxChart", series.lux, thresholds.lux, "照度 (lux)");
    renderSensorProfile("sensorProfileSolarChart", series.solar_rad, thresholds.solar_rad, "日射 (W/m²)");
    renderSensorProfile("sensorProfileAltitudeChart", series.altitude, thresholds.altitude, "太陽高度 (°)");
}

// 閾値マージンヒストグラム（照度・日射・太陽高度の 3 個）
function renderMargin(canvasId, thresholdMargin, sensor, xLabel) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    const margin = thresholdMargin || {};
    const openMargins = (margin.open || [])
        .map((e) => e[sensor])
        .filter((v) => v !== null && v !== undefined);
    const closeMargins = (margin.close || [])
        .map((e) => e[sensor])
        .filter((v) => v !== null && v !== undefined);
    if (openMargins.length === 0 && closeMargins.length === 0) {
        ctx.getContext("2d").fillText("データがありません", 20, 40);
        return;
    }

    const all = openMargins.concat(closeMargins);
    const minV = Math.min(...all, 0);
    const maxV = Math.max(...all, 0);
    const span = maxV - minV || 1;
    const binCount = 20;
    const bins = Array.from({ length: binCount + 1 }, (_, i) => minV + (span * i) / binCount);

    new Chart(ctx, {
        type: "bar",
        data: {
            labels: bins.slice(0, -1).map((b) => b.toFixed(1)),
            datasets: [
                {
                    label: "☀️ 開け操作",
                    data: createHistogram(openMargins, bins),
                    backgroundColor: METRICS_COLOR.postponeOpen.bg,
                },
                {
                    label: "🌙 閉め操作",
                    data: createHistogram(closeMargins, bins),
                    backgroundColor: METRICS_COLOR.postponeClose.bg,
                },
            ],
        },
        options: countBarOptions(xLabel, false),
    });
}

function generateThresholdMarginCharts(thresholdMargin) {
    renderMargin("thresholdMarginLuxChart", thresholdMargin, "lux", "lux マージン");
    renderMargin("thresholdMarginSolarChart", thresholdMargin, "solar_rad", "solar_rad マージン (W/m²)");
    renderMargin("thresholdMarginAltitudeChart", thresholdMargin, "altitude", "altitude マージン (°)");
}

// 制御失敗の推移（日別棒グラフ）
function generateFailureTimeSeriesChart(failureTimeSeries) {
    const ctx = document.getElementById("failureTimeSeriesChart");
    if (!ctx) return;
    const data = failureTimeSeries || {};
    new Chart(ctx, {
        type: "bar",
        data: {
            labels: data.dates || [],
            datasets: [
                {
                    label: "制御失敗件数",
                    data: data.counts || [],
                    backgroundColor: METRICS_COLOR.failure.bg,
                    borderColor: METRICS_COLOR.failure.border,
                    borderWidth: 1,
                },
            ],
        },
        options: countBarOptions("日付", false),
    });
}

// 閾値チューニング支援（不足量 ×2、what-if、解消ラグの 4 個）
function generateThresholdTuningCharts(thresholdTuning) {
    const tuning = thresholdTuning || {};
    const shortfall = tuning.shortfall || {};

    renderSimpleHistogram(
        "tuningShortfallLuxChart",
        shortfall.lux || [],
        "閾値までの不足量",
        "lux 不足量",
        METRICS_COLOR.postponeOpen,
        (b) => Math.round(b).toLocaleString()
    );
    renderSimpleHistogram(
        "tuningShortfallSolarChart",
        shortfall.solar_rad || [],
        "閾値までの不足量",
        "solar_rad 不足量 (W/m²)",
        METRICS_COLOR.postponeOpen,
        (b) => Math.round(b).toLocaleString()
    );

    const whatIfCtx = document.getElementById("tuningWhatIfChart");
    const whatIf = tuning.what_if || [];
    if (whatIfCtx && whatIf.length > 0) {
        new Chart(whatIfCtx, {
            type: "bar",
            data: {
                labels: whatIf.map((entry) => "×" + entry.scale.toFixed(1)),
                datasets: [
                    {
                        label: "即時開けられた率",
                        data: whatIf.map((entry) => entry.ratio * 100),
                        backgroundColor: METRICS_COLOR.whatIf.bg,
                        borderColor: METRICS_COLOR.whatIf.border,
                        borderWidth: 1,
                    },
                ],
            },
            options: percentBarOptions("閾値スケール", 100),
        });
    }

    renderSimpleHistogram(
        "tuningResolveLagChart",
        tuning.resolve_lag_minutes || [],
        "解消までの時間",
        "解消までの時間（分）",
        METRICS_COLOR.whatIf,
        (b) => Math.round(b)
    );
}

// 全チャートの描画エントリポイント
function renderAllCharts(data) {
    // 凡例を正方形に設定
    Chart.defaults.plugins.legend.labels.boxWidth = 12;
    Chart.defaults.plugins.legend.labels.boxHeight = 12;

    const chartData = data.charts || {};

    generateTimeCharts(chartData);
    generateTimeSeriesCharts(chartData);
    const hasManualData = toggleManualSensorSection(chartData);
    generateSensorHistogramCharts({
        auto_sensor_data: chartData.auto_sensor_data,
        manual_sensor_data: hasManualData ? chartData.manual_sensor_data : null,
    });
    generatePostponeCharts((data.postpone || {}).chart, data.reason_labels);
    generateSensorProfileCharts(chartData.sensor_samples);
    generateThresholdMarginCharts(chartData.threshold_margin);
    generateFailureTimeSeriesChart(chartData.failure_time_series);
    generateThresholdTuningCharts(data.threshold_tuning);
}
