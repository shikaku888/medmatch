/* MedMatch — frontend logic. Vanilla JS, no build step. */
"use strict";

const $ = (sel) => document.querySelector(sel);

/* ---------- profile + cabinet store (localStorage) ---------- */
const CAB_KEY = "medmatch_cabinet_v1";
const PROF_KEY = "medmatch_profiles_v1";

function loadProfiles() {
  try {
    const raw = localStorage.getItem(PROF_KEY);
    if (raw) {
      const profiles = JSON.parse(raw);
      if (Array.isArray(profiles) && profiles.length) return profiles;
    }
  } catch { /* fall through to migration */ }
  // migrate legacy single cabinet into a default profile
  let cabinet = [];
  try {
    cabinet = JSON.parse(localStorage.getItem(CAB_KEY) || "[]");
  } catch { /* ignore */ }
  return [{ id: "default", name: "My cabinet", cabinet }];
}

let profiles = loadProfiles();
let activeProfile = profiles[0];
let cabinet = activeProfile.cabinet;

function saveProfiles() {
  localStorage.setItem(PROF_KEY, JSON.stringify(profiles));
  renderCabinetCount();
}
function saveCabinet() {
  saveProfiles();
}
function cabinetAdd(item) {
  const exists = cabinet.some((c) => c.id === item.id && c.kind === item.kind);
  if (!exists) {
    cabinet.push({ ...item, time: item.time || null });
    saveCabinet();
  }
  renderCabinet();
  flash("Added to cabinet");
}
function cabinetRemove(idx) {
  cabinet.splice(idx, 1);
  saveCabinet();
  renderCabinet();
}

function renderProfiles() {
  const sel = $("#profile-select");
  sel.innerHTML = profiles
    .map((p) => `<option value="${p.id}">${escapeHtml(p.name)}</option>`)
    .join("") + '<option value="__new__">+ New profile…</option>';
  sel.value = activeProfile.id;
}
function switchProfile(id) {
  activeProfile = profiles.find((p) => p.id === id) || profiles[0];
  cabinet = activeProfile.cabinet;
  saveProfiles();
  renderProfiles();
  renderCabinet();
}
$("#profile-select").addEventListener("change", (e) => {
  if (e.target.value === "__new__") {
    const name = (prompt("Name for the new profile (person you care for):") || "").trim();
    if (!name) {
      renderProfiles();
      return;
    }
    const profile = { id: "p" + Date.now(), name, cabinet: [] };
    profiles.push(profile);
    switchProfile(profile.id);
  } else {
    switchProfile(e.target.value);
  }
});
/* ---------- tabs ---------- */
$("#tabs").addEventListener("click", (e) => {
  const btn = e.target.closest(".tab");
  if (!btn) return;
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t === btn));
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  $("#view-" + btn.dataset.tab).classList.add("active");
  if (btn.dataset.tab === "cabinet") renderCabinet();
  if (btn.dataset.tab === "check") runCheck();
  if (btn.dataset.tab === "review") loadReview();
});

function goTab(name) {
  document.querySelector(`.tab[data-tab="${name}"]`).click();
}

/* ---------- camera / barcode ---------- */
let stream = null;
let scannerLoop = null;
let detector = null;

if ("BarcodeDetector" in window) {
  detector = new BarcodeDetector({ formats: ["ean_13", "ean_8", "upc_a", "upc_e", "code_128"] });
} else {
  $("#camera-hint").textContent =
    "Camera barcode scanning works in Chrome/Edge. On other browsers, type the barcode below.";
}

$("#btn-camera").addEventListener("click", async () => {
  if (stream) return stopCamera();
  if (!detector) {
    $("#camera-hint").textContent = "Barcode scanning is not supported in this browser — type the barcode below.";
    return;
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment" },
      audio: false,
    });
  } catch (err) {
    $("#camera-hint").textContent = "Camera unavailable: " + err.message;
    return;
  }
  const video = $("#camera");
  video.srcObject = stream;
  video.style.display = "block";
  $("#scan-placeholder").style.display = "none";
  $("#btn-camera").textContent = "Stop camera";
  $("#camera-hint").textContent = "Aim the camera at the barcode…";
  await video.play();
  scannerLoop = setInterval(async () => {
    if (video.readyState < 2) return;
    try {
      const codes = await detector.detect(video);
      if (codes.length) {
        stopCamera();
        $("#barcode-input").value = codes[0].rawValue;
        lookupBarcode(codes[0].rawValue);
      }
    } catch (err) {
      /* keep trying */
    }
  }, 400);
});

function stopCamera() {
  if (scannerLoop) clearInterval(scannerLoop);
  scannerLoop = null;
  if (stream) {
    stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }
  $("#camera").style.display = "none";
  $("#scan-placeholder").style.display = "flex";
  $("#btn-camera").textContent = "Start camera";
}

/* ---------- lookup ---------- */
$("#btn-lookup").addEventListener("click", () => {
  const code = $("#barcode-input").value.trim();
  if (code) lookupBarcode(code);
});
$("#barcode-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") $("#btn-lookup").click();
});

/* ---------- iDISK product search ---------- */
$("#btn-product").addEventListener("click", () => doProductSearch());
$("#product-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") doProductSearch();
});

async function doProductSearch() {
  const q = $("#product-input").value.trim();
  const box = $("#product-results");
  if (!q) return;
  box.innerHTML = '<div class="empty-note">Searching…</div>';
  try {
    const res = await fetch("/api/products?q=" + encodeURIComponent(q) + "&limit=8");
    const data = await res.json();
    box.innerHTML = "";
    if (!data.results.length) {
      box.innerHTML = '<div class="empty-note">No products found.</div>';
      return;
    }
    data.results.forEach((p) => {
      const item = document.createElement("div");
      item.className = "result-item";
      const left = document.createElement("div");
      left.className = "label";
      left.textContent = p.name;
      const sub = document.createElement("div");
      sub.className = "sub";
      sub.textContent = (p.company ? p.company + " · " : "") + (p.ingredients || []).join(", ");
      left.appendChild(sub);
      const add = document.createElement("button");
      add.className = "btn";
      add.textContent = "Add";
      add.addEventListener("click", async () => {
        add.textContent = "Adding…";
        add.disabled = true;
        let added = 0;
        for (const ing of p.ingredients || []) {
          const r = await fetch("/api/search?q=" + encodeURIComponent(ing) + "&limit=1");
          const j = await r.json();
          const m = (j.results || []).find((x) => x.kind === "herb" && x.score >= 0.85);
          if (m) {
            cabinetAdd({ kind: "herb", id: m.id, label: m.label, source: p.name });
            added += 1;
          }
        }
        add.textContent = added ? "Added " + added : "No matches";
      });
      item.append(left, add);
      box.appendChild(item);
    });
  } catch {
    box.innerHTML = '<div class="empty-note">Server unreachable — is the backend running?</div>';
  }
}

/* ---------- label OCR (Tesseract.js, lazy-loaded) ---------- */
$("#btn-ocr").addEventListener("click", () => $("#label-photo").click());
$("#label-photo").addEventListener("change", (e) => {
  const file = e.target.files && e.target.files[0];
  if (file) ocrLabel(file);
  e.target.value = "";
});

async function ocrLabel(file) {
  const hint = $("#camera-hint");
  hint.textContent = "Reading label…";
  try {
    if (!window.Tesseract) {
      await new Promise((resolve, reject) => {
        const s = document.createElement("script");
        s.src = "https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js";
        s.onload = resolve;
        s.onerror = reject;
        document.head.appendChild(s);
      });
    }
    const url = URL.createObjectURL(file);
    const { data } = await window.Tesseract.recognize(url, "eng");
    URL.revokeObjectURL(url);
    hint.textContent = "Label read — matching ingredients…";
    const words = data.text.toLowerCase().split(/[^a-z0-9]+/).filter((w) => w.length > 2);
    const found = new Map();
    for (let i = 0; i < words.length - 1 && found.size < 8; i++) {
      const phrase = words[i] + " " + words[i + 1];
      if (found.has(phrase)) continue;
      const res = await fetch("/api/search?q=" + encodeURIComponent(phrase) + "&limit=3");
      const j = await res.json();
      (j.results || []).forEach((r) => {
        if (r.score >= 0.9) found.set(r.kind + ":" + r.id, r);
      });
    }
    const results = [...found.values()].slice(0, 8);
    if (!results.length) {
      hint.textContent = "No recognized ingredients in the label — try a clearer photo.";
      return;
    }
    renderOcrResults(results);
    hint.textContent = "Found " + results.length + " ingredients. Tap Add.";
  } catch {
    hint.textContent = "OCR unavailable (needs network for the OCR engine) — type the barcode or search manually.";
  }
}

function renderOcrResults(results) {
  const box = $("#ocr-results");
  box.innerHTML = "";
  results.forEach((r) => {
    const item = document.createElement("div");
    item.className = "result-item";
    const badge = document.createElement("span");
    badge.className = "kind-badge " + (r.kind === "herb" ? "kind-herb" : r.kind === "food" ? "kind-food" : "kind-drug");
    badge.textContent = r.kind === "herb" ? "Supplement" : r.kind === "food" ? "Food" : "Drug";
    const label = document.createElement("span");
    label.className = "label";
    label.textContent = r.label;
    const add = document.createElement("button");
    add.className = "btn";
    add.textContent = "Add";
    add.addEventListener("click", () => {
      cabinetAdd({ kind: r.kind, id: r.id, label: r.label, source: "OCR label" });
      add.textContent = "Added";
      add.disabled = true;
    });
    item.append(badge, label, add);
    box.appendChild(item);
  });
}

let currentProduct = null;

async function lookupBarcode(code) {
  const card = $("#product-card");
  card.hidden = false;
  card.querySelector("#product-name").textContent = "Looking up " + code + "…";
  card.querySelector("#product-meta").textContent = "";
  card.querySelector("#product-ingredients").innerHTML = "";
  card.querySelector("#product-warnings").innerHTML = "";
  $("#btn-add-product").disabled = true;
  try {
    const res = await fetch("/api/lookup/" + encodeURIComponent(code));
    if (!res.ok) throw new Error("not found");
    const p = await res.json();
    currentProduct = p;
    card.querySelector("#product-name").textContent = p.name;
    card.querySelector("#product-meta").textContent =
      [p.brands, p.quantity].filter(Boolean).join(" · ") + " (via " + p.source + ")";
    const chips = $("#product-ingredients");
    chips.innerHTML = "";
    (p.ingredients || []).slice(0, 12).forEach((ing) => {
      const span = document.createElement("span");
      span.className = "chip";
      span.textContent = ing;
      chips.appendChild(span);
    });
    const warns = $("#product-warnings");
    warns.innerHTML = "";
    if (p.matched_ingredients.length) {
      const box = document.createElement("div");
      box.className = "warn-box";
      box.innerHTML = "<b>Ingredients of caution found:</b>";
      p.matched_ingredients.forEach((m) => {
        const line = document.createElement("div");
        line.style.marginTop = "6px";
        line.innerHTML =
          "• <b>" + escapeHtml(m.label) + "</b>" +
          (m.warns_against.length
            ? " — watch with: " + m.warns_against.map(escapeHtml).join(", ")
            : "");
        box.appendChild(line);
      });
      warns.appendChild(box);
    }
    $("#btn-add-product").disabled = false;
  } catch (err) {
    card.querySelector("#product-name").textContent = "Product not found";
    card.querySelector("#product-meta").textContent =
      "Try the ingredients search below, or check the barcode and retry.";
  }
}

$("#btn-add-product").addEventListener("click", () => {
  if (!currentProduct) return;
  const matched = currentProduct.matched_ingredients || [];
  if (matched.length) {
    matched.forEach((m) => {
      cabinetAdd({ kind: "herb", id: m.herb_id, label: m.label, source: currentProduct.name });
    });
  } else {
    cabinetAdd({
      kind: "product",
      id: "barcode:" + currentProduct.barcode,
      label: currentProduct.name,
      source: currentProduct.brands,
    });
  }
});

/* ---------- manual search ---------- */
$("#btn-search").addEventListener("click", doSearch);
$("#search-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") doSearch();
});

async function doSearch() {
  const q = $("#search-input").value.trim();
  if (!q) return;
  const box = $("#search-results");
  box.innerHTML = '<div class="empty-note">Searching…</div>';
  try {
    const res = await fetch("/api/search?q=" + encodeURIComponent(q));
    const data = await res.json();
    box.innerHTML = "";
    if (!data.results.length) {
      box.innerHTML =
        '<div class="empty-note">No match. Try the English or scientific name, e.g. "ginkgo", "sertraline".</div>';
      return;
    }
    data.results.forEach((r) => {
      const item = document.createElement("div");
      item.className = "result-item";
      const left = document.createElement("div");
      left.className = "label";
      left.textContent = r.label;
      const sub = document.createElement("div");
      sub.className = "sub";
      sub.textContent = r.kind === "herb" ? (r.scientific || "Supplement")
        : r.kind === "food" ? "Food & drink"
        : "Drug class — " + (r.examples || []).join(", ");
      left.appendChild(sub);
      const badge = document.createElement("span");
      badge.className = "kind-badge " + (r.kind === "herb" ? "kind-herb" : r.kind === "food" ? "kind-food" : "kind-drug");
      badge.textContent = r.kind === "herb" ? "Supplement" : r.kind === "food" ? "Food" : "Drug";
      const add = document.createElement("button");
      add.className = "btn";
      add.textContent = "Add";
      add.addEventListener("click", () => {
        cabinetAdd({ kind: r.kind, id: r.id, label: r.label, source: "manual" });
        box.innerHTML = "";
        $("#search-input").value = "";
      });
      item.append(left, badge, add);
      box.appendChild(item);
    });
  } catch {
    box.innerHTML = '<div class="empty-note">Server unreachable — is the backend running?</div>';
  }
}

/* ---------- cabinet view ---------- */
function renderCabinetCount() {
  $("#cabinet-count").textContent = cabinet.length;
}
function renderCabinet() {
  const list = $("#cabinet-list");
  list.innerHTML = "";
  if (!cabinet.length) {
    list.innerHTML =
      '<div class="empty-note">Your cabinet is empty.<br>Scan a product or search for supplements and drugs to add them.</div>';
    return;
  }
  cabinet.forEach((item, idx) => {
    const row = document.createElement("div");
    row.className = "cab-item";
    const name = document.createElement("span");
    name.className = "name";
    name.textContent = item.label;
    const badge = document.createElement("span");
    badge.className = "kind-badge " + (item.kind === "herb" ? "kind-herb" : item.kind === "food" ? "kind-food" : "kind-drug");
    badge.textContent = item.kind === "herb" ? "Supplement" : item.kind === "food" ? "Food" : item.kind === "drug_class" ? "Drug class" : "Product";
    const rm = document.createElement("button");
    rm.className = "remove";
    rm.title = "Remove";
    rm.textContent = "×";
    rm.addEventListener("click", () => cabinetRemove(idx));
    const time = document.createElement("select");
    time.className = "time-select";
    time.title = "When do you take this?";
    time.innerHTML = [
      ["", "Any time"],
      ["morning", "Morning"],
      ["midday", "Midday"],
      ["evening", "Evening"],
      ["bedtime", "Bedtime"],
    ].map(([v, label]) => `<option value="${v}">${label}</option>`).join("");
    time.value = item.time || "";
    time.addEventListener("change", () => {
      item.time = time.value || null;
      saveCabinet();
    });
    row.append(name, badge, time, rm);
    list.appendChild(row);
  });
}
$("#btn-check").addEventListener("click", () => goTab("check"));

/* ---------- check view ---------- */
async function runCheck() {
  const box = $("#check-content");
  if (!cabinet.length) {
    box.innerHTML =
      '<div class="card"><h2>Nothing to check yet</h2><p class="muted">Add your supplements and medications first.</p></div>';
    return;
  }
  box.innerHTML = '<div class="card"><div class="empty-note">Analyzing ' + cabinet.length + " items…</div></div>";
  try {
    const payload = cabinet.map((c) =>
      c.kind === "herb" || c.kind === "drug_class" || c.kind === "food"
        ? { name: c.label, kind: c.kind, matched: { kind: c.kind, id: c.id }, time: c.time || null }
        : { name: c.label }
    );
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: payload }),
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    renderCheckResults(data);
  } catch {
    box.innerHTML = '<div class="card"><div class="empty-note">Server unreachable — is the backend running?</div></div>';
  }
}
function renderCheckResults(data) {
  const box = $("#check-content");
  box.innerHTML = "";

  const head = document.createElement("div");
  head.className = "card";
  const h2 = document.createElement("h2");
  const major = data.interactions.filter((i) => i.severity === "major").length;
  const moderate = data.interactions.filter((i) => i.severity === "moderate").length;
  const minor = data.interactions.filter((i) => i.severity === "minor").length;
  const evidence = data.interactions.length - major - moderate - minor;
  if (!data.interactions.length) {
    h2.textContent = "No known interactions";
    const ok = document.createElement("div");
    ok.className = "ok-box";
    ok.textContent = "✓ No documented interactions were found among these items.";
    head.append(h2, ok);
  } else {
    h2.textContent = major
      ? major + " serious warning" + (major > 1 ? "s" : "") + " found"
      : "Interaction summary";
    const summary = document.createElement("p");
    summary.className = "muted";
    summary.textContent = major + " major · " + moderate + " moderate · " + minor + " minor"
      + (evidence ? " · " + evidence + " evidence-based" : "");
    head.append(h2, summary);
  }
  box.appendChild(head);

  if (data.unmatched.length) {
    const card = document.createElement("div");
    card.className = "card";
    const h3 = document.createElement("h3");
    h3.textContent = "Could not identify";
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = "These items were not recognized — check spelling or add them via search:";
    const chips = document.createElement("div");
    chips.className = "chips";
    data.unmatched.forEach((u) => {
      const span = document.createElement("span");
      span.className = "chip";
      span.textContent = u;
      chips.appendChild(span);
    });
    card.append(h3, p, chips);
    box.appendChild(card);
  }
  const sevOrder = { major: 0, moderate: 1, minor: 2, evidence: 3 };
  data.interactions
    .slice()
    .sort((a, b) => (sevOrder[a.severity ?? "evidence"] ?? 3) - (sevOrder[b.severity ?? "evidence"] ?? 3))
    .forEach((inter) => box.appendChild(renderInteraction(inter)));


  if (data.depletions && data.depletions.length) {
    const depCard = document.createElement("div");
    depCard.className = "card";
    const h3 = document.createElement("h3");
    h3.textContent = "Nutrient depletion watch";
    const sub = document.createElement("p");
    sub.className = "muted";
    sub.textContent = "These medications may deplete nutrients over time — worth discussing supplementation with your doctor.";
    depCard.append(h3, sub);
    data.depletions.forEach((d) => {
      const row = document.createElement("div");
      row.className = "depletion";
      const sevCls = { major: "sev-major", moderate: "sev-warn", minor: "sev-minor" }[d.severity] || "sev-minor";
      const sev = document.createElement("span");
      sev.className = "sev " + sevCls;
      sev.textContent = d.severity;
      const label = document.createElement("span");
      label.className = "dep-label";
      label.textContent = "May deplete " + d.ingredient + (d.effect_size ? " (" + d.effect_size + ")" : "");
      const mech = document.createElement("div");
      mech.className = "dep-mech";
      mech.textContent = d.mechanism || "";
      row.append(sev, label);
      depCard.append(row, mech);
    });
    box.appendChild(depCard);
  }

  const fda = document.createElement("div");
  fda.className = "card";
  const p = document.createElement("p");
  p.className = "muted small";
  p.innerHTML =
    "<i>This statement has not been evaluated by the Food and Drug Administration. This product is not intended to diagnose, treat, cure, or prevent any disease.</i>";
  fda.appendChild(p);
  box.appendChild(fda);

  const save = document.createElement("div");
  save.className = "card no-print";
  const btn = document.createElement("button");
  btn.className = "btn primary wide";
  btn.textContent = "Print / Save as PDF";
  btn.addEventListener("click", () => window.print());
  save.appendChild(btn);
  box.appendChild(save);
}

function renderInteraction(inter) {
  const isEvidence = inter.type === "herb-drug-evidence" || !inter.severity;
  const card = document.createElement("div");
  card.className = "interaction " + (isEvidence ? "evidence" : inter.severity);

  const head = document.createElement("div");
  head.className = "head";
  const pair = document.createElement("span");
  pair.className = "pair";
  pair.textContent = inter.a.label + " × " + inter.b.label;
  const sev = document.createElement("span");
  sev.className = "sev " + (isEvidence ? "sev-evidence" : "sev-" + inter.severity);
  sev.textContent = isEvidence ? "Evidence-based" : inter.severity;
  head.append(pair, sev);

  if (isEvidence) {
    const papers = Array.isArray(inter.evidence) ? inter.evidence : [];
    const first = papers[0];
    const effect = document.createElement("p");
    effect.className = "effect";
    effect.textContent = inter.description
      ? inter.description
      : first
        ? (first.year ? first.year + " — " : "") + (first.title || "See evidence")
        : inter.drug_name
          ? "Documented interaction with " + inter.drug_name + "."
          : "Documented interaction.";
    const list = document.createElement("div");
    list.className = "papers";
    papers.forEach((p) => {
      const row = document.createElement("a");
      row.className = "paper";
      row.href = p.doi ? "https://doi.org/" + p.doi : "https://pubmed.ncbi.nlm.nih.gov/" + p.pmid;
      row.target = "_blank";
      row.rel = "noopener";
      row.textContent = (p.title || "Paper") + (p.year ? " (" + p.year + ")" : "");
      list.appendChild(row);
    });
    const meta = document.createElement("div");
    meta.className = "meta";
    meta.textContent = "Source: " + (inter.source || "SUPP.AI")
      + (inter.rating ? " · Rating: " + inter.rating : "")
      + (inter.trust != null ? " · Trust: " + inter.trust : "");
    const timing = timingNote(inter);
    card.append(head, effect, list, meta, timing);
    return card;
  }

  const effect = document.createElement("p");
  effect.className = "effect";
  effect.textContent = inter.effect || "";

  const mech = document.createElement("p");
  mech.className = "mech";
  mech.innerHTML = "<b>Why:</b> " + escapeHtml(inter.mechanism || "");

  const meta = document.createElement("div");
  meta.className = "meta";
  const bits = [];
  if (inter.evidence) bits.push("Evidence: " + inter.evidence);
  if (inter.source) bits.push("Source: " + inter.source);
  if (inter.doi) bits.push("DOI: " + inter.doi);
  if (inter.trust != null) bits.push("Trust: " + inter.trust);
  meta.textContent = bits.join(" · ");
  const action = document.createElement("div");
  action.className = "action action-" + inter.severity;
  action.textContent = inter.action || "";

  const timing = timingNote(inter);
  card.append(head, effect, mech, meta, action, ...(timing ? [timing] : []));
  return card;
}

function timingNote(inter) {
  if (inter.timing !== "separated") return null;
  const note = document.createElement("div");
  note.className = "timing-note";
  note.textContent = "Timing: you take these at different times of day — separating doses by 2+ hours reduces this risk.";
  return note;
}


/* ---------- review queue (pharmacist triage) ---------- */
let reviewNote = "";

async function loadReview() {
  const box = $("#review-content");
  try {
    const res = await fetch("/api/review/next");
    const item = await res.json();
    if (!item.id) {
      box.innerHTML = '<div class="ok-box">✓ Queue clear — nothing left to review.</div>';
      return;
    }
    box.innerHTML = "";
    const pair = document.createElement("p");
    pair.className = "pair";
    pair.textContent = item.a_label + " × " + item.b_label;
    const mech = document.createElement("p");
    mech.className = "muted";
    mech.textContent = (item.mechanism || "") + " · trust " + item.trust;
    const note = document.createElement("input");
    note.type = "text";
    note.placeholder = "Note (optional, e.g. citation)";
    note.value = reviewNote;
    note.addEventListener("input", () => (reviewNote = note.value));
    const row = document.createElement("div");
    row.className = "row";
    const okBtn = document.createElement("button");
    okBtn.className = "btn primary";
    okBtn.textContent = "✓ Verify";
    okBtn.addEventListener("click", async () => {
      await fetch("/api/review/" + item.id + "?status=verified&note=" + encodeURIComponent(reviewNote), { method: "POST" });
      reviewNote = "";
      loadReview();
    });
    const rejBtn = document.createElement("button");
    rejBtn.className = "btn";
    rejBtn.textContent = "✗ Reject";
    rejBtn.addEventListener("click", async () => {
      await fetch("/api/review/" + item.id + "?status=rejected&note=" + encodeURIComponent(reviewNote), { method: "POST" });
      reviewNote = "";
      loadReview();
    });
    row.append(okBtn, rejBtn);
    box.append(pair, mech, note, row);
  } catch {
    box.innerHTML = '<div class="empty-note">Server unreachable.</div>';
  }
}

/* ---------- utils ---------- */
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

let flashTimer = null;
function flash(msg) {
  const hint = $("#camera-hint");
  hint.textContent = msg;
  clearTimeout(flashTimer);
  flashTimer = setTimeout(() => {
    if (stream) hint.textContent = "Aim the camera at the barcode…";
    else hint.textContent = "";
  }, 2500);
}

/* ---------- init ---------- */
renderProfiles();
renderCabinetCount();
renderCabinet();
