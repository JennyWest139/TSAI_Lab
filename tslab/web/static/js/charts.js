/**
 * Interaktive Plotly-Grafiken (Originalwerte + Trend, optional Renditen).
 */
const TSLabCharts = (() => {
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
      margin: { l: 56, r: data.returns ? 56 : 24, t: 32, b: 48 },
      title: { text: data.label, font: { size: 15 } },
      xaxis: { ...plotTheme().xaxis, title: "Datum" },
      yaxis: { ...plotTheme().yaxis, title: "Originalwert" },
      legend: { orientation: "h", y: 1.12, x: 0 },
      hovermode: "x unified",
    };

    if (data.returns?.dates?.length) {
      layout.yaxis2 = {
        ...plotTheme().yaxis,
        title: "Renditen",
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
        name: `${a.label} (Original)`,
        mode: "lines",
        line: { color: "#1f6feb", width: 1.8 },
        yaxis: "y",
        hovertemplate: hoverTemplate(a.label, "Wert"),
      },
      {
        x: a.dates,
        y: a.trend,
        name: `${a.label} (Trend)`,
        mode: "lines",
        line: { color: "#8db4e2", width: 1.6, dash: "dash" },
        yaxis: "y",
        hovertemplate: hoverTemplate(`${a.label} Trend`, "Trend"),
      },
      {
        x: b.dates,
        y: b.values,
        name: `${b.label} (Original)`,
        mode: "lines",
        line: { color: "#c55a11", width: 1.8 },
        yaxis: "y2",
        hovertemplate: hoverTemplate(b.label, "Wert"),
      },
      {
        x: b.dates,
        y: b.trend,
        name: `${b.label} (Trend)`,
        mode: "lines",
        line: { color: "#f0a88a", width: 1.6, dash: "dash" },
        yaxis: "y2",
        hovertemplate: hoverTemplate(`${b.label} Trend`, "Trend"),
      },
    ];

    const layout = {
      ...plotTheme(),
      margin: { l: 60, r: 60, t: 40, b: 56 },
      title: {
        text: `Zeitreihen-Vorschau · ${data.window?.start || ""} … ${data.window?.end || ""}`,
        font: { size: 14 },
      },
      xaxis: { ...plotTheme().xaxis, title: "Datum" },
      yaxis: {
        ...plotTheme().yaxis,
        title: a.label,
        titlefont: { color: "#1f6feb" },
        tickfont: { color: "#1f6feb" },
      },
      yaxis2: {
        ...plotTheme().yaxis,
        title: b.label,
        overlaying: "y",
        side: "right",
        titlefont: { color: "#c55a11" },
        tickfont: { color: "#c55a11" },
        showgrid: false,
      },
      legend: { orientation: "h", y: 1.18, x: 0, font: { size: 10 } },
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
        name: `${data.series_a.label} · ${data.returns_a.label}`,
        mode: "lines",
        line: { color: "#10b981", width: 1.5 },
        hovertemplate: hoverTemplate(data.series_a.label, "Rendite"),
      },
    ];
    if (data.returns_b?.dates?.length) {
      traces.push({
        x: data.returns_b.dates,
        y: data.returns_b.values,
        name: `${data.series_b.label} · ${data.returns_b.label}`,
        mode: "lines",
        line: { color: "#059669", width: 1.5, dash: "dot" },
        hovertemplate: hoverTemplate(data.series_b.label, "Rendite"),
      });
    }

    const layout = {
      ...plotTheme(),
      margin: { l: 56, r: 24, t: 28, b: 48 },
      title: { text: "Kontinuierliche Renditen (Zusatz)", font: { size: 13 } },
      xaxis: { ...plotTheme().xaxis, title: "Datum" },
      yaxis: { ...plotTheme().yaxis, title: "Rendite" },
      legend: { orientation: "h", y: 1.15, x: 0 },
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
    renderSeriesChart,
    renderPairChart,
    renderReturnsPairChart,
    initSeriesDetail,
    loadSeriesChart,
  };
})();
