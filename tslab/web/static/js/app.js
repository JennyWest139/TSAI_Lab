/**
 * TSLab Dashboard — Theme, Navigation, Workflows (Design v1 + unabhängige Von/Bis-Daten)
 */
const TSLab = (() => {
  const STORAGE_THEME = "tslab-theme";

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
    const rep = data.report;
    if (rep?.ok && rep.report_url) {
      html += ` <a href="${rep.report_url}" class="stat-link">Word-Bericht (.docx)</a>`;
    } else if (rep && !rep.ok) {
      html += ` <span class="hint"> · KI-Bericht: ${rep.message}</span>`;
    }
    return html;
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
   * Zwei unabhängige Auswahlfelder — nur Zeitstempel aus dates[].
   * Validierung: von < bis (beide in dates).
   */
  function bindIndependentDateRange(vonEl, bisEl, dates, suggestedVon, suggestedBis, onChange) {
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
    const previewCard = document.getElementById("corrPreviewCard");
    const returnsChart = document.getElementById("corrReturnsChart");
    const trendNote = document.getElementById("corrTrendNote");
    const form = document.getElementById("correlationForm");
    let validateDates = () => false;
    let gStart;
    let gEnd;

    function refreshWindowBar() {
      updateWindowBar(
        document.getElementById("barWindow"),
        vonSelect?.value,
        bisSelect?.value,
        gStart,
        gEnd
      );
      refreshPreview();
    }

    async function refreshPreview() {
      const a = selA?.value;
      const b = selB?.value;
      const start = vonSelect?.value;
      const end = bisSelect?.value;
      if (!a || !b || a === b || !start || !end || start >= end) {
        if (previewCard) previewCard.hidden = true;
        return;
      }
      if (!window.TSLabCharts || !window.Plotly) return;

      const params = new URLSearchParams({ a, b, start, end });
      if (showReturnsEl?.checked) params.set("show_returns", "1");
      if (modeSelect?.value) params.set("analysis_mode", modeSelect.value);
      if (freqSelect?.value) params.set("frequency", freqSelect.value);

      try {
        const res = await fetch(`/api/correlation/preview?${params}`);
        if (!res.ok) throw new Error("Vorschau nicht verfügbar");
        const data = await res.json();
        if (previewCard) previewCard.hidden = false;
        TSLabCharts.renderPairChart("corrPreviewChart", data);
        if (trendNote) {
          trendNote.textContent = `${data.series_a.trend_note} · ${data.series_b.trend_note}`;
        }
        const returnsHint = document.getElementById("corrReturnsHint");
        if (returnsHint) {
          returnsHint.textContent = data.returns_recommended
            ? "Optional: kontinuierliche Renditen für Kursindizes."
            : "Renditen nur per Checkbox — für diese Paarung kein Standard.";
        }
        if (returnsChart) {
          const hasReturns = !!(data.returns_a?.dates?.length);
          returnsChart.hidden = !hasReturns;
          if (hasReturns) TSLabCharts.renderReturnsPairChart("corrReturnsChart", data);
        }
      } catch {
        if (previewCard) previewCard.hidden = true;
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

    async function update() {
      const a = selA?.value;
      const b = selB?.value;
      if (!a || !b || a === b) return;
      try {
        renderOverlap(await fetchOverlap(a, b, freqSelect?.value || null));
      } catch {
        toast("Keine gemeinsame Datenbasis für diese Paarung.");
      }
    }

    selA?.addEventListener("change", update);
    selB?.addEventListener("change", update);
    freqSelect?.addEventListener("change", update);
    showReturnsEl?.addEventListener("change", refreshPreview);
    modeSelect?.addEventListener("change", refreshPreview);
    document.getElementById("themeToggle")?.addEventListener("click", () => {
      setTimeout(refreshPreview, 50);
    });
    update();

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
      const panel = document.getElementById("corrResult");
      if (panel) {
        panel.hidden = false;
        panel.innerHTML = formatRunResult(data);
      }
      toast(data.ok ? data.message : data.message || "Fehler");
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
      const s = await loadSeriesMeta(slug);
      const dates = s.dates || [];

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
      refreshWindowChart();
    });
    updateMeta();

    async function refreshWindowChart() {
      const chartEl = document.getElementById("tsaWindowChart");
      if (!chartEl || !window.TSLabCharts?.renderTsaWindowChart) return;
      const fd = new FormData(form);
      const params = new URLSearchParams(fd);
      params.set("series_slug", sel?.value || "");
      params.delete("models");
      try {
        const res = await fetch(`/api/tsa/window-preview?${params}`);
        const data = await res.json();
        if (!data.error) TSLabCharts.renderTsaWindowChart("tsaWindowChart", data);
      } catch (_) {
        /* ignore preview errors while typing */
      }
    }

    ["trainStart", "trainEnd", "forecastEnd", "plotPre", "plotForecast", "plotPost", "tsaMode"].forEach((id) => {
      document.getElementById(id)?.addEventListener("change", refreshWindowChart);
      document.getElementById(id)?.addEventListener("input", refreshWindowChart);
    });
    setTimeout(refreshWindowChart, 400);

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
      const res = await fetch("/api/tsa/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      const panel = document.getElementById("tsaResult");
      if (panel) {
        panel.hidden = false;
        panel.innerHTML = formatRunResult(data);
      }
      toast(data.ok ? data.message : data.message || "Fehler");
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

  initCore();
  return { initCorrelation, initTsa, initUpload, toast };
})();
