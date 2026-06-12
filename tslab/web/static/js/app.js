/**
 * TSLab Dashboard — Theme, Navigation, Mock-Workflows
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

  function parseDate(iso) {
    return new Date(iso + "T12:00:00");
  }

  function positionBar(bar, startIso, endIso, globalStart, globalEnd) {
    const total = globalEnd - globalStart || 1;
    const left = ((parseDate(startIso) - globalStart) / total) * 100;
    const width = ((parseDate(endIso) - parseDate(startIso)) / total) * 100;
    bar.style.left = `${Math.max(0, left)}%`;
    bar.style.width = `${Math.max(2, width)}%`;
  }

  async function fetchOverlap(a, b) {
    const res = await fetch(`/api/overlap?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`);
    if (!res.ok) throw new Error("Keine Überlappung");
    return res.json();
  }

  function renderOverlap(data) {
    const viz = document.getElementById("overlapViz");
    const ph = document.getElementById("overlapPlaceholder");
    if (!viz || !ph) return;

    ph.hidden = true;
    viz.hidden = false;

    const gStart = parseDate(
      data.series_a.first_date < data.series_b.first_date
        ? data.series_a.first_date
        : data.series_b.first_date
    );
    const gEnd = parseDate(
      data.series_a.last_date > data.series_b.last_date
        ? data.series_a.last_date
        : data.series_b.last_date
    );

    positionBar(document.getElementById("barA"), data.series_a.first_date, data.series_a.last_date, gStart, gEnd);
    positionBar(document.getElementById("barB"), data.series_b.first_date, data.series_b.last_date, gStart, gEnd);
    positionBar(document.getElementById("barOverlap"), data.overlap_start, data.overlap_end, gStart, gEnd);

    const startInput = document.getElementById("corrStart");
    const endInput = document.getElementById("corrEnd");
    const freqSelect = document.getElementById("frequency");
    if (startInput) startInput.value = data.suggested_start;
    if (endInput) endInput.value = data.suggested_end;
    if (freqSelect) freqSelect.value = data.suggested_frequency;

    const meta = document.getElementById("overlapMeta");
    if (meta) {
      meta.innerHTML = `
        <dt>Serie A</dt><dd>${data.series_a.first_date} → ${data.series_a.last_date} (${data.series_a.observation_count} n)</dd>
        <dt>Serie B</dt><dd>${data.series_b.first_date} → ${data.series_b.last_date} (${data.series_b.observation_count} n)</dd>
        <dt>Überlappung</dt><dd>${data.overlap_start} → ${data.overlap_end} (~${data.overlap_observations} Monate)</dd>
        <dt>Rhythmus (Vorschlag)</dt><dd>${data.suggested_frequency_label}</dd>
      `;
    }
  }

  function initCorrelation() {
    const selA = document.getElementById("seriesA");
    const selB = document.getElementById("seriesB");
    const form = document.getElementById("correlationForm");

    async function update() {
      const a = selA?.value;
      const b = selB?.value;
      if (!a || !b || a === b) return;
      try {
        const data = await fetchOverlap(a, b);
        renderOverlap(data);
      } catch {
        toast("Keine gemeinsame Datenbasis für diese Paarung.");
      }
    }

    selA?.addEventListener("change", update);
    selB?.addEventListener("change", update);
    update();

    form?.addEventListener("submit", async (e) => {
      e.preventDefault();
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
        panel.innerHTML = `<strong>${data.message}</strong><br><code>${data.job?.output_preview || ""}</code>`;
      }
      toast("Korrelationslauf simuliert");
    });
  }

  async function loadSeriesMeta(slug) {
    const res = await fetch(`/api/series/${slug}`);
    return res.json();
  }

  function initTsa() {
    const sel = document.getElementById("tsaSeries");
    const form = document.getElementById("tsaForm");
    const metaBox = document.getElementById("seriesMeta");

    async function updateMeta() {
      const slug = sel?.value;
      if (!slug || !metaBox) return;
      const s = await loadSeriesMeta(slug);
      metaBox.innerHTML = `
        <strong>${s.label_de}</strong><br>
        Daten: <span class="mono">${s.first_date}</span> bis <span class="mono">${s.last_date}</span><br>
        Beobachtungen: ${s.observation_count} · Rhythmus: ${s.frequency_label}
      `;
    }

    sel?.addEventListener("change", updateMeta);
    updateMeta();

    form?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const models = fd.getAll("models");
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
        panel.innerHTML = `<strong>${data.message}</strong><br>Modelle: ${models.join(", ")}<br><code>${data.job?.output_preview || ""}</code>`;
      }
      toast("TSA-Lauf simuliert");
    });
  }

  function initUpload() {
    const drop = document.getElementById("uploadDrop");
    const input = document.getElementById("fileInput");
    const meta = document.getElementById("uploadMeta");
    const fileName = document.getElementById("fileName");
    const form = document.getElementById("uploadForm");
    const result = document.getElementById("uploadResult");

    drop?.addEventListener("click", () => input?.click());

    drop?.addEventListener("dragover", (e) => {
      e.preventDefault();
      drop.classList.add("dragover");
    });
    drop?.addEventListener("dragleave", () => drop.classList.remove("dragover"));
    drop?.addEventListener("drop", (e) => {
      e.preventDefault();
      drop.classList.remove("dragover");
      if (e.dataTransfer.files.length && input) {
        input.files = e.dataTransfer.files;
        showFile(e.dataTransfer.files[0].name);
      }
    });

    input?.addEventListener("change", () => {
      if (input.files?.length) showFile(input.files[0].name);
    });

    function showFile(name) {
      if (fileName) fileName.textContent = name;
      if (meta) meta.hidden = false;
    }

    form?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const res = await fetch("/api/upload", { method: "POST", body: fd });
      const data = await res.json();
      if (result) {
        result.hidden = false;
        result.innerHTML = data.ok
          ? `<strong>${data.message}</strong><br>Slug: <code>${data.series?.slug}</code>`
          : data.message;
      }
      toast(data.ok ? "Upload simuliert" : "Upload fehlgeschlagen");
    });
  }

  initCore();

  return { initCorrelation, initTsa, initUpload, toast };
})();
