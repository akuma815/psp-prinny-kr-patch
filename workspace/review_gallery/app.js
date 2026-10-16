(() => {
  "use strict";
  const dataset = window.REVIEW_DATA;
  const storageKey = "prinny-image-review-v1";
  const preferencesKey = "prinny-image-gallery-prefs-v1";
  const $ = (id) => document.getElementById(id);
  const controls = {
    search: $("searchInput"), bind: $("bindFilter"), review: $("reviewFilter"),
    group: $("groupFilter"), view: $("viewMode"), zoom: $("zoomMode"),
    duplicate: $("duplicateOnly"), pixelated: $("pixelatedToggle")
  };
  let reviews = loadJson(storageKey, {});

  function loadJson(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key)) || fallback; }
    catch (_) { return fallback; }
  }
  function reviewFor(id) {
    const item = dataset.items.find((entry) => entry.asset_id === id);
    return reviews[id] || item?.initial_review || { status: "pending", note: "" };
  }
  function saveReviews() {
    localStorage.setItem(storageKey, JSON.stringify(reviews));
    updateSummary();
  }
  function savePreferences() {
    const prefs = Object.fromEntries(Object.entries(controls).map(([key, node]) => [
      key, node.type === "checkbox" ? node.checked : node.value
    ]));
    localStorage.setItem(preferencesKey, JSON.stringify(prefs));
  }
  function restorePreferences() {
    const prefs = loadJson(preferencesKey, {});
    Object.entries(prefs).forEach(([key, value]) => {
      const node = controls[key];
      if (!node) return;
      if (node.type === "checkbox") node.checked = Boolean(value);
      else node.value = value;
    });
  }
  function updateSummary() {
    const statusCounts = { pending: 0, approved: 0, needs_fix: 0 };
    dataset.items.forEach((item) => statusCounts[reviewFor(item.asset_id).status]++);
    $("summary").innerHTML = [
      ["전체 추출", dataset.summary.inventory_total],
      ["번역 대상", dataset.summary.target_asset_count],
      ["고유 번역본", dataset.summary.unique_replacement_count],
      ["PPSSPP 적용 가능", dataset.summary.installed_or_aliased_asset_count],
      ["덤프 대기", dataset.summary.staged_until_dump_asset_count],
      ["승인 / 수정", `${statusCounts.approved} / ${statusCounts.needs_fix}`]
    ].map(([label, value]) => `<div class="stat"><strong>${value}</strong><span>${label}</span></div>`).join("");
  }
  function setupGroups() {
    [...new Set(dataset.items.map((item) => item.group))].sort().forEach((group) => {
      const option = document.createElement("option");
      option.value = group;
      option.textContent = group;
      controls.group.append(option);
    });
  }
  function filteredItems() {
    const q = controls.search.value.trim().toLocaleLowerCase("ko");
    return dataset.items.filter((item) => {
      const review = reviewFor(item.asset_id);
      const haystack = `${item.asset_id} ${item.label} ${item.group}`.toLocaleLowerCase("ko");
      return (!q || haystack.includes(q))
        && (controls.bind.value === "all" || item.bind_status === controls.bind.value)
        && (controls.review.value === "all" || review.status === controls.review.value)
        && (controls.group.value === "all" || item.group === controls.group.value)
        && (!controls.duplicate.checked || Boolean(item.duplicate_of));
    });
  }
  function render() {
    savePreferences();
    const items = filteredItems();
    $("resultCount").textContent = `${items.length}개`;
    $("emptyState").hidden = items.length !== 0;
    $("gallery").innerHTML = "";
    const fragment = document.createDocumentFragment();
    items.forEach((item) => fragment.append(buildCard(item)));
    $("gallery").append(fragment);
  }
  function buildCard(item) {
    const review = reviewFor(item.asset_id);
    const card = document.createElement("article");
    card.className = "card";
    card.dataset.review = review.status;
    const bindLabel = item.bind_status === "installed_or_aliased" ? "PPSSPP 적용 가능" : "덤프 대기";
    const bindClass = item.bind_status === "installed_or_aliased" ? "live" : "wait";
    const viewClass = controls.view.value === "original" ? "original-only" : controls.view.value === "translated" ? "translated-only" : "";
    card.innerHTML = `
      <div class="card-head">
        <div><p class="eyebrow">${escapeHtml(item.group)}</p><h2>${escapeHtml(item.label)}</h2><code class="asset-id">${escapeHtml(item.asset_id)}</code></div>
        <div class="chips"><span class="chip ${bindClass}">${bindLabel}</span><span class="chip">${item.width}×${item.height}</span></div>
      </div>
      <div class="image-grid ${viewClass}">
        ${imageFigure("원본", "original", item.original, item)}
        ${imageFigure("초벌 번역", "translated", item.translated, item)}
      </div>
      <div class="card-foot">
        <select class="review-select" aria-label="검수 상태">
          <option value="pending">미검수</option><option value="approved">승인</option><option value="needs_fix">수정 필요</option>
        </select>
        <textarea placeholder="수정 메모" aria-label="검수 메모"></textarea>
        ${item.duplicate_of ? `<p class="duplicate-note">동일 번역본: ${escapeHtml(item.duplicate_of)}</p>` : ""}
      </div>`;
    const select = card.querySelector(".review-select");
    const note = card.querySelector("textarea");
    select.value = review.status;
    note.value = review.note || "";
    select.addEventListener("change", () => {
      reviews[item.asset_id] = { status: select.value, note: note.value };
      card.dataset.review = select.value;
      saveReviews();
      if (controls.review.value !== "all") render();
    });
    note.addEventListener("change", () => {
      reviews[item.asset_id] = { status: select.value, note: note.value };
      saveReviews();
    });
    card.querySelectorAll(".image-box").forEach((node) => node.addEventListener("click", () => openCompare(item)));
    return card;
  }
  function imageFigure(label, className, src, item) {
    const zoom = controls.zoom.value === "fit" ? "" : `zoom-${controls.zoom.value}`;
    const pixelated = controls.pixelated.checked ? "pixelated" : "";
    return `<figure class="${className}"><figcaption>${label}</figcaption><div class="image-box ${zoom} ${pixelated}">
      <img src="${src}" width="${item.width}" height="${item.height}" loading="lazy" alt="${escapeHtml(item.label)} ${label}">
    </div></figure>`;
  }
  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[char]);
  }
  function openCompare(item) {
    $("dialogGroup").textContent = item.group;
    $("dialogTitle").textContent = item.label;
    $("dialogAsset").textContent = item.asset_id;
    $("dialogOriginalImage").src = item.original;
    $("dialogTranslatedImage").src = item.translated;
    setOverlay(50);
    $("compareDialog").showModal();
  }
  function setOverlay(value) {
    $("overlayRange").value = value;
    $("dialogOriginalImage").style.opacity = String(value / 100);
  }
  function exportReviews() {
    const result = {
      schema_version: 1,
      generated_at: new Date().toISOString(),
      source_generated_at: dataset.generated_at,
      summary: dataset.summary,
      entries: dataset.items.map((item) => ({
        asset_id: item.asset_id, label: item.label,
        status: reviewFor(item.asset_id).status, note: reviewFor(item.asset_id).note || ""
      }))
    };
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `prinny-image-review-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  setupGroups();
  restorePreferences();
  Object.values(controls).forEach((node) => node.addEventListener("input", render));
  $("exportButton").addEventListener("click", exportReviews);
  $("resetButton").addEventListener("click", () => {
    localStorage.removeItem(preferencesKey);
    location.reload();
  });
  $("closeDialog").addEventListener("click", () => $("compareDialog").close());
  $("overlayRange").addEventListener("input", (event) => setOverlay(Number(event.target.value)));
  $("dialogOriginal").addEventListener("click", () => setOverlay(100));
  $("dialogHalf").addEventListener("click", () => setOverlay(50));
  $("dialogTranslated").addEventListener("click", () => setOverlay(0));
  $("compareDialog").addEventListener("click", (event) => {
    if (event.target === $("compareDialog")) $("compareDialog").close();
  });
  updateSummary();
  render();
})();
