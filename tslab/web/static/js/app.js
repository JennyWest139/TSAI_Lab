/**
 * TSLab Dashboard — Theme, Navigation, Workflows (Design v1 + unabhängige Von/Bis-Daten)
 */
const TSLab = (() => {
  const STORAGE_THEME = "tslab-theme";
  let askRateLimit = null;

  function initCore() {
    const saved = localStorage.getItem(STORAGE_THEME) || "light";
    document.documentElement.setAttribute("data-theme", saved);

    document.getElementById("themeToggle")?.addEventListener("click", () => {
      const next =
        document.documentElement.getAttribute("data-theme") === "dark"
          ? "light"
          : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem(STORAGE_THEME, next);
    });

    document.getElementById("menuToggle")?.addEventListener("click", () => {
      document.getElementById("sidebar")?.classList.toggle("open");
    });

    document.querySelectorAll(".nav-link").forEach((link) => {
      link.addEventListener("click", () => {
        document.getElementById("sidebar")?.classList.remove("open");
      });
    });

    initDeleteModal();
    initTagShuttle();
    askRateLimit = initRateLimitModal();
  }

  function initDeleteModal() {
    const modal = document.getElementById("deleteModal");
    if (!modal) return;
    const form = document.getElementById("deleteForm");
    const summary = document.getElementById("deleteSummary");
    const confirmBtn = document.getElementById("deleteConfirmBtn");
    let pending = null;

    document.querySelectorAll("[data-delete-trigger]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        pending = {
          entity_type: btn.dataset.entityType,
          id: btn.dataset.entityId,
          slug: btn.dataset.entitySlug,
          scope: btn.dataset.deleteScope || "both",
        };
        const body = {
          entity_type: pending.entity_type,
          scope: pending.scope,
        };
        if (pending.slug) body.slug = pending.slug;
        else body.id = pending.id;
        const res = await fetch("/api/delete/preview", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const data = await res.json();
        if (!data.ok) {
          toast(data.message || "Vorschau fehlgeschlagen");
          return;
        }
        const p = data.preview;
        if (summary) {
          summary.innerHTML = `
            <p><strong>${p.label}</strong></p>
            <p>Tags: ${(p.tags || []).join(", ") || "—"}</p>
            <ul>${(p.actions || []).map((a) => `<li>${a}</li>`).join("")}</ul>
            ${(p.warnings || []).map((w) => `<p class="hint">${w}</p>`).join("")}
            ${p.blocked ? `<p class="field-error">${p.block_reason}</p>` : ""}
          `;
        }
        if (confirmBtn) confirmBtn.disabled = !!p.blocked;
        modal.hidden = false;
      });
    });

    modal.querySelectorAll("[data-delete-cancel]").forEach((el) => {
      el.addEventListener("click", () => {
        modal.hidden = true;
      });
    });

    form?.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!pending) return;
      const scope = form.querySelector('input[name="delete_scope"]:checked')?.value || pending.scope;
      const body = { entity_type: pending.entity_type, scope };
      if (pending.slug) body.slug = pending.slug;
      else body.id = pending.id;
      const res = await fetch("/api/delete/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      toast(data.ok ? data.message : data.message || "Fehler");
      if (data.ok) window.location.reload();
    });
  }

  function toast(message) {
    const box = document.getElementById("toastContainer");
    if (!box) return;
    const el = document.createElement("div");
    el.className = "toast";
    el.textContent = message;
    box.appendChild(el);
    setTimeout(() => el.remove(), 4000);
  }

  function formatRunResult(data) {
    if (!data.ok) {
      return `<strong>${data.message || "Fehler"}</strong>`;
    }
    let html = `<strong>${data.message}</strong>`;
    const browse = data.job?.browse_url;
    if (browse) {
      html += ` <a href="${browse}" class="stat-link">Output-Ordner</a>`;
    }
    const reps = data.reports || (data.report ? [data.report] : []);
    for (const rep of reps) {
      if (rep?.ok && rep.report_url) {
        const label = rep.target && rep.target !== "." ? rep.target : "Bericht";
        html += ` <a href="${rep.report_url}" class="stat-link">${label} (.docx)</a>`;
        if (rep.report_pdf_url) {
          html += ` <a href="${rep.report_pdf_url}" class="stat-link">${label} (PDF)</a>`;
        }
      }
    }
    const single = data.report;
    if (!reps.length && single?.ok && single.report_url) {
      html += ` <a href="${single.report_url}" class="stat-link">Word-Bericht (.docx)</a>`;
      if (single.report_pdf_url) {
        html += ` <a href="${single.report_pdf_url}" class="stat-link">KI-Bericht (PDF)</a>`;
      }
    }
    const allErrors = reps.flatMap((r) => r?.ai_errors || []);
    if (allErrors.length) {
      html += ` <span class="hint"> · KI: ${allErrors.length} Fehler (Details im .docx)</span>`;
    } else if (single?.ai_errors?.length) {
      html += ` <span class="hint"> · KI: ${single.ai_errors.length} Fehler (Details im .docx)</span>`;
    }
    if (data.rate_limit_pause_count) {
      html += ` <span class="hint"> · ${data.rate_limit_pause_count}× 1-Min.-Pause</span>`;
    }
    const runRep = data.run_report;
    if (runRep?.ok && runRep.url) {
      html += ` <a href="${runRep.url}" class="stat-link">Laufbericht (PDF)</a>`;
    }
    return html;
  }

  function initRateLimitModal() {
    const modal = document.getElementById("rateLimitModal");
    const msgEl = document.getElementById("rateLimitMessage");
    const countdownEl = document.getElementById("rateLimitCountdown");
    const pauseBtn = document.getElementById("rateLimitPauseBtn");
    const finishBtn = document.getElementById("rateLimitFinishBtn");
    let resolveChoice = null;
    let countdownTimer = null;

    function hide() {
      modal.hidden = true;
      if (countdownTimer) {
        clearInterval(countdownTimer);
        countdownTimer = null;
      }
    }

    pauseBtn?.addEventListener("click", () => {
      hide();
      resolveChoice?.("pause");
      resolveChoice = null;
    });
    finishBtn?.addEventListener("click", () => {
      hide();
      resolveChoice?.("finish");
      resolveChoice = null;
    });

    return function askRateLimit(stepResult) {
      return new Promise((resolve) => {
        resolveChoice = resolve;
        if (msgEl) {
          msgEl.textContent = stepResult.message || "Nach 5 KI-Anfragen Pause empfohlen.";
        }
        const seconds = stepResult.pause_seconds || 60;
        let left = seconds;
        if (countdownEl) {
          countdownEl.textContent = `Empfohlene Wartezeit: ${left} Sekunden`;
        }
        modal.hidden = false;
        countdownTimer = setInterval(() => {
          left -= 1;
          if (countdownEl) {
            countdownEl.textContent =
              left > 0
                ? `Empfohlene Wartezeit: ${left} Sekunden`
                : "Pause kann jetzt fortgesetzt werden.";
          }
          if (left <= 0 && countdownTimer) {
            clearInterval(countdownTimer);
            countdownTimer = null;
          }
        }, 1000);
      });
    };
  }

  async function runDeferredAiReports(runData) {
    const outputDir = runData.job?.output_dir;
    const modelId = runData.report_model;
    if (!outputDir || !modelId) return runData;

    const runType = runData.run_type_label || "Analyse";

    const prep = await fetch("/api/report/session/prepare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        output_dir: outputDir,
        report_model: modelId,
        run_type: runType,
        analysis_mode: analysisMode,
      }),
    });
    const prepData = await prep.json();
    if (!prepData.ok) {
      runData.report = prepData;
      runData.message += ` · KI-Bericht: ${prepData.message}`;
      return runData;
    }

    toast("KI-Berichte werden erstellt …");
    let reportResult = null;

    while (true) {
      const stepRes = await fetch("/api/report/session/step", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ output_dir: outputDir }),
      });
      const stepData = await stepRes.json();
      if (stepData.status === "awaiting_user") {
        const choice = askRateLimit
          ? await askRateLimit(stepData)
          : "pause";
        const actionRes = await fetch("/api/report/session/step", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ output_dir: outputDir, action: choice }),
        });
        const actionData = await actionRes.json();
        if (actionData.status === "done") {
          reportResult = actionData;
          break;
        }
        if (actionData.status === "awaiting_user") {
          continue;
        }
        if (!actionData.ok) {
          reportResult = actionData;
          break;
        }
        continue;
      }
      if (stepData.status === "done") {
        reportResult = stepData;
        break;
      }
      if (!stepData.ok) {
        reportResult = stepData;
        break;
      }
    }

    if (reportResult) {
      runData.reports = reportResult.reports;
      runData.report = reportResult.report || reportResult.reports?.[0];
      runData.rate_limit_pause_count = reportResult.rate_limit_pause_count;
      if (reportResult.ok) {
        runData.message += ` · ${reportResult.message}`;
        if (reportResult.ai_errors?.length) {
          runData.message += ` ⚠ ${reportResult.ai_errors.length} KI-Fehler`;
        }
      }
    }

    const fin = await fetch("/api/run/finalize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ output_dir: outputDir, report_result: reportResult }),
    });
    const finData = await fin.json();
    if (finData.ok && finData.run_report) {
      runData.run_report = finData.run_report;
      runData.message += ` · ${finData.run_report.message || "Laufbericht"}`;
    }
    return runData;
  }

  function parseDate(iso) {
    return new Date(iso + "T12:00:00");
  }

  function positionBar(bar, startIso, endIso, globalStart, globalEnd) {
    if (!bar || !startIso || !endIso) return;
    const total = globalEnd - globalStart || 1;
    const left = ((parseDate(startIso) - globalStart) / total) * 100;
    const width = ((parseDate(endIso) - parseDate(startIso)) / total) * 100;
    bar.style.left = `${Math.max(0, left)}%`;
    bar.style.width = `${Math.max(2, width)}%`;
  }

  function debounce(fn, ms = 250) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), ms);
    };
  }

  function createChartModal() {
    const modal = document.getElementById("chartModal");
    if (!modal) return null;
    const titleEl = document.getElementById("chartModalTitle");
    const body = document.getElementById("chartModalBody");
    modal.querySelectorAll("[data-chart-close]").forEach((el) => {
      el.addEventListener("click", () => {
        modal.hidden = true;
        if (body) body.innerHTML = "";
      });
    });
    return {
      open(title, renderFn) {
        if (titleEl) titleEl.textContent = title;
        if (body) {
          body.innerHTML =
            '<div id="chartModalPlot" class="plotly-chart" style="min-height:420px"></div><p class="hint chart-footnote" id="chartModalNote"></p>';
          modal.hidden = false;
          renderFn("chartModalPlot", "chartModalNote");
        }
      },
    };
  }

  const chartModal = createChartModal();

  function snapToValidDate(iso, dates) {
    if (!iso || !dates?.length) return iso;
    if (dates.includes(iso)) return iso;
    for (const d of dates) {
      if (d >= iso) return d;
    }
    return dates[dates.length - 1];
  }

  function fillDateSelect(selectEl, dates, selected, fallback = "first") {
    if (!selectEl) return;
    selectEl.innerHTML = "";
    dates.forEach((d) => {
      const opt = document.createElement("option");
      opt.value = d;
      opt.textContent = d;
      selectEl.appendChild(opt);
    });
    if (selected && dates.includes(selected)) {
      selectEl.value = selected;
    } else if (dates.length) {
      selectEl.value = fallback === "last" ? dates[dates.length - 1] : dates[0];
    }
  }

  /**
   * Datumsfelder (type=date) — gültige Werte nur aus dates[] (im Speicher, nicht als Dropdown).
   */
  function bindIndependentDateInputs(vonEl, bisEl, dates, suggestedVon, suggestedBis, onChange) {
    if (!vonEl || !bisEl || !dates || dates.length < 2) return () => false;

    vonEl.min = bisEl.min = dates[0];
    vonEl.max = bisEl.max = dates[dates.length - 1];
    vonEl.value = snapToValidDate(suggestedVon || dates[0], dates);
    bisEl.value = snapToValidDate(suggestedBis || dates[dates.length - 1], dates);

    const validate = () => {
      let von = snapToValidDate(vonEl.value, dates);
      let bis = snapToValidDate(bisEl.value, dates);
      if (vonEl.value !== von) vonEl.value = von;
      if (bisEl.value !== bis) bisEl.value = bis;
      const ok = dates.includes(von) && dates.includes(bis) && von < bis;

      vonEl.classList.toggle("field-invalid", !ok);
      bisEl.classList.toggle("field-invalid", !ok);

      const errVon = document.getElementById(`${vonEl.id}Error`);
      const errBis = document.getElementById(`${bisEl.id}Error`);
      const msg = ok ? "" : "Von-Datum muss vor Bis-Datum liegen (gültige Zeitstempel).";
      if (errVon) {
        errVon.hidden = ok;
        errVon.textContent = msg;
      }
      if (errBis) {
        errBis.hidden = ok;
        errBis.textContent = msg;
      }

      onChange?.(ok, von, bis);
      return ok;
    };

    vonEl.onchange = validate;
    bisEl.onchange = validate;
    validate();
    return validate;
  }

  function bindIndependentDateRange(vonEl, bisEl, dates, suggestedVon, suggestedBis, onChange) {
    if (vonEl?.type === "date" || bisEl?.type === "date") {
      return bindIndependentDateInputs(vonEl, bisEl, dates, suggestedVon, suggestedBis, onChange);
    }
    if (!vonEl || !bisEl || !dates || dates.length < 2) return () => false;

    fillDateSelect(vonEl, dates, suggestedVon || dates[0], "first");
    fillDateSelect(bisEl, dates, suggestedBis || dates[dates.length - 1], "last");

    const validate = () => {
      const von = vonEl.value;
      const bis = bisEl.value;
      const ok =
        dates.includes(von) &&
        dates.includes(bis) &&
        von < bis;

      vonEl.classList.toggle("field-invalid", !ok);
      bisEl.classList.toggle("field-invalid", !ok);

      const errVon = document.getElementById(`${vonEl.id}Error`);
      const errBis = document.getElementById(`${bisEl.id}Error`);
      const msg = ok ? "" : "Von-Datum muss vor Bis-Datum liegen (gültige Zeitstempel).";
      if (errVon) {
        errVon.hidden = ok;
        errVon.textContent = msg;
      }
      if (errBis) {
        errBis.hidden = ok;
        errBis.textContent = msg;
      }

      onChange?.(ok, von, bis);
      return ok;
    };

    vonEl.onchange = validate;
    bisEl.onchange = validate;
    validate();
    return validate;
  }

  function updateWindowBar(bar, vonIso, bisIso, globalStart, globalEnd) {
    if (!bar || !vonIso || !bisIso) return;
    const ok = vonIso < bisIso;
    bar.hidden = !ok;
    if (ok) positionBar(bar, vonIso, bisIso, globalStart, globalEnd);
  }

  async function fetchOverlap(a, b, frequency) {
    const params = new URLSearchParams({ a, b });
    if (frequency) params.set("frequency", frequency);
    const res = await fetch(`/api/overlap?${params}`);
    if (!res.ok) throw new Error("Keine Überlappung");
    return res.json();
  }

  function initCorrelation() {
    const selA = document.getElementById("seriesA");
    const selB = document.getElementById("seriesB");
    const vonSelect = document.getElementById("corrStart");
    const bisSelect = document.getElementById("corrEnd");
    const freqSelect = document.getElementById("frequency");
    const modeSelect = document.getElementById("analysisMode");
    const showReturnsEl = document.getElementById("corrShowReturns");
    const previewBtn = document.getElementById("corrShowPreviewBtn");
    const form = document.getElementById("correlationForm");
    let validateDates = () => false;
    let gStart;
    let gEnd;
    let overlapDates = [];

    function filterSeriesBByA() {
      if (!selB) return;
      Array.from(selB.options).forEach((opt) => {
        if (!opt.value) return;
        opt.hidden = false;
      });
    }

    function refreshWindowBar() {
      updateWindowBar(
        document.getElementById("barWindow"),
        vonSelect?.value,
        bisSelect?.value,
        gStart,
        gEnd
      );
    }

    async function openCorrPreview() {
      const a = selA?.value;
      const b = selB?.value;
      const start = vonSelect?.value;
      const end = bisSelect?.value;
      if (!a || !b || a === b || !start || !end || start >= end) {
        toast("Bitte Reihen und gültiges Datumsfenster wählen.");
        return;
      }
      if (typeof TSLabCharts === "undefined" || !window.Plotly || !chartModal) {
        toast("Grafik nicht verfügbar.");
        return;
      }
      const t0 = performance.now();
      const params = new URLSearchParams({ a, b, start, end });
      if (showReturnsEl?.checked) params.set("show_returns", "1");
      if (modeSelect?.value) params.set("analysis_mode", modeSelect.value);
      if (freqSelect?.value) params.set("frequency", freqSelect.value);
      try {
        const res = await fetch(`/api/correlation/preview?${params}`);
        if (!res.ok) throw new Error("Vorschau nicht verfügbar");
        const data = await res.json();
        console.info(`[tslab] correlation preview ${(performance.now() - t0).toFixed(0)} ms`);
        chartModal.open("Zeitreihen-Vorschau", (plotId, noteId) => {
          TSLabCharts.renderPairChart(plotId, data);
          const note = document.getElementById(noteId);
          if (note) {
            note.textContent = `${data.series_a.trend_note} · ${data.series_b.trend_note}`;
          }
        });
      } catch {
        toast("Vorschau konnte nicht geladen werden.");
      }
    }

    function renderOverlap(data) {
      const viz = document.getElementById("overlapViz");
      const ph = document.getElementById("overlapPlaceholder");
      if (!viz || !ph) return;

      ph.hidden = true;
      viz.hidden = false;

      gStart = parseDate(
        data.series_a.first_date < data.series_b.first_date
          ? data.series_a.first_date
          : data.series_b.first_date
      );
      gEnd = parseDate(
        data.series_a.last_date > data.series_b.last_date
          ? data.series_a.last_date
          : data.series_b.last_date
      );

      positionBar(document.getElementById("barA"), data.series_a.first_date, data.series_a.last_date, gStart, gEnd);
      positionBar(document.getElementById("barB"), data.series_b.first_date, data.series_b.last_date, gStart, gEnd);
      positionBar(document.getElementById("barOverlap"), data.overlap_start, data.overlap_end, gStart, gEnd);

      if (freqSelect && data.suggested_frequency) {
        freqSelect.value = data.suggested_frequency;
      }

      const dates = data.dates || [];
      validateDates = bindIndependentDateRange(
        vonSelect,
        bisSelect,
        dates,
        data.suggested_start,
        data.suggested_end,
        () => refreshWindowBar()
      );
      overlapDates = dates;

      const meta = document.getElementById("overlapMeta");
      if (meta) {
        const notes = [data.window_note, data.frequency_note].filter(Boolean).join(" ");
        meta.innerHTML = `
          <dt>Serie A</dt><dd>${data.series_a.first_date} → ${data.series_a.last_date} (${data.series_a.observation_count} n)</dd>
          <dt>Serie B</dt><dd>${data.series_b.first_date} → ${data.series_b.last_date} (${data.series_b.observation_count} n)</dd>
          <dt>Schnittmenge</dt><dd>${data.overlap_start} → ${data.overlap_end} (${data.overlap_observations} n)</dd>
          <dt>Rhythmus (Vorschlag)</dt><dd>${data.suggested_frequency_label}</dd>
          ${data.narrower_series_label ? `<dt>Eingeschränkte Reihe</dt><dd>${data.narrower_series_label}</dd>` : ""}
          ${notes ? `<dt>Hinweis</dt><dd>${notes}</dd>` : ""}
        `;
      }
      refreshWindowBar();
    }

    async function updateOverlap() {
      filterSeriesBByA();
      const a = selA?.value;
      const b = selB?.value;
      if (!a || !b || a === b) return;
      const t0 = performance.now();
      try {
        renderOverlap(await fetchOverlap(a, b, freqSelect?.value || null));
        console.info(`[tslab] overlap loaded ${(performance.now() - t0).toFixed(0)} ms`);
      } catch {
        toast("Keine gemeinsame Datenbasis für diese Paarung.");
      }
    }

    const updateOverlapDebounced = debounce(updateOverlap, 200);

    selA?.addEventListener("change", () => {
      filterSeriesBByA();
      updateOverlapDebounced();
    });
    selB?.addEventListener("change", updateOverlapDebounced);
    freqSelect?.addEventListener("change", updateOverlapDebounced);
    previewBtn?.addEventListener("click", openCorrPreview);
    filterSeriesBByA();
    updateOverlap();

    form?.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!validateDates()) {
        toast("Bitte Von-Datum und Bis-Datum prüfen (Von < Bis, nur gültige Zeitstempel).");
        return;
      }
      const payload = Object.fromEntries(new FormData(form));
      const res = await fetch("/api/correlation/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      let result = data;
      if (data.report_deferred) {
        result = await runDeferredAiReports(data);
      }
      const panel = document.getElementById("corrResult");
      if (panel) {
        panel.hidden = false;
        panel.innerHTML = formatRunResult(result);
      }
      toast(result.ok ? result.message : result.message || "Fehler");
    });
  }

  async function loadSeriesMeta(slug) {
    const res = await fetch(`/api/series/${slug}`);
    return res.json();
  }

  function initTsa() {
    const sel = document.getElementById("tsaSeries");
    const vonSelect = document.getElementById("trainStart");
    const bisSelect = document.getElementById("trainEnd");
    const forecastInput = document.getElementById("forecastEnd");
    const form = document.getElementById("tsaForm");
    const metaBox = document.getElementById("seriesMeta");
    let validateTrainDates = () => false;

    async function updateMeta() {
      const slug = sel?.value;
      if (!slug) return;
      const t0 = performance.now();
      const [metaRes, datesRes] = await Promise.all([
        fetch(`/api/series/${slug}/meta`),
        fetch(`/api/series/${slug}/dates`),
      ]);
      const s = await metaRes.json();
      const datesPayload = await datesRes.json();
      const dates = datesPayload.dates || [];
      console.info(`[tslab] series meta+dates ${(performance.now() - t0).toFixed(0)} ms (${dates.length} n)`);

      if (metaBox) {
        metaBox.innerHTML = `
          <strong>${s.label_de}</strong><br>
          Daten: <span class="mono">${s.first_date}</span> bis <span class="mono">${s.last_date}</span><br>
          Beobachtungen: ${s.observation_count} · Rhythmus: ${s.frequency_label}
        `;
      }

      const suggestedCutoff =
        dates.find((d) => d.startsWith("2006-07")) ||
        dates[Math.max(0, dates.length - 2)];

      validateTrainDates = bindIndependentDateRange(
        vonSelect,
        bisSelect,
        dates,
        s.first_date,
        suggestedCutoff,
        (ok, von, bis) => {
          if (forecastInput && ok && bis) {
            forecastInput.min = bis;
            if (!forecastInput.value || forecastInput.value < bis) {
              forecastInput.value = bis;
            }
          }
        }
      );
    }

    sel?.addEventListener("change", () => {
      updateMeta();
    });
    updateMeta();

    function syncOrderPanel() {
      const panel = document.getElementById("userOrderPanel");
      const mode = document.querySelector('input[name="order_mode"]:checked')?.value;
      if (panel) panel.hidden = mode !== "user";
    }
    document.querySelectorAll('input[name="order_mode"]').forEach((el) => {
      el.addEventListener("change", syncOrderPanel);
    });
    syncOrderPanel();

    async function openTsaWindowChart() {
      if (!chartModal || typeof TSLabCharts === "undefined" || !TSLabCharts.renderTsaWindowChart) {
        toast("Grafik nicht verfügbar.");
        return;
      }
      const t0 = performance.now();
      const fd = new FormData(form);
      const params = new URLSearchParams(fd);
      params.set("series_slug", sel?.value || "");
      params.delete("models");
      try {
        const res = await fetch(`/api/tsa/window-preview?${params}`);
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        console.info(`[tslab] tsa window preview ${(performance.now() - t0).toFixed(0)} ms`);
        chartModal.open("Prognosefenster", (plotId) => {
          TSLabCharts.renderTsaWindowChart(plotId, data);
        });
      } catch {
        toast("Fenster-Vorschau nicht verfügbar.");
      }
    }

    document.getElementById("tsaShowWindowBtn")?.addEventListener("click", openTsaWindowChart);

    form?.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!validateTrainDates()) {
        toast("Training Von-Datum muss vor Bis-Datum liegen.");
        return;
      }
      const fd = new FormData(form);
      const models = fd.getAll("models");
      if (!models.length) {
        toast("Bitte mindestens ein Modell wählen.");
        return;
      }
      const payload = Object.fromEntries(fd.entries());
      payload.models = models;
      if (payload.order_mode !== "user") {
        delete payload.arma_order;
        delete payload.garch_order;
      }
      const res = await fetch("/api/tsa/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      let result = data;
      if (data.report_deferred) {
        result = await runDeferredAiReports(data);
      }
      const panel = document.getElementById("tsaResult");
      if (panel) {
        panel.hidden = false;
        panel.innerHTML = formatRunResult(result);
      }
      toast(result.ok ? result.message : result.message || "Fehler");
    });
  }

  function initUpload() {
    const drop = document.getElementById("uploadDrop");
    const input = document.getElementById("fileInput");
    const wizard = document.getElementById("uploadWizard");
    const preview = document.getElementById("filePreview");
    const fileMeta = document.getElementById("fileMeta");
    const dateCol = document.getElementById("dateColumn");
    const dateMode = document.getElementById("dateParseMode");
    const decimalMode = document.getElementById("decimalMode");
    const dateFormatInput = document.getElementById("uploadDateFormat");
    const encodingInput = document.getElementById("uploadEncoding");
    const dateDetectMeta = document.getElementById("dateDetectMeta");
    const decimalDetectMeta = document.getElementById("decimalDetectMeta");
    const decimalSampleWrap = document.getElementById("decimalSampleWrap");
    const decimalSampleBody = document.getElementById("decimalSampleBody");
    const dateOrderHint = document.getElementById("dateOrderHint");
    const dateSampleWrap = document.getElementById("dateSampleWrap");
    const dateSampleBody = document.getElementById("dateSampleBody");
    const dateDetectError = document.getElementById("dateDetectError");
    const valueCol = document.getElementById("valueColumn");
    const seriesName = document.getElementById("seriesName");
    const freq = document.getElementById("uploadFrequency");
    const sepInput = document.getElementById("uploadSep");
    const form = document.getElementById("uploadForm");
    const result = document.getElementById("uploadResult");
    let pendingFile = null;
    let previewCache = null;

    function fillDecimalModes(modes, selected) {
      if (!decimalMode) return;
      decimalMode.innerHTML = "";
      (modes || []).forEach((m) => {
        const o = document.createElement("option");
        o.value = m.id;
        o.textContent = m.label;
        decimalMode.appendChild(o);
      });
      if (selected) decimalMode.value = selected;
    }

    function renderDecimalDetection(det) {
      if (!det) {
        if (decimalDetectMeta) decimalDetectMeta.innerHTML = "";
        if (decimalSampleWrap) decimalSampleWrap.hidden = true;
        return;
      }
      if (decimalDetectMeta) {
        const pct = Math.round((det.parse_rate || 0) * 100);
        decimalDetectMeta.innerHTML = `
          <dt>Lesbarkeit</dt><dd>${det.parsed_count} / ${det.total_count} (${pct}%)</dd>
          <dt>Modus</dt><dd class="mono">${det.mode}</dd>
        `;
      }
      if (decimalMode && det.mode && decimalMode.querySelector(`option[value="${det.mode}"]`)) {
        decimalMode.value = det.mode;
      }
      if (decimalSampleBody && decimalSampleWrap) {
        decimalSampleBody.innerHTML = "";
        (det.samples || []).forEach((row) => {
          const tr = document.createElement("tr");
          const parsed = row.parsed == null ? "—" : row.parsed;
          tr.innerHTML = `<td class="mono">${row.raw}</td><td class="mono">${parsed}</td>`;
          decimalSampleBody.appendChild(tr);
        });
        decimalSampleWrap.hidden = !(det.samples || []).length;
      }
    }

    async function refreshDecimalDetection() {
      if (!pendingFile || !valueCol?.value) return;
      const fd = new FormData();
      fd.append("file", pendingFile);
      fd.append("value_column", valueCol.value);
      fd.append("decimal_mode", decimalMode?.value || "auto");
      const res = await fetch("/api/upload/validate-decimals", { method: "POST", body: fd });
      const data = await res.json();
      if (data.ok) renderDecimalDetection(data.decimal_detection);
    }

    function fillDateModes(modes, selected) {
      if (!dateMode) return;
      dateMode.innerHTML = "";
      (modes || []).forEach((m) => {
        const o = document.createElement("option");
        o.value = m.id;
        o.textContent = m.example ? `${m.label} · z. B. ${m.example}` : m.label;
        o.dataset.order = m.order || "";
        dateMode.appendChild(o);
      });
      if (selected) dateMode.value = selected;
    }

    function renderDateDetection(det) {
      if (!det) {
        if (dateDetectMeta) dateDetectMeta.innerHTML = "";
        if (dateSampleWrap) dateSampleWrap.hidden = true;
        return;
      }
      if (dateOrderHint) {
        dateOrderHint.textContent = `Erkannt: ${det.label_de} — ${det.order_de}`;
      }
      if (dateDetectMeta) {
        const pct = Math.round((det.parse_rate || 0) * 100);
        dateDetectMeta.innerHTML = `
          <dt>Lesbarkeit</dt><dd>${det.parsed_count} / ${det.total_count} (${pct}%)</dd>
          <dt>Reihenfolge</dt><dd>${det.order_de}</dd>
          <dt>Modus</dt><dd class="mono">${det.mode}</dd>
        `;
      }
      if (dateFormatInput) {
        dateFormatInput.value = det.strftime_format || "";
      }
      if (dateMode && det.mode && dateMode.querySelector(`option[value="${det.mode}"]`)) {
        dateMode.value = det.mode;
      }
      if (dateSampleBody && dateSampleWrap) {
        dateSampleBody.innerHTML = "";
        (det.samples || []).forEach((row) => {
          const tr = document.createElement("tr");
          tr.innerHTML = `<td class="mono">${row.raw}</td><td class="mono">${row.parsed}</td>`;
          dateSampleBody.appendChild(tr);
        });
        dateSampleWrap.hidden = !(det.samples || []).length;
      }
      if (dateDetectError) {
        const ok = (det.parse_rate || 0) >= 0.5;
        dateDetectError.hidden = ok;
        dateDetectError.textContent = ok
          ? ""
          : "Weniger als 50% der Datumswerte lesbar — bitte anderes Format wählen.";
      }
    }

    async function refreshDateDetection() {
      if (!pendingFile || !dateCol?.value) return;
      const fd = new FormData();
      fd.append("file", pendingFile);
      fd.append("date_column", dateCol.value);
      fd.append("date_parse_mode", dateMode?.value || "auto");
      if (dateFormatInput?.value) fd.append("date_format", dateFormatInput.value);
      const res = await fetch("/api/upload/validate-dates", { method: "POST", body: fd });
      const data = await res.json();
      if (!data.ok) {
        if (dateDetectError) {
          dateDetectError.hidden = false;
          dateDetectError.textContent = data.message || "Datumserkennung fehlgeschlagen";
        }
        return;
      }
      renderDateDetection(data.date_detection);
    }

    drop?.addEventListener("click", () => input?.click());
    drop?.addEventListener("dragover", (e) => {
      e.preventDefault();
      drop.classList.add("dragover");
    });
    drop?.addEventListener("dragleave", () => drop.classList.remove("dragover"));
    drop?.addEventListener("drop", (e) => {
      e.preventDefault();
      drop.classList.remove("dragover");
      if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
    });
    input?.addEventListener("change", () => {
      if (input.files?.length) handleFile(input.files[0]);
    });

    valueCol?.addEventListener("change", () => {
      if (previewCache?.decimal_detection && valueCol.value === previewCache.suggested_value_column) {
        renderDecimalDetection(previewCache.decimal_detection);
      }
      refreshDecimalDetection();
    });
    decimalMode?.addEventListener("change", refreshDecimalDetection);

    dateCol?.addEventListener("change", () => {
      if (previewCache?.date_columns_info?.[dateCol.value]) {
        renderDateDetection(previewCache.date_columns_info[dateCol.value]);
        if (dateMode) dateMode.value = previewCache.date_columns_info[dateCol.value].mode || "auto";
      }
      refreshDateDetection();
    });
    dateMode?.addEventListener("change", refreshDateDetection);

    async function handleFile(file) {
      pendingFile = file;
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/api/upload/preview", { method: "POST", body: fd });
      const data = await res.json();
      if (!data.ok) {
        toast(data.message || "Vorschau fehlgeschlagen");
        return;
      }
      previewCache = data;
      if (wizard) wizard.hidden = false;
      if (preview) preview.value = data.preview_text || "";
      if (fileMeta) fileMeta.textContent = `${data.filename} · ${data.line_count} Zeilen`;
      if (sepInput) sepInput.value = data.sep || ";";
      if (encodingInput) encodingInput.value = data.encoding || "utf-8-sig";
      fillDateModes(data.date_parse_modes, data.date_detection?.mode || "auto");
      fillDecimalModes(data.decimal_modes, data.decimal_detection?.mode || "auto");
      fillDateSelect(dateCol, data.columns, data.suggested_date_column);
      fillDateSelect(valueCol, data.value_columns || data.columns, data.suggested_value_column);
      if (seriesName) seriesName.value = data.suggested_value_column || "";
      if (freq && data.frequencies) {
        freq.innerHTML = "";
        data.frequencies.forEach((f) => {
          const o = document.createElement("option");
          o.value = f.id;
          o.textContent = f.label;
          freq.appendChild(o);
        });
        if (data.suggested_frequency) freq.value = data.suggested_frequency;
      }
      renderDateDetection(data.date_detection);
      renderDecimalDetection(data.decimal_detection);
    }

    form?.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!pendingFile) {
        toast("Bitte Datei wählen");
        return;
      }
      if (dateDetectError && !dateDetectError.hidden) {
        toast("Bitte Datumsformat korrigieren bevor Sie importieren.");
        return;
      }
      const fd = new FormData(form);
      fd.set("file", pendingFile);
      const res = await fetch("/api/upload", { method: "POST", body: fd });
      const data = await res.json();
      if (result) {
        result.hidden = false;
        const detailLink = data.redirect_url || (data.series?.slug ? `/series/${data.series.slug}` : "/series");
        result.innerHTML = data.ok
          ? `<strong>${data.message}</strong> · <a href="${detailLink}" class="stat-link">Zur Zeitreihe</a> · <a href="/series" class="stat-link">Alle Zeitreihen</a>`
          : data.message;
      }
      toast(data.ok ? "Import OK" : data.message || "Fehler");
    });
  }

  function initCategoriesPage(returnTo) {
    const form = document.getElementById("categoryCreateForm");
    const createBtn = document.getElementById("categoryCreateBtn");

    async function createCategory() {
      const name = document.getElementById("newCategoryName")?.value?.trim();
      if (!name) {
        toast("Bitte Tag-Namen eingeben.");
        return;
      }
      const res = await fetch("/api/categories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      let data = {};
      try {
        data = await res.json();
      } catch {
        toast("Server-Antwort unlesbar.");
        return;
      }
      if (!res.ok || data.ok === false) {
        toast(data.message || "Anlegen fehlgeschlagen");
        return;
      }
      toast(`Tag „${data.name}“ angelegt.`);
      const nameInput = document.getElementById("newCategoryName");
      if (nameInput) nameInput.value = "";
      if (returnTo) window.location.href = returnTo;
      else window.location.reload();
    }

    form?.addEventListener("submit", (e) => {
      e.preventDefault();
      createCategory();
    });
    createBtn?.addEventListener("click", createCategory);

    document.querySelectorAll("[data-save-category]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.saveCategory;
        const input = document.querySelector(`.category-name-input[data-id="${id}"]`);
        const name = input?.value?.trim();
        if (!name) return;
        const res = await fetch(`/api/categories/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name }),
        });
        const data = await res.json();
        toast(data.message || (data.ok ? "Gespeichert" : "Fehler"));
      });
    });

    document.querySelectorAll("[data-delete-category]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.deleteCategory;
        if (!confirm("Tag wirklich löschen? Zuordnungen werden entfernt.")) return;
        const res = await fetch(`/api/categories/${id}`, { method: "DELETE" });
        const data = await res.json();
        if (data.ok) window.location.reload();
        else toast(data.message || "Fehler");
      });
    });
  }

  function initListToolbar({
    tagFilterId,
    categoryFilterId,
    searchInputId,
    tableId,
    showHiddenId,
    rowSelector = "tbody tr",
  }) {
    const filterId = tagFilterId || categoryFilterId;
    const searchInput = document.getElementById(searchInputId);
    const table = document.getElementById(tableId);
    const applySearch = () => {
      const q = (searchInput?.value || "").trim().toLowerCase();
      table?.querySelectorAll(rowSelector).forEach((row) => {
        const hay = (row.dataset.search || row.textContent || "").toLowerCase();
        row.hidden = !!(q && !hay.includes(q));
      });
    };
    searchInput?.addEventListener("input", applySearch);

    document.getElementById(filterId)?.addEventListener("change", (e) => {
      const v = e.target.value;
      const url = new URL(window.location.href);
      if (v) url.searchParams.set("tag", v);
      else url.searchParams.delete("tag");
      url.searchParams.delete("category_id");
      window.location.href = url.toString();
    });

    document.getElementById(showHiddenId)?.addEventListener("change", (e) => {
      const url = new URL(window.location.href);
      if (e.target.checked) url.searchParams.set("include_hidden", "1");
      else url.searchParams.delete("include_hidden");
      window.location.href = url.toString();
    });
  }

  const REPORTING_TAG = "Reporting";

  function sortTagSelect(el) {
    const opts = Array.from(el.options).sort((a, b) => a.text.localeCompare(b.text, "de"));
    el.innerHTML = "";
    opts.forEach((o) => el.appendChild(o));
  }

  function wireTagShuttle({ selectedEl, availableEl, addOne, addAll, remOne, remAll, confirmReporting }) {
    async function moveSelected(from, to, checkReporting = false) {
      const moving = Array.from(from.selectedOptions).map((o) => o.textContent);
      if (checkReporting && moving.length) {
        const ok = await confirmReporting(moving);
        if (!ok) return;
      }
      Array.from(from.selectedOptions).forEach((opt) => to.appendChild(opt));
      sortTagSelect(from);
      sortTagSelect(to);
    }
    async function moveAll(from, to, checkReporting = false) {
      const moving = Array.from(from.options).map((o) => o.textContent);
      if (checkReporting && moving.length) {
        const ok = await confirmReporting(moving);
        if (!ok) return;
      }
      Array.from(from.options).forEach((opt) => to.appendChild(opt));
      sortTagSelect(from);
      sortTagSelect(to);
    }
    addOne?.addEventListener("click", () => moveSelected(availableEl, selectedEl));
    addAll?.addEventListener("click", () => moveAll(availableEl, selectedEl));
    remOne?.addEventListener("click", () => moveSelected(selectedEl, availableEl, true));
    remAll?.addEventListener("click", () => moveAll(selectedEl, availableEl, true));
    return {
      selectedTags() {
        return Array.from(selectedEl.options)
          .map((o) => parseInt(o.value, 10))
          .filter(Boolean);
      },
    };
  }

  function initTagShuttle() {
    if (initTagShuttle._ready) return;
    initTagShuttle._ready = true;
    const modal = document.getElementById("tagShuttleModal");
    const reportingModal = document.getElementById("reportingConfirmModal");
    const selectedEl = document.getElementById("tagShuttleSelected");
    const availableEl = document.getElementById("tagShuttleAvailable");
    const saveBtn = document.getElementById("tagShuttleSave");
    const titleEl = document.getElementById("tagShuttleTitle");
    if (!modal || !selectedEl || !availableEl) return;

    let reportingResolve = null;

    function askReporting() {
      if (reportingModal) {
        return new Promise((resolve) => {
          reportingResolve = resolve;
          reportingModal.hidden = false;
        });
      }
      return Promise.resolve(confirm("Ist Reporting wirklich erledigt?"));
    }

    reportingModal?.querySelector("[data-reporting-cancel]")?.addEventListener("click", () => {
      reportingModal.hidden = true;
      reportingResolve?.(false);
      reportingResolve = null;
    });
    document.getElementById("reportingConfirmBtn")?.addEventListener("click", () => {
      reportingModal.hidden = true;
      reportingResolve?.(true);
      reportingResolve = null;
    });

    async function confirmReporting(tagsToRemove) {
      if (!tagsToRemove.includes(REPORTING_TAG)) return true;
      return askReporting();
    }

    const shuttle = wireTagShuttle({
      selectedEl,
      availableEl,
      addOne: document.getElementById("tagAddOne"),
      addAll: document.getElementById("tagAddAll"),
      remOne: document.getElementById("tagRemOne"),
      remAll: document.getElementById("tagRemAll"),
      confirmReporting,
    });

    let context = null;
    let allTagsCache = null;

    async function loadAllCategories() {
      if (allTagsCache) return allTagsCache;
      const res = await fetch("/api/categories");
      allTagsCache = res.ok ? await res.json() : [];
      return allTagsCache;
    }

    function fillLists(selectedIds, allCategories) {
      selectedEl.innerHTML = "";
      availableEl.innerHTML = "";
      const selected = new Set(selectedIds.map(String));
      (allCategories || [])
        .slice()
        .sort((a, b) => a.name.localeCompare(b.name, "de"))
        .forEach((cat) => {
          const opt = document.createElement("option");
          opt.value = String(cat.id);
          opt.textContent = cat.name;
          if (selected.has(String(cat.id))) selectedEl.appendChild(opt);
          else availableEl.appendChild(opt);
        });
    }

    function parseCategoryIds(raw) {
      return (raw || "")
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean)
        .map((t) => parseInt(t, 10))
        .filter(Boolean);
    }

    async function openShuttle(entityType, entityId, selectedIds, label) {
      context = { entityType, entityId };
      if (titleEl) titleEl.textContent = label || "Tags";
      const allCategories = await loadAllCategories();
      fillLists(selectedIds, allCategories);
      modal.hidden = false;
    }

    document.addEventListener("click", (e) => {
      const cell = e.target.closest(".tag-shuttle-trigger");
      if (!cell || cell.closest("a")) return;
      e.preventDefault();
      e.stopPropagation();
      openShuttle(
        cell.dataset.entityType,
        cell.dataset.entityId,
        parseCategoryIds(cell.dataset.categoryIds),
        "Tags"
      );
    });

    document.getElementById("seriesTagsEditBtn")?.addEventListener("click", (e) => {
      const btn = e.currentTarget;
      openShuttle(
        btn.dataset.entityType,
        btn.dataset.entityId,
        parseCategoryIds(btn.dataset.categoryIds),
        "Tags"
      );
    });

    modal.querySelectorAll("[data-tag-shuttle-cancel]").forEach((el) => {
      el.addEventListener("click", () => {
        modal.hidden = true;
        context = null;
      });
    });

    saveBtn?.addEventListener("click", async () => {
      if (!context) return;
      const category_ids = shuttle.selectedTags();
      const res = await fetch("/api/tags", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          entity_type: context.entityType,
          entity_id: context.entityId,
          category_ids,
        }),
      });
      const data = await res.json();
      if (!res.ok || data.ok === false) {
        toast(data.message || "Speichern fehlgeschlagen");
        return;
      }
      modal.hidden = true;
      toast("Tags gespeichert");
      window.location.reload();
    });
  }

  function initSeriesEdit(slug) {
    const form = document.getElementById("seriesEditForm");
    const saveBtn = document.getElementById("seriesSaveBtn");

    async function saveSeries() {
      const name = document.getElementById("seriesNameEdit")?.value?.trim();
      const res = await fetch(`/api/series/${slug}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      const data = await res.json();
      if (!res.ok || data.ok === false) {
        toast(data.message || "Speichern fehlgeschlagen");
        return;
      }
      toast("Gespeichert");
      window.location.reload();
    }

    form?.addEventListener("submit", (e) => {
      e.preventDefault();
      saveSeries();
    });
    saveBtn?.addEventListener("click", saveSeries);
  }

  initCore();
  return {
    initCore,
    initCorrelation,
    initTsa,
    initUpload,
    initCategoriesPage,
    initSeriesEdit,
    initListToolbar,
    initTagShuttle,
    toast,
  };
})();
