/**
 * Interaktive Plotly-Grafiken (Originalwerte + Trend, optional Renditen).
 */
const TSLabCharts = (() => {
  function wrapPlotlyText(text, maxLen = 42) {
    if (!text) return "";
    const words = String(text).split(/\s+/);
    const lines = [];
    let line = "";
    for (const word of words) {
      const next = line ? `${line} ${word}` : word;
      if (next.length > maxLen && line) {
        lines.push(line);
        line = word;
      } else {
        line = next;
      }
    }
    if (line) lines.push(line);
    return lines.join("<br>");
  }

  function plotTheme() {
    const dark = document.documentElement.getAttribute("data-theme") === "dark";
    return {
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      font: { color: dark ? "#e6edf3" : "#1a2332", family: "DM Sans, system-ui, sans-serif" },
      xaxis: { gridcolor: dark ? "#30363d" : "#dde3ec", zerolinecolor: dark ? "#484f58" : "#c8d4e6" },
      yaxis: { gridcolor: dark ? "#30363d" : "#dde3ec", zerolinecolor: dark ? "#484f58" : "#c8d4e6" },
    };
  }

  function hoverTemplate(label, valueLabel) {
    return `<b>%{x|%b %Y}</b><br>${label}: %{y:.4f}<extra></extra>`;
  }

  function legendY(traceCount) {
    if (traceCount <= 2) return 1.1;
    if (traceCount <= 4) return 1.16;
    return 1.22;
  }

  function renderSeriesChart(containerId, data) {
    const el = document.getElementById(containerId);
    if (!el || !window.Plotly) return;

    const traces = [
      {
        x: data.dates,
        y: data.values,
        name: "Originalwert",
        mode: "lines",
        line: { color: "#1f6feb", width: 2 },
        hovertemplate: hoverTemplate(data.label, data.value_label || "Wert"),
      },
      {
        x: data.dates,
        y: data.trend,
        name: "Trendkomponente",
        mode: "lines",
        line: { color: "#c55a11", width: 2, dash: "dash" },
        hovertemplate: hoverTemplate("Trend", "Trend"),
      },
    ];

    if (data.returns?.dates?.length) {
      traces.push({
        x: data.returns.dates,
        y: data.returns.values,
        name: data.returns.label || "Renditen",
        mode: "lines",
        line: { color: "#10b981", width: 1.5 },
        yaxis: "y2",
        hovertemplate: hoverTemplate(data.returns.label, "Rendite"),
      });
    }

    const layout = {
      ...plotTheme(),
      margin: { l: 56, r: data.returns ? 56 : 24, t: 48, b: 48 },
      title: { text: wrapPlotlyText(data.label, 50), font: { size: 15 } },
      xaxis: { ...plotTheme().xaxis, title: "Datum" },
      yaxis: { ...plotTheme().yaxis, title: wrapPlotlyText("Originalwert", 24) },
      legend: { orientation: "h", y: legendY(traces.length), x: 0 },
      hovermode: "x unified",
    };

    if (data.returns?.dates?.length) {
      layout.yaxis2 = {
        ...plotTheme().yaxis,
        title: wrapPlotlyText("Renditen", 24),
        overlaying: "y",
        side: "right",
        showgrid: false,
      };
    }

    Plotly.react(el, traces, layout, { responsive: true, displayModeBar: true });
  }

  function renderPairChart(containerId, data) {
    const el = document.getElementById(containerId);
    if (!el || !window.Plotly) return;

    const a = data.series_a;
    const b = data.series_b;
    const traces = [
      {
        x: a.dates,
        y: a.values,
        name: wrapPlotlyText(`${a.label} (Original)`, 36),
        mode: "lines",
        line: { color: "#1f6feb", width: 1.8 },
        yaxis: "y",
        hovertemplate: hoverTemplate(a.label, "Wert"),
      },
      {
        x: a.dates,
        y: a.trend,
        name: wrapPlotlyText(`${a.label} (Trend)`, 36),
        mode: "lines",
        line: { color: "#8db4e2", width: 1.6, dash: "dash" },
        yaxis: "y",
        hovertemplate: hoverTemplate(`${a.label} Trend`, "Trend"),
      },
      {
        x: b.dates,
        y: b.values,
        name: wrapPlotlyText(`${b.label} (Original)`, 36),
        mode: "lines",
        line: { color: "#c55a11", width: 1.8 },
        yaxis: "y2",
        hovertemplate: hoverTemplate(b.label, "Wert"),
      },
      {
        x: b.dates,
        y: b.trend,
        name: wrapPlotlyText(`${b.label} (Trend)`, 36),
        mode: "lines",
        line: { color: "#f0a88a", width: 1.6, dash: "dash" },
        yaxis: "y2",
        hovertemplate: hoverTemplate(`${b.label} Trend`, "Trend"),
      },
    ];

    const layout = {
      ...plotTheme(),
      margin: { l: 60, r: 60, t: 56, b: 56 },
      title: {
        text: wrapPlotlyText(
          `Zeitreihen-Vorschau · ${data.window?.start || ""} … ${data.window?.end || ""}`,
          52
        ),
        font: { size: 14 },
      },
      xaxis: { ...plotTheme().xaxis, title: "Datum" },
      yaxis: {
        ...plotTheme().yaxis,
        title: wrapPlotlyText(a.label, 22),
        titlefont: { color: "#1f6feb" },
        tickfont: { color: "#1f6feb" },
      },
      yaxis2: {
        ...plotTheme().yaxis,
        title: wrapPlotlyText(b.label, 22),
        overlaying: "y",
        side: "right",
        titlefont: { color: "#c55a11" },
        tickfont: { color: "#c55a11" },
        showgrid: false,
      },
      legend: { orientation: "h", y: legendY(traces.length), x: 0, font: { size: 10 } },
      hovermode: "x unified",
    };

    Plotly.react(el, traces, layout, { responsive: true, displayModeBar: true });
  }

  function renderReturnsPairChart(containerId, data) {
    const el = document.getElementById(containerId);
    if (!el || !window.Plotly || !data.returns_a?.dates?.length) return;

    const traces = [
      {
        x: data.returns_a.dates,
        y: data.returns_a.values,
        name: wrapPlotlyText(`${data.series_a.label} · ${data.returns_a.label}`, 40),
        mode: "lines",
        line: { color: "#10b981", width: 1.5 },
        hovertemplate: hoverTemplate(data.series_a.label, "Rendite"),
      },
    ];
    if (data.returns_b?.dates?.length) {
      traces.push({
        x: data.returns_b.dates,
        y: data.returns_b.values,
        name: wrapPlotlyText(`${data.series_b.label} · ${data.returns_b.label}`, 40),
        mode: "lines",
        line: { color: "#059669", width: 1.5, dash: "dot" },
        hovertemplate: hoverTemplate(data.series_b.label, "Rendite"),
      });
    }

    const layout = {
      ...plotTheme(),
      margin: { l: 56, r: 24, t: 40, b: 48 },
      title: { text: wrapPlotlyText("Kontinuierliche Renditen (Zusatz)", 48), font: { size: 13 } },
      xaxis: { ...plotTheme().xaxis, title: "Datum" },
      yaxis: { ...plotTheme().yaxis, title: "Rendite" },
      legend: { orientation: "h", y: legendY(traces.length), x: 0 },
      hovermode: "x unified",
    };

    Plotly.react(el, traces, layout, { responsive: true, displayModeBar: true });
  }

  async function loadSeriesChart(slug, { showReturns = false } = {}) {
    const params = new URLSearchParams();
    if (showReturns) params.set("show_returns", "1");
    const res = await fetch(`/api/series/${encodeURIComponent(slug)}/chart?${params}`);
    if (!res.ok) throw new Error("Grafikdaten nicht verfügbar");
    return res.json();
  }

  function initSeriesDetail(slug) {
    const showReturnsEl = document.getElementById("showReturns");
    const footnote = document.getElementById("trendNote");
    const returnsHint = document.getElementById("returnsHint");

    async function refresh() {
      try {
        const data = await loadSeriesChart(slug, {
          showReturns: showReturnsEl?.checked,
        });
        renderSeriesChart("seriesChart", data);
        if (footnote) footnote.textContent = data.trend_note || "";
        if (returnsHint) {
          returnsHint.textContent = data.returns_recommended
            ? "Bei Kursindizes sind kontinuierliche Renditen als Zusatz sinnvoll."
            : "Für diese Reihe sind Renditen kein Standard — nur optional per Checkbox.";
        }
      } catch (err) {
        if (footnote) footnote.textContent = err.message || "Fehler beim Laden";
      }
    }

    showReturnsEl?.addEventListener("change", refresh);
    document.getElementById("themeToggle")?.addEventListener("click", () => {
      setTimeout(refresh, 50);
    });
    refresh();
  }

  return {
    wrapPlotlyText,
    renderSeriesChart,
    renderPairChart,
    renderReturnsPairChart,
    initSeriesDetail,
    loadSeriesChart,
  };
})();
