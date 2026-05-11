"use strict";

const gate = document.getElementById("gate");
const shell = document.getElementById("shell");
const gateError = document.getElementById("gate-error");
const gateSetup = document.getElementById("gate-setup");
const passwordInput = document.getElementById("password-input");
const unlockBtn = document.getElementById("unlock-btn");
const grid = document.getElementById("grid");
const loading = document.getElementById("loading");
const emptyMsg = document.getElementById("empty");
const detailPanel = document.getElementById("detail-panel");
const detailContent = document.getElementById("detail-content");
const contentBody = document.getElementById("content-body");
const searchInput = document.getElementById("search");
const updatedAt = document.getElementById("updated-at");
const filterBar = document.getElementById("filter-bar");
const progressText = document.getElementById("progress-text");
const progressFill = document.getElementById("progress-fill");

let allVideos = [];
let siteConfig = {};

// ── Reading Progress ──────────────────────────────────────────────────
const READ_KEY = "yt-digest-read";
let readIds = new Set(JSON.parse(localStorage.getItem(READ_KEY) || "[]"));

function markRead(videoId) {
  if (readIds.has(videoId)) return;
  readIds.add(videoId);
  localStorage.setItem(READ_KEY, JSON.stringify([...readIds]));
  const card = grid.querySelector(`[data-id="${esc(videoId)}"]`);
  if (card) {
    card.classList.add("card-read");
    const top = card.querySelector(".card-top");
    if (top && !top.querySelector(".read-badge")) {
      top.insertAdjacentHTML("beforeend", `<span class="read-badge">✓</span>`);
    }
  }
  updateStats();
}

function markUnread(videoId) {
  readIds.delete(videoId);
  localStorage.setItem(READ_KEY, JSON.stringify([...readIds]));
  const card = grid.querySelector(`[data-id="${esc(videoId)}"]`);
  if (card) {
    card.classList.remove("card-read");
    card.querySelector(".read-badge")?.remove();
  }
  updateStats();
}

function updateStats() {
  const total = allVideos.length;
  const read = allVideos.filter(v => readIds.has(v.video_id)).length;
  progressText.textContent = `${read} / ${total} read`;
  progressFill.style.width = total ? `${(read / total) * 100}%` : "0%";
}

// ── Bookmarks ─────────────────────────────────────────────────────────
const BOOKMARK_KEY = "yt-digest-bookmarks";
let bookmarkIds = new Set(JSON.parse(localStorage.getItem(BOOKMARK_KEY) || "[]"));

function toggleBookmark(videoId) {
  if (bookmarkIds.has(videoId)) {
    bookmarkIds.delete(videoId);
  } else {
    bookmarkIds.add(videoId);
  }
  localStorage.setItem(BOOKMARK_KEY, JSON.stringify([...bookmarkIds]));
}

// ── Duration helpers ──────────────────────────────────────────────────
function parseDurationToMinutes(dur) {
  if (!dur) return 0;
  let mins = 0;
  const h = dur.match(/(\d+)h/);
  const m = dur.match(/(\d+)m/);
  const s = dur.match(/(\d+)s/);
  if (h) mins += parseInt(h[1]) * 60;
  if (m) mins += parseInt(m[1]);
  if (s) mins += parseInt(s[1]) / 60;
  return mins;
}

function getLengthCategory(mins) {
  if (mins < 3)  return { label: "Quick",     cls: "len-quick",  key: "quick" };
  if (mins < 10) return { label: "Short",     cls: "len-short",  key: "short" };
  if (mins < 25) return { label: "Medium",    cls: "len-medium", key: "medium" };
  return             { label: "Deep Dive", cls: "len-deep",   key: "deep" };
}

// ── Sort ──────────────────────────────────────────────────────────────
let activeSortOrder = "date-desc";
const importanceOrder = { high: 0, medium: 1, low: 2 };

function sortVideos(videos) {
  return [...videos].sort((a, b) => {
    switch (activeSortOrder) {
      case "date-asc":    return new Date(a.published_at) - new Date(b.published_at);
      case "importance":  return (importanceOrder[a.importance] ?? 1) - (importanceOrder[b.importance] ?? 1);
      case "views":       return parseInt(b.view_count || 0) - parseInt(a.view_count || 0);
      case "length-desc": return parseDurationToMinutes(b.duration) - parseDurationToMinutes(a.duration);
      case "length-asc":  return parseDurationToMinutes(a.duration) - parseDurationToMinutes(b.duration);
      default:            return new Date(b.published_at) - new Date(a.published_at);
    }
  });
}

// ── Weekly Grouping ───────────────────────────────────────────────────
function getWeekLabel(dateStr) {
  const d = new Date(dateStr);
  const now = new Date();
  const diffDays = Math.floor((now - d) / 86400000);
  if (diffDays < 7)  return "This Week";
  if (diffDays < 14) return "Last Week";
  return d.toLocaleDateString(undefined, { month: "long", year: "numeric" });
}

function groupByWeek(videos) {
  const groups = new Map();
  for (const v of videos) {
    const label = getWeekLabel(v.published_at);
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label).push(v);
  }
  return groups;
}

// ── Channel List ──────────────────────────────────────────────────────
let activeChannel = "";

function buildChannelList() {
  const channelList = document.getElementById("channel-list");
  const counts = {};
  for (const v of allVideos) {
    const key = v.channel_handle || v.channel_title;
    if (!counts[key]) counts[key] = { title: v.channel_title, handle: key, count: 0 };
    counts[key].count++;
  }
  const channels = Object.values(counts).sort((a, b) => b.count - a.count);

  let html = `<div class="channel-item${!activeChannel ? " active" : ""}" data-handle="">
    <span class="channel-name">All Channels</span>
    <span class="channel-count">${allVideos.length}</span>
  </div>`;
  for (const ch of channels) {
    html += `<div class="channel-item${activeChannel === ch.handle ? " active" : ""}" data-handle="${esc(ch.handle)}">
      <span class="channel-name">${esc(ch.title)}</span>
      <span class="channel-count">${ch.count}</span>
    </div>`;
  }
  channelList.innerHTML = html;

  channelList.querySelectorAll(".channel-item").forEach(item => {
    item.addEventListener("click", () => {
      activeChannel = item.dataset.handle;
      channelList.querySelectorAll(".channel-item").forEach(i => i.classList.toggle("active", i === item));
      closeDetail();
      applyFilters();
    });
  });
}

// ── Filter State ──────────────────────────────────────────────────────
let activeReadFilter = "all";
let activeLengthFilter = "";

function applyFilters() {
  const q = searchInput.value.toLowerCase().trim();
  let videos = allVideos;

  if (activeChannel) {
    videos = videos.filter(v => (v.channel_handle || v.channel_title) === activeChannel);
  }
  if (activeReadFilter === "unread") {
    videos = videos.filter(v => !readIds.has(v.video_id));
  } else if (activeReadFilter === "bookmarked") {
    videos = videos.filter(v => bookmarkIds.has(v.video_id));
  }
  if (activeLengthFilter) {
    videos = videos.filter(v => getLengthCategory(parseDurationToMinutes(v.duration)).key === activeLengthFilter);
  }
  if (q) {
    videos = videos.filter(v =>
      v.title.toLowerCase().includes(q) ||
      (v.topics || []).some(t => t.toLowerCase().includes(q)) ||
      v.channel_title.toLowerCase().includes(q) ||
      (v.executive_summary || "").toLowerCase().includes(q)
    );
  }
  renderGrid(videos);
}

// ── Related Videos ────────────────────────────────────────────────────
function getRelatedVideos(videoId, topics) {
  if (!topics || !topics.length) return [];
  return allVideos
    .filter(v => v.video_id !== videoId)
    .map(v => ({ ...v, overlap: (v.topics || []).filter(t => topics.includes(t)).length }))
    .filter(v => v.overlap > 0)
    .sort((a, b) => b.overlap - a.overlap)
    .slice(0, 3);
}

// ── Auth ──────────────────────────────────────────────────────────────
async function sha256(str) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(str));
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, "0")).join("");
}

async function init() {
  try {
    const resp = await fetch("config.json");
    siteConfig = await resp.json();
  } catch {
    siteConfig = { passwordHash: "" };
  }
  if (!siteConfig.passwordHash) {
    gateSetup.classList.remove("hidden");
    unlockBtn.disabled = true;
    return;
  }
  if (sessionStorage.getItem("yt-digest-auth") === siteConfig.passwordHash) {
    showApp();
  }
}

async function tryUnlock() {
  const pw = passwordInput.value;
  if (!pw) return;
  const hash = await sha256(pw);
  if (hash === siteConfig.passwordHash) {
    sessionStorage.setItem("yt-digest-auth", hash);
    gateError.classList.add("hidden");
    showApp();
  } else {
    gateError.classList.remove("hidden");
    passwordInput.value = "";
    passwordInput.focus();
  }
}

function showApp() {
  gate.classList.add("hidden");
  shell.classList.remove("hidden");
  loadVideos();
}

async function loadVideos() {
  try {
    const resp = await fetch(`data/index.json?t=${Date.now()}`);
    const data = await resp.json();
    allVideos = data.videos || [];
  } catch {
    allVideos = [];
  }
  loading.classList.add("hidden");
  if (allVideos.length === 0) {
    emptyMsg.classList.remove("hidden");
    return;
  }
  if (siteConfig.updatedAt) {
    updatedAt.textContent = `Updated ${new Date(siteConfig.updatedAt).toLocaleString()}`;
  }
  filterBar.classList.remove("hidden");
  buildChannelList();
  loadMonthlyIndex();
  updateStats();
  applyFilters();
}

// ── Monthly Digests ───────────────────────────────────────────────────
async function loadMonthlyIndex() {
  const monthlyList = document.getElementById("monthly-list");
  try {
    const resp = await fetch(`data/monthly/index.json?t=${Date.now()}`);
    if (!resp.ok) throw new Error("not found");
    const data = await resp.json();
    buildMonthlyList(data.months || []);
  } catch {
    monthlyList.innerHTML = "<div class='rail-empty'>Run monthly summary script first</div>";
  }
}

function buildMonthlyList(months) {
  const monthlyList = document.getElementById("monthly-list");
  if (!months.length) {
    monthlyList.innerHTML = "<div class='rail-empty'>No monthly digests yet</div>";
    return;
  }
  monthlyList.innerHTML = months.map(m => `
    <div class="channel-item" data-month="${esc(m.month)}">
      <span class="channel-name">${esc(m.label)}</span>
      <span class="channel-count">${m.video_count}</span>
    </div>`).join("");

  monthlyList.querySelectorAll(".channel-item").forEach(item => {
    item.addEventListener("click", () => {
      document.querySelectorAll("#monthly-list .channel-item, #channel-list .channel-item")
        .forEach(i => i.classList.remove("active"));
      item.classList.add("active");
      openMonthlyDetail(item.dataset.month);
    });
  });
}

async function openMonthlyDetail(ym) {
  detailContent.innerHTML = '<p style="color:var(--text-muted);padding:2rem 0;text-align:center">Loading…</p>';
  detailPanel.classList.add("open");
  contentBody.classList.add("detail-open");
  grid.querySelectorAll(".card").forEach(c => c.classList.remove("card-active"));

  let m;
  try {
    const resp = await fetch(`data/monthly/${ym}.json?t=${Date.now()}`);
    m = await resp.json();
  } catch {
    detailContent.innerHTML = '<p style="color:var(--accent)">Failed to load monthly digest.</p>';
    return;
  }

  const themesHTML = (m.key_themes || []).map(t => `<li>${esc(t)}</li>`).join("");
  const developmentsHTML = (m.major_developments || []).map(d => `<li>${esc(d)}</li>`).join("");
  const mustReadsHTML = (m.must_reads || []).map(r => `
    <div class="related-item" data-id="${esc(r.video_id || "")}">
      <div class="related-body">
        <div class="related-title">${esc(r.title || "")}</div>
        <div class="related-meta">${esc(r.why || "")}</div>
      </div>
    </div>`).join("");
  const takeawaysHTML = (m.key_takeaways || []).map(t => `<li>${esc(t)}</li>`).join("");
  const topicsHTML = Object.entries(m.topics_breakdown || {})
    .sort(([, a], [, b]) => b - a).slice(0, 10)
    .map(([topic, count]) => `<span class="tag">${esc(topic)} <span style="opacity:0.6">${count}</span></span>`)
    .join("");

  detailContent.innerHTML = `
    <div style="margin-bottom:1.2rem">
      <div class="detail-channel">Monthly Digest</div>
      <div class="detail-title">${esc(m.label || ym)}</div>
      <div class="detail-meta"><span>${m.video_count} videos</span></div>
      <div class="detail-topics" style="margin-top:0.5rem">${topicsHTML}</div>
    </div>

    ${m.executive_summary ? `<div class="exec-summary">${esc(m.executive_summary)}</div>` : ""}

    ${themesHTML ? `
    <div class="section">
      <div class="section-title">Key Themes This Month</div>
      <ul class="video-bullets">${themesHTML}</ul>
    </div>` : ""}

    ${developmentsHTML ? `
    <div class="section">
      <div class="section-title">Major Developments</div>
      <ul class="takeaways">${developmentsHTML}</ul>
    </div>` : ""}

    ${mustReadsHTML ? `
    <div class="section">
      <div class="section-title">Must-Read Videos This Month</div>
      <div class="related-list">${mustReadsHTML}</div>
    </div>` : ""}

    ${takeawaysHTML ? `
    <div class="section">
      <div class="section-title">What To Do This Month</div>
      <ul class="takeaways">${takeawaysHTML}</ul>
    </div>` : ""}
  `;

  detailContent.querySelectorAll(".related-item[data-id]").forEach(item => {
    if (item.dataset.id) item.addEventListener("click", () => openDetail(item.dataset.id));
  });
}

// ── Render ────────────────────────────────────────────────────────────
function renderGrid(videos) {
  grid.innerHTML = "";
  if (videos.length === 0) {
    emptyMsg.classList.remove("hidden");
    return;
  }
  emptyMsg.classList.add("hidden");

  const sorted = sortVideos(videos);
  const useGroups = activeSortOrder === "date-desc" || activeSortOrder === "date-asc";

  if (useGroups) {
    grid.classList.remove("grid-2col");
    const groups = groupByWeek(sorted);
    let html = "";
    for (const [label, groupVideos] of groups) {
      html += `<div class="week-group">
        <div class="week-header">${esc(label)} <span class="week-count">${groupVideos.length}</span></div>
        <div class="grid-inner">${groupVideos.map(cardHTML).join("")}</div>
      </div>`;
    }
    grid.innerHTML = html;
  } else {
    grid.classList.add("grid-2col");
    grid.innerHTML = sorted.map(cardHTML).join("");
  }

  setupGridListeners();
}

function setupGridListeners() {
  grid.querySelectorAll(".card").forEach(card => {
    card.addEventListener("click", e => {
      if (e.target.closest(".bookmark-btn")) return;
      openDetail(card.dataset.id);
    });
    card.addEventListener("keydown", e => {
      if ((e.key === "Enter" || e.key === " ") && !e.target.closest(".bookmark-btn")) {
        openDetail(card.dataset.id);
      }
    });
  });

  grid.querySelectorAll(".bookmark-btn").forEach(btn => {
    btn.addEventListener("click", e => {
      e.stopPropagation();
      toggleBookmark(btn.dataset.id);
      const starred = bookmarkIds.has(btn.dataset.id);
      btn.textContent = starred ? "★" : "☆";
      btn.classList.toggle("bookmarked", starred);
      if (activeReadFilter === "bookmarked") applyFilters();
    });
  });
}

function cardHTML(v) {
  const date = new Date(v.published_at).toLocaleDateString(undefined, {
    year: "numeric", month: "short", day: "numeric",
  });
  const importance = v.importance || "medium";
  const excerpt = v.executive_summary || "";
  const topics = (v.topics || []).slice(0, 4).map(t => `<span class="tag">${esc(t)}</span>`).join("");
  const thumb = v.thumbnail
    ? `<img class="card-thumb" src="${esc(v.thumbnail)}" alt="" loading="lazy" />`
    : `<div class="card-thumb"></div>`;

  const lenCat = getLengthCategory(parseDurationToMinutes(v.duration));
  const isRead = readIds.has(v.video_id);
  const isBookmarked = bookmarkIds.has(v.video_id);

  return `
    <article class="card${isRead ? " card-read" : ""}" data-id="${esc(v.video_id)}" role="button" tabindex="0" aria-label="${esc(v.title)}">
      <div class="card-thumb-wrap">${thumb}</div>
      <div class="card-body">
        <div class="card-top">
          <span class="card-channel">${esc(v.channel_title)}</span>
          <span class="card-dot">·</span>
          <span class="card-date">${date}</span>
          ${v.duration ? `<span class="card-dot">·</span><span class="card-duration">${esc(v.duration)}</span>` : ""}
          <span class="importance importance-${importance}">${importance}</span>
          <span class="len-badge ${lenCat.cls}">${esc(lenCat.label)}</span>
          ${isRead ? `<span class="read-badge">✓</span>` : ""}
          <button class="bookmark-btn${isBookmarked ? " bookmarked" : ""}" data-id="${esc(v.video_id)}" title="${isBookmarked ? "Remove bookmark" : "Save for later"}">${isBookmarked ? "★" : "☆"}</button>
        </div>
        <div class="card-title">${esc(v.title)}</div>
        ${excerpt ? `<div class="card-excerpt">${esc(excerpt)}</div>` : ""}
        <div class="topics">${topics}</div>
      </div>
    </article>`;
}

// ── Detail Panel ──────────────────────────────────────────────────────
async function openDetail(videoId) {
  detailContent.innerHTML = '<p style="color:var(--text-muted);padding:2rem 0;text-align:center">Loading…</p>';
  detailPanel.classList.add("open");
  contentBody.classList.add("detail-open");
  grid.querySelectorAll(".card").forEach(c => c.classList.remove("card-active"));
  const activeCard = grid.querySelector(`[data-id="${esc(videoId)}"]`);
  if (activeCard) activeCard.classList.add("card-active");

  markRead(videoId);

  let v;
  try {
    const resp = await fetch(`data/${videoId}.json?t=${Date.now()}`);
    v = await resp.json();
  } catch {
    detailContent.innerHTML = '<p style="color:var(--accent)">Failed to load details.</p>';
    return;
  }

  const date = new Date(v.published_at).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
  const importance = v.importance || "medium";
  const lenCat = getLengthCategory(parseDurationToMinutes(v.duration));
  const isBookmarked = bookmarkIds.has(v.video_id);

  const topicsHTML = (v.topics || []).map(t => `<span class="tag">${esc(t)}</span>`).join("");
  const bulletsHTML = (v.bullets || []).map(b => `<li>${esc(b)}</li>`).join("");
  const takeawaysHTML = (v.key_takeaways || []).map(t => `<li>${esc(t)}</li>`).join("");
  const termsHTML = Object.entries(v.technical_terms || {})
    .map(([term, def]) => `<div class="term"><div class="term-name">${esc(term)}</div><div class="term-def">${esc(def)}</div></div>`).join("");
  const refsHTML = (v.external_references || []).filter(r => r.url && r.title)
    .map(r => `<div class="ref"><div class="ref-icon">↗</div><div class="ref-body"><div class="ref-title"><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a></div>${r.why_relevant ? `<div class="ref-why">${esc(r.why_relevant)}</div>` : ""}</div></div>`).join("");

  const related = getRelatedVideos(videoId, v.topics);
  const relatedHTML = related.length ? `
    <div class="section">
      <div class="section-title">Related Videos</div>
      <div class="related-list">
        ${related.map(r => `
          <div class="related-item" data-id="${esc(r.video_id)}">
            ${r.thumbnail ? `<img class="related-thumb" src="${esc(r.thumbnail)}" alt="" />` : ""}
            <div class="related-body">
              <div class="related-title">${esc(r.title)}</div>
              <div class="related-meta">${new Date(r.published_at).toLocaleDateString()} · ${esc(r.duration || "")}</div>
            </div>
          </div>`).join("")}
      </div>
    </div>` : "";

  detailContent.innerHTML = `
    <div class="detail-header">
      ${v.thumbnail ? `<img class="detail-thumb" src="${esc(v.thumbnail)}" alt="" />` : ""}
      <div class="detail-header-text">
        <div class="detail-channel">${esc(v.channel_title)}</div>
        <div class="detail-title">${esc(v.title)}</div>
        <div class="detail-meta">
          <span>${date}</span>
          ${v.duration ? `<span>· ${esc(v.duration)}</span>` : ""}
          ${v.view_count ? `<span>· ${Number(v.view_count).toLocaleString()} views</span>` : ""}
          <span class="importance importance-${importance}">${importance} importance</span>
          <span class="len-badge ${lenCat.cls}">${esc(lenCat.label)}</span>
          <button class="bookmark-btn${isBookmarked ? " bookmarked" : ""}" id="detail-bookmark" data-id="${esc(videoId)}" title="${isBookmarked ? "Remove bookmark" : "Save for later"}">${isBookmarked ? "★" : "☆"}</button>
          <a href="${esc(v.url)}" target="_blank" rel="noopener">Watch ↗</a>
          <button id="mark-unread-btn" class="copy-btn" title="Remove from read history">Mark unread</button>
        </div>
        <div class="detail-topics">${topicsHTML}</div>
      </div>
    </div>

    ${v.executive_summary ? `<div class="exec-summary">${esc(v.executive_summary)}</div>` : ""}

    ${bulletsHTML ? `
    <div class="section">
      <div class="section-title">What Was Discussed <button class="copy-btn" id="copy-bullets">Copy</button></div>
      <ul class="video-bullets">${bulletsHTML}</ul>
    </div>` : ""}

    ${takeawaysHTML ? `
    <div class="section">
      <div class="section-title">Key Takeaways</div>
      <ul class="takeaways">${takeawaysHTML}</ul>
    </div>` : ""}

    ${refsHTML ? `
    <div class="section">
      <div class="section-title">Go Deeper — External References</div>
      <div class="refs">${refsHTML}</div>
    </div>` : ""}

    ${termsHTML ? `
    <div class="section">
      <div class="section-title">Technical Terms in This Video</div>
      <div class="terms">${termsHTML}</div>
    </div>` : ""}

    ${relatedHTML}
  `;

  const unreadBtn = detailContent.querySelector("#mark-unread-btn");
  if (unreadBtn) {
    unreadBtn.addEventListener("click", () => {
      markUnread(videoId);
      unreadBtn.textContent = "Marked unread";
      unreadBtn.disabled = true;
      setTimeout(() => closeDetail(), 600);
    });
  }

  const copyBtn = detailContent.querySelector("#copy-bullets");
  if (copyBtn) {
    const copyText = [
      v.title, "",
      "SUMMARY", v.executive_summary || "", "",
      "KEY POINTS", ...(v.bullets || []).map(b => `• ${b}`), "",
      "KEY TAKEAWAYS", ...(v.key_takeaways || []).map(t => `→ ${t}`),
    ].join("\n");
    copyBtn.addEventListener("click", () => {
      navigator.clipboard.writeText(copyText).then(() => {
        copyBtn.textContent = "Copied!";
        setTimeout(() => { copyBtn.textContent = "Copy"; }, 2000);
      });
    });
  }

  const detailBookmark = detailContent.querySelector("#detail-bookmark");
  if (detailBookmark) {
    detailBookmark.addEventListener("click", () => {
      toggleBookmark(videoId);
      const starred = bookmarkIds.has(videoId);
      detailBookmark.textContent = starred ? "★" : "☆";
      detailBookmark.classList.toggle("bookmarked", starred);
      const cardBtn = grid.querySelector(`.bookmark-btn[data-id="${esc(videoId)}"]`);
      if (cardBtn) {
        cardBtn.textContent = starred ? "★" : "☆";
        cardBtn.classList.toggle("bookmarked", starred);
      }
    });
  }

  detailContent.querySelectorAll(".related-item").forEach(item => {
    item.addEventListener("click", () => openDetail(item.dataset.id));
  });
}

function closeDetail() {
  detailPanel.classList.remove("open");
  contentBody.classList.remove("detail-open");
  contentBody.classList.remove("list-collapsed");
  grid.querySelectorAll(".card").forEach(c => c.classList.remove("card-active"));
  document.getElementById("list-toggle").textContent = "‹";
}

function esc(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── Event Listeners ───────────────────────────────────────────────────
searchInput.addEventListener("input", applyFilters);
document.getElementById("close-detail").addEventListener("click", closeDetail);

document.getElementById("sidebar-toggle").addEventListener("click", () => {
  const collapsed = shell.classList.toggle("sidebar-collapsed");
  document.getElementById("sidebar-toggle").textContent = collapsed ? "»" : "«";
});

document.getElementById("list-toggle").addEventListener("click", () => {
  const collapsed = contentBody.classList.toggle("list-collapsed");
  document.getElementById("list-toggle").textContent = collapsed ? "›" : "‹";
});
document.addEventListener("keydown", e => { if (e.key === "Escape") closeDetail(); });

unlockBtn.addEventListener("click", tryUnlock);
passwordInput.addEventListener("keydown", e => { if (e.key === "Enter") tryUnlock(); });

document.querySelectorAll("[data-read]").forEach(btn => {
  btn.addEventListener("click", () => {
    activeReadFilter = btn.dataset.read;
    document.querySelectorAll("[data-read]").forEach(b => b.classList.toggle("active", b === btn));
    applyFilters();
  });
});

document.querySelectorAll("[data-len]").forEach(btn => {
  btn.addEventListener("click", () => {
    activeLengthFilter = btn.dataset.len;
    document.querySelectorAll("[data-len]").forEach(b => b.classList.toggle("active", b === btn));
    applyFilters();
  });
});

document.querySelectorAll("[data-sort]").forEach(btn => {
  btn.addEventListener("click", () => {
    activeSortOrder = btn.dataset.sort;
    document.querySelectorAll("[data-sort]").forEach(b => b.classList.toggle("active", b === btn));
    applyFilters();
  });
});

init();
