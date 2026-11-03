/**
 * BashCraft Sitemap Engine Frontend Controller
 * Controls Vis.js interactive graph, SSE live stream, collapsible tree,
 * search & filters, and export interactions.
 */

let networkInstance = null;
let currentCrawlData = null;
let eventSource = null;
let physicsEnabled = true;

document.addEventListener("DOMContentLoaded", () => {
  initUI();
  initTabs();
  initTheme();
  checkExistingResult();
});

// Initialize UI listeners
function initUI() {
  const crawlForm = document.getElementById("crawlForm");
  const resetBtn = document.getElementById("resetBashcraftBtn");
  const exportBtn = document.getElementById("exportDropdownBtn");
  const exportMenu = document.getElementById("exportMenu");

  // Reset URL to BashCraft default
  resetBtn.addEventListener("click", () => {
    document.getElementById("urlInput").value = "https://bashcraftclub.vercel.app/";
  });

  // Handle Crawl Submission
  crawlForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    await startCrawl();
  });

  // Export dropdown toggle
  exportBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    exportMenu.classList.toggle("hidden");
  });
  document.addEventListener("click", () => {
    exportMenu.classList.add("hidden");
  });

  // Table search & filter listeners
  document.getElementById("tableSearch").addEventListener("input", filterAndRenderTable);
  document.getElementById("statusFilter").addEventListener("change", filterAndRenderTable);
  document.getElementById("sortBy").addEventListener("change", filterAndRenderTable);

  // Network controls
  document.getElementById("fitGraphBtn").addEventListener("click", () => {
    if (networkInstance) networkInstance.fit({ animation: { duration: 600 } });
  });

  document.getElementById("physicsToggleBtn").addEventListener("click", () => {
    if (!networkInstance) return;
    physicsEnabled = !physicsEnabled;
    networkInstance.setOptions({ physics: { enabled: physicsEnabled } });
    document.getElementById("physicsToggleBtn").innerHTML = physicsEnabled
      ? '<i class="fa-solid fa-atom mr-1"></i> Freeze Physics'
      : '<i class="fa-solid fa-play mr-1"></i> Enable Physics';
  });

  // Detail overlay close
  document.getElementById("closeDetailBtn").addEventListener("click", () => {
    document.getElementById("nodeDetailOverlay").classList.add("hidden");
  });

  // Tree controls
  document.getElementById("expandTreeBtn").addEventListener("click", () => toggleAllTree(true));
  document.getElementById("collapseTreeBtn").addEventListener("click", () => toggleAllTree(false));
}

// Tab navigation handler
function initTabs() {
  const tabBtns = document.querySelectorAll(".tab-btn");
  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      const targetId = btn.getAttribute("data-target");
      document.querySelectorAll(".tab-content").forEach((c) => c.classList.add("hidden"));
      const targetContent = document.getElementById(targetId);
      if (targetContent) {
        targetContent.classList.remove("hidden");
        if (targetId === "tabGraph" && networkInstance) {
          networkInstance.fit();
        }
      }
    });
  });
}

// Light/Dark Theme toggle
function initTheme() {
  const themeBtn = document.getElementById("themeToggleBtn");
  const themeIcon = document.getElementById("themeIcon");

  const savedTheme = localStorage.getItem("bashcraft_theme") || "dark";
  if (savedTheme === "light") {
    document.documentElement.classList.remove("dark");
    themeIcon.classList.replace("fa-sun", "fa-moon");
  }

  themeBtn.addEventListener("click", () => {
    const isDark = document.documentElement.classList.toggle("dark");
    localStorage.setItem("bashcraft_theme", isDark ? "dark" : "light");
    if (isDark) {
      themeIcon.classList.replace("fa-moon", "fa-sun");
    } else {
      themeIcon.classList.replace("fa-sun", "fa-moon");
    }
  });
}

// Check if crawl result already exists on page load
async function checkExistingResult() {
  try {
    const res = await fetch("/api/crawl/result");
    if (res.ok) {
      const data = await res.json();
      renderAllResults(data);
    }
  } catch (err) {
    // No prior crawl, leave blank
  }
}

// Trigger crawl request
async function startCrawl() {
  const url = document.getElementById("urlInput").value.trim();
  const maxDepth = parseInt(document.getElementById("maxDepth").value, 10);
  const maxPages = parseInt(document.getElementById("maxPages").value, 10);
  const spaScan = document.getElementById("spaScan").checked;
  const checkBroken = document.getElementById("checkBroken").checked;
  const respectRobots = document.getElementById("respectRobots").checked;

  const btn = document.getElementById("crawlBtn");
  const btnText = document.getElementById("btnText");
  const btnIcon = document.getElementById("btnIcon");

  btn.disabled = true;
  btnText.innerText = "Analyzing...";
  btnIcon.className = "fa-solid fa-spinner fa-spin";

  // Show live progress
  const progressContainer = document.getElementById("liveProgressContainer");
  const progressBar = document.getElementById("liveProgressBar");
  const statusText = document.getElementById("liveStatusText");
  const statsIndicator = document.getElementById("liveStatsIndicator");
  const logMsg = document.getElementById("liveLogMsg");

  progressContainer.classList.remove("hidden");
  progressBar.style.width = "10%";
  statusText.innerText = "Initializing crawler...";
  statsIndicator.innerText = "Connecting...";
  logMsg.innerText = `Target: ${url}`;

  try {
    const response = await fetch("/api/crawl", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url,
        max_depth: maxDepth,
        max_pages: maxPages,
        crawl_delay: 0.05,
        spa_scan: spaScan,
        check_broken_links: checkBroken,
        respect_robots_txt: respectRobots,
      }),
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || "Crawl request failed.");
    }

    // Connect to SSE stream
    listenToCrawlStream();
  } catch (err) {
    alert(`Error: ${err.message}`);
    resetCrawlBtn();
  }
}

// Connect to Server-Sent Events stream
function listenToCrawlStream() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource("/api/crawl/stream");

  const progressBar = document.getElementById("liveProgressBar");
  const statusText = document.getElementById("liveStatusText");
  const statsIndicator = document.getElementById("liveStatsIndicator");
  const logMsg = document.getElementById("liveLogMsg");

  eventSource.onmessage = (e) => {
    if (!e.data || e.data.startsWith(":")) return;
    try {
      const payload = JSON.parse(e.data);

      if (payload.event === "crawling") {
        const count = payload.crawled_count || 0;
        const progressPercent = Math.min(15 + count * 8, 90);
        progressBar.style.width = `${progressPercent}%`;
        statusText.innerText = `Crawling depth ${payload.depth}...`;
        statsIndicator.innerText = `${count} pages analyzed (Queue: ${payload.queue_size})`;
        logMsg.innerText = payload.url;
      } else if (payload.event === "done") {
        progressBar.style.width = "100%";
        statusText.innerText = "Crawl finished successfully!";
        statsIndicator.innerText = "Complete";
        eventSource.close();
        resetCrawlBtn();
        renderAllResults(payload.result);
      } else if (payload.event === "error") {
        eventSource.close();
        resetCrawlBtn();
        alert(`Crawl failed: ${payload.message}`);
      }
    } catch (err) {
      console.error("SSE parse error:", err);
    }
  };

  eventSource.onerror = () => {
    eventSource.close();
    resetCrawlBtn();
  };
}

function resetCrawlBtn() {
  const btn = document.getElementById("crawlBtn");
  const btnText = document.getElementById("btnText");
  const btnIcon = document.getElementById("btnIcon");
  btn.disabled = false;
  btnText.innerText = "Start Crawl";
  btnIcon.className = "fa-solid fa-play";
}

// Render complete results
function renderAllResults(data) {
  currentCrawlData = data;
  const stats = data.stats;

  // 1. Stat cards
  document.getElementById("statPages").innerText = stats.pages_crawled;
  document.getElementById("statDiscovered").innerText = `/ ${stats.pages_discovered} discovered`;
  document.getElementById("statInternal").innerText = stats.total_internal_links;
  document.getElementById("statExternal").innerText = stats.total_external_links;
  document.getElementById("statBroken").innerText = stats.total_broken_links;
  document.getElementById("statHealth").innerText = `${stats.health_score}%`;
  document.getElementById("statDuration").innerText = `${stats.duration_seconds}s`;

  document.getElementById("tableCountBadge").innerText = stats.pages_crawled;
  document.getElementById("brokenCountBadge").innerText = stats.total_broken_links;

  // 2. Render Network Graph
  renderNetworkGraph(data.graph_nodes, data.graph_edges, data.pages);

  // 3. Render Tree
  renderSitemapTree(data.sitemap_tree);

  // 4. Render Table
  filterAndRenderTable();

  // 5. Render Broken Links
  renderBrokenLinks(data.all_broken_links);
}

// -------------------------------------------------------------
// Interactive Force-Directed Graph (Vis.js Network)
// -------------------------------------------------------------
function renderNetworkGraph(nodesData, edgesData, pagesDict) {
  const container = document.getElementById("networkGraph");

  const formattedNodes = nodesData.map((node) => {
    let bgColor = "#10b981"; // green (ok)
    let borderColor = "#059669";

    if (node.group === "root") {
      bgColor = "#8b5cf6"; // purple for root
      borderColor = "#7c3aed";
    } else if (node.group === "broken") {
      bgColor = "#ef4444"; // red for broken
      borderColor = "#dc2626";
    }

    return {
      id: node.id,
      label: node.label,
      title: node.title,
      shape: "box",
      margin: 10,
      color: {
        background: bgColor,
        border: borderColor,
        highlight: {
          background: "#38bdf8",
          border: "#0284c7",
        },
      },
      font: {
        color: "#ffffff",
        face: "JetBrains Mono",
        size: 11,
      },
      shadow: {
        enabled: true,
        color: "rgba(0,0,0,0.5)",
        size: 8,
      },
    };
  });

  const formattedEdges = edgesData.map((edge) => ({
    from: edge.from,
    to: edge.to,
    arrows: "to",
    color: { color: "#334155", highlight: "#38bdf8" },
    smooth: { type: "cubicBezier", roundness: 0.2 },
  }));

  const data = {
    nodes: new vis.DataSet(formattedNodes),
    edges: new vis.DataSet(formattedEdges),
  };

  const options = {
    physics: {
      enabled: physicsEnabled,
      solver: "forceAtlas2Based",
      forceAtlas2Based: {
        gravitationalConstant: -40,
        centralGravity: 0.01,
        springLength: 90,
        springConstant: 0.08,
      },
      stabilization: { iterations: 120 },
    },
    interaction: {
      hover: true,
      tooltipDelay: 150,
      zoomView: true,
      dragView: true,
    },
  };

  networkInstance = new vis.Network(container, data, options);

  // Click on node: show detail card
  networkInstance.on("click", (params) => {
    if (params.nodes && params.nodes.length > 0) {
      const selectedUrl = params.nodes[0];
      const page = pagesDict[selectedUrl];
      if (page) {
        showNodeDetails(page);
      }
    } else {
      document.getElementById("nodeDetailOverlay").classList.add("hidden");
    }
  });
}

function showNodeDetails(page) {
  const overlay = document.getElementById("nodeDetailOverlay");
  const badge = document.getElementById("detailBadge");
  const title = document.getElementById("detailTitle");
  const urlLink = document.getElementById("detailUrlLink");
  const depth = document.getElementById("detailDepth");
  const latency = document.getElementById("detailLatency");
  const inbound = document.getElementById("detailInbound");
  const outInt = document.getElementById("detailOutInternal");
  const outExt = document.getElementById("detailOutExternal");
  const meta = document.getElementById("detailMeta");

  badge.innerText = `${page.status_code} ${page.status_text}`;
  badge.className =
    page.status_code === 200
      ? "px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
      : "px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30";

  title.innerText = page.title || "Untitled";
  urlLink.innerText = page.url;
  urlLink.href = page.url;
  depth.innerText = page.depth;
  latency.innerText = page.response_time_ms;
  inbound.innerText = page.inbound_links_count;
  outInt.innerText = page.outbound_internal_count;
  outExt.innerText = page.outbound_external_count;
  meta.innerText = page.meta_description || "None provided";

  overlay.classList.remove("hidden");
}

// -------------------------------------------------------------
// Sitemap Collapsible Tree
// -------------------------------------------------------------
function renderSitemapTree(treeNode) {
  const container = document.getElementById("treeContainer");
  container.innerHTML = "";

  function createBranch(node) {
    const div = document.createElement("div");
    div.className = "tree-node";

    const row = document.createElement("div");
    row.className = "flex items-center space-x-2 py-1 select-none hover:bg-dark-800/80 rounded px-1.5 transition";

    const hasChildren = node.children && node.children.length > 0;

    if (hasChildren) {
      const toggle = document.createElement("button");
      toggle.className = "text-slate-400 hover:text-emerald-400 text-[10px] w-4 text-center";
      toggle.innerHTML = '<i class="fa-solid fa-chevron-down"></i>';
      toggle.onclick = () => {
        childrenDiv.classList.toggle("hidden");
        toggle.innerHTML = childrenDiv.classList.contains("hidden")
          ? '<i class="fa-solid fa-chevron-right"></i>'
          : '<i class="fa-solid fa-chevron-down"></i>';
      };
      row.appendChild(toggle);
    } else {
      const spacer = document.createElement("span");
      spacer.className = "w-4 text-center text-slate-600 text-[9px]";
      spacer.innerHTML = '<i class="fa-solid fa-circle"></i>';
      row.appendChild(spacer);
    }

    const icon = document.createElement("i");
    icon.className = hasChildren ? "fa-regular fa-folder text-amber-400" : "fa-regular fa-file-code text-emerald-400";
    row.appendChild(icon);

    const nameSpan = document.createElement("span");
    nameSpan.className = "font-semibold text-white";
    nameSpan.innerText = node.name;
    row.appendChild(nameSpan);

    if (node.title && node.title !== node.name) {
      const titleSpan = document.createElement("span");
      titleSpan.className = "text-slate-400 text-[11px] truncate max-w-xs";
      titleSpan.innerText = `— ${node.title}`;
      row.appendChild(titleSpan);
    }

    if (node.url) {
      const link = document.createElement("a");
      link.href = node.url;
      link.target = "_blank";
      link.className = "text-emerald-400 hover:underline text-[10px] ml-auto";
      link.innerHTML = '<i class="fa-solid fa-arrow-up-right-from-square"></i>';
      row.appendChild(link);
    }

    div.appendChild(row);

    let childrenDiv = document.createElement("div");
    if (hasChildren) {
      childrenDiv.className = "tree-children space-y-1";
      node.children.forEach((child) => {
        childrenDiv.appendChild(createBranch(child));
      });
      div.appendChild(childrenDiv);
    }

    return div;
  }

  container.appendChild(createBranch(treeNode));
}

function toggleAllTree(expand) {
  document.querySelectorAll(".tree-children").forEach((el) => {
    if (expand) el.classList.remove("hidden");
    else el.classList.add("hidden");
  });
}

// -------------------------------------------------------------
// Filter & Render Discovered Pages Table
// -------------------------------------------------------------
function filterAndRenderTable() {
  if (!currentCrawlData || !currentCrawlData.pages) return;

  const tbody = document.getElementById("pagesTableBody");
  const query = document.getElementById("tableSearch").value.toLowerCase();
  const statusFilter = document.getElementById("statusFilter").value;
  const sortBy = document.getElementById("sortBy").value;

  let pagesList = Object.values(currentCrawlData.pages);

  // Filter
  pagesList = pagesList.filter((p) => {
    const matchesSearch =
      p.url.toLowerCase().includes(query) || (p.title && p.title.toLowerCase().includes(query));
    if (!matchesSearch) return false;

    if (statusFilter === "200") return p.status_code === 200;
    if (statusFilter === "broken") return p.broken_links_count > 0 || p.status_code !== 200;
    return true;
  });

  // Sort
  if (sortBy === "depth") {
    pagesList.sort((a, b) => a.depth - b.depth || a.url.localeCompare(b.url));
  } else if (sortBy === "latency") {
    pagesList.sort((a, b) => b.response_time_ms - a.response_time_ms);
  } else if (sortBy === "inbound") {
    pagesList.sort((a, b) => b.inbound_links_count - a.inbound_links_count);
  } else if (sortBy === "url") {
    pagesList.sort((a, b) => a.url.localeCompare(b.url));
  }

  tbody.innerHTML = "";

  if (pagesList.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-6 text-slate-500">No matching pages found.</td></tr>`;
    return;
  }

  pagesList.forEach((p) => {
    const tr = document.createElement("tr");
    tr.className = "hover:bg-dark-700/50 transition";

    const badgeClass =
      p.status_code === 200
        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
        : "bg-rose-500/10 text-rose-400 border-rose-500/20";

    tr.innerHTML = `
      <td class="px-4 py-3 whitespace-nowrap">
        <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${badgeClass}">
          ${p.status_code}
        </span>
      </td>
      <td class="px-4 py-3 whitespace-nowrap font-mono text-slate-400">
        ${p.depth}
      </td>
      <td class="px-4 py-3 max-w-sm">
        <div class="font-semibold text-white truncate">${escapeHtml(p.title || "Untitled")}</div>
        <div class="font-mono text-[11px] text-slate-400 truncate">
          <a href="${p.url}" target="_blank" class="hover:text-emerald-400 hover:underline">${escapeHtml(p.url)}</a>
        </div>
      </td>
      <td class="px-4 py-3 text-center font-mono text-slate-300">
        ${p.inbound_links_count}
      </td>
      <td class="px-4 py-3 text-center font-mono text-slate-300">
        ${p.outbound_internal_count}
      </td>
      <td class="px-4 py-3 text-center font-mono text-slate-300">
        ${p.outbound_external_count}
      </td>
      <td class="px-4 py-3 text-right font-mono text-slate-300 whitespace-nowrap">
        ${p.response_time_ms} ms
      </td>
    `;
    tbody.appendChild(tr);
  });
}

// -------------------------------------------------------------
// Render Broken Links Table
// -------------------------------------------------------------
function renderBrokenLinks(brokenList) {
  const tbody = document.getElementById("brokenTableBody");
  const emptyView = document.getElementById("brokenLinksEmpty");
  const tableWrapper = document.getElementById("brokenLinksTableWrapper");

  tbody.innerHTML = "";

  if (!brokenList || brokenList.length === 0) {
    emptyView.classList.remove("hidden");
    tableWrapper.classList.add("hidden");
    return;
  }

  emptyView.classList.add("hidden");
  tableWrapper.classList.remove("hidden");

  brokenList.forEach((bl) => {
    const tr = document.createElement("tr");
    tr.className = "hover:bg-dark-700/50 transition";

    tr.innerHTML = `
      <td class="px-4 py-3 whitespace-nowrap">
        <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-500/10 text-rose-400 border border-rose-500/30">
          ${bl.status_code || "FAIL"}
        </span>
      </td>
      <td class="px-4 py-3 font-mono text-rose-300 break-all max-w-xs">
        <a href="${bl.url}" target="_blank" class="hover:underline">${escapeHtml(bl.url)}</a>
      </td>
      <td class="px-4 py-3 font-mono text-slate-400 break-all max-w-xs">
        <a href="${bl.source_url}" target="_blank" class="text-emerald-400 hover:underline">${escapeHtml(bl.source_url)}</a>
      </td>
      <td class="px-4 py-3 text-slate-300 italic text-[11px] max-w-[150px] truncate">
        ${escapeHtml(bl.anchor_text || "N/A")}
      </td>
      <td class="px-4 py-3 text-slate-300 text-[11px]">
        ${escapeHtml(bl.error_reason || "Unreachable")}
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

