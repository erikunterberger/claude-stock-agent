/* Renders the dashboard from window.DASHBOARD_DATA (written by the agent). */
(function () {
  const D = window.DASHBOARD_DATA;
  if (!D) {
    document.querySelector("main").innerHTML =
      '<div class="card"><p class="empty">No data yet — run the stock agent once (python -m src.main) to generate data.js.</p></div>';
    return;
  }

  /* ---------- helpers ---------- */
  const $ = (id) => document.getElementById(id);
  const money = (n) =>
    n == null ? "—" : "$" + Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const pct = (n, digits = 2) => {
    if (n == null || isNaN(n)) return "—";
    const v = Number(n);
    return (v > 0 ? "+" : "") + v.toFixed(digits) + "%";
  };
  const pctClass = (n) => (n == null ? "muted" : Number(n) >= 0 ? "pos" : "neg");
  const mcap = (n) => {
    if (!n) return "—";
    if (n >= 1e12) return (n / 1e12).toFixed(2) + "T";
    if (n >= 1e9) return (n / 1e9).toFixed(1) + "B";
    return (n / 1e6).toFixed(0) + "M";
  };
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  function table(headers, rows) {
    if (!rows.length) return '<p class="empty">No data available.</p>';
    return (
      "<table><thead><tr>" + headers.map((h) => `<th>${h}</th>`).join("") +
      "</tr></thead><tbody>" + rows.map((r) => "<tr>" + r.map((c) => `<td>${c}</td>`).join("") + "</tr>").join("") +
      "</tbody></table>"
    );
  }

  function newsList(el, articles) {
    if (!articles || !articles.length) { el.innerHTML = '<p class="empty">No articles.</p>'; return; }
    el.innerHTML = articles
      .map((a) => {
        const title = a.url
          ? `<a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.title)}</a>`
          : `<span>${esc(a.title)}</span>`;
        return `<div class="news-item">${title}<div class="src">${esc(a.source || "")}</div>` +
          (a.description ? `<div class="desc">${esc(a.description)}</div>` : "") + "</div>";
      })
      .join("");
  }

  // Extract a "## Section" chunk out of the report markdown.
  function mdSection(name) {
    const re = new RegExp("^##\\s+" + name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\s*$", "mi");
    const m = D.report_markdown.match(re);
    if (!m) return null;
    const start = m.index + m[0].length;
    const rest = D.report_markdown.slice(start);
    const next = rest.search(/^##\s+/m);
    return rest.slice(0, next === -1 ? undefined : next).trim();
  }
  const mdRender = (text) => (text ? marked.parse(text) : '<p class="empty">Not in today\'s report.</p>');

  /* ---------- header ---------- */
  $("meta-line").textContent = `Report date: ${D.run_date} · Generated ${D.generated_at}`;

  /* ---------- tabs ---------- */
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      $("page-" + btn.dataset.page).classList.add("active");
    });
  });

  /* ---------- portfolio (rendered as a function so Refresh can re-call it) ---------- */
  const palette = ["#4ade80", "#60a5fa", "#fbbf24", "#f87171", "#b8a5f5", "#34d399", "#f472b6", "#93c5fd"];
  let allocationChart = null;
  let networthChart = null;

  function renderPortfolio(P) {
    $("header-networth").textContent = money(P.net_worth);

    const hist = P.history || [];
    let histChange = null;
    if (hist.length >= 2) {
      const first = hist[0].net_worth, last = hist[hist.length - 1].net_worth;
      if (first) histChange = ((last - first) / first) * 100;
    }
    $("portfolio-stats").innerHTML = [
      { k: "Net Worth", v: money(P.net_worth) },
      { k: "Cash", v: money(P.cash_total) },
      { k: "Invested (Holdings)", v: money(P.holdings_value) },
      { k: "Change Since Tracking Began", v: pct(histChange), cls: pctClass(histChange) },
    ]
      .map((s) => `<div class="stat"><div class="k">${s.k}</div><div class="v ${s.cls || ""}">${s.v}</div></div>`)
      .join("");

    if (allocationChart) allocationChart.destroy();
    allocationChart = new Chart($("allocation-chart"), {
      type: "doughnut",
      data: {
        labels: P.allocation.map((a) => a.label),
        datasets: [{ data: P.allocation.map((a) => a.value), backgroundColor: palette, borderColor: "#161b22", borderWidth: 2 }],
      },
      options: {
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "right", labels: { color: "#e6edf3", padding: 14 } },
          tooltip: { callbacks: { label: (ctx) => ` ${ctx.label}: ${money(ctx.parsed)}` } },
        },
      },
    });

    if (networthChart) networthChart.destroy();
    networthChart = new Chart($("networth-chart"), {
      type: "line",
      data: {
        labels: hist.map((h) => h.date),
        datasets: [{
          data: hist.map((h) => h.net_worth),
          borderColor: "#4ade80",
          backgroundColor: "rgba(74, 222, 128, 0.12)",
          fill: true,
          tension: 0.25,
          pointRadius: 3,
        }],
      },
      options: {
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => money(ctx.parsed.y) } } },
        scales: {
          x: { ticks: { color: "#8b98a9" }, grid: { color: "#2a3242" } },
          y: { ticks: { color: "#8b98a9", callback: (v) => "$" + Number(v).toLocaleString() }, grid: { color: "#2a3242" } },
        },
      },
    });

    $("holdings-table").innerHTML = P.holdings.length
      ? table(
          ["Ticker", "Bucket", "Shares", "Cost Basis", "Price Now", "Value", "Gain/Loss"],
          P.holdings.map((h) => [
            `<b>${esc(h.ticker)}</b>`, esc(h.bucket || "—"), h.shares, money(h.cost_basis_per_share),
            money(h.price_now), money(h.value_now),
            `<span class="${pctClass(h.gain_pct)}">${pct(h.gain_pct)}</span>`,
          ])
        )
      : '<p class="empty">No stock positions yet — everything is in cash. Your first buys will show up here.</p>';

    $("accounts-table").innerHTML = table(
      ["Account", "Cash"],
      (P.accounts || []).map((a) => [esc(a.name), money(a.cash)])
    );
  }

  renderPortfolio(D.portfolio);

  /* ---------- refresh button (needs dashboard_server.py running) ---------- */
  const refreshBtn = $("refresh-btn");
  const refreshStatus = $("refresh-status");
  refreshBtn.addEventListener("click", async () => {
    refreshBtn.disabled = true;
    refreshStatus.className = "refresh-status";
    refreshStatus.textContent = "Refreshing prices…";
    try {
      const res = await fetch("/api/refresh-prices");
      if (!res.ok) throw new Error((await res.json()).error || "Server error");
      const portfolio = await res.json();
      D.portfolio = portfolio;
      renderPortfolio(portfolio);
      refreshStatus.className = "refresh-status ok";
      refreshStatus.textContent = "Updated " + new Date().toLocaleTimeString();
    } catch (err) {
      refreshStatus.className = "refresh-status error";
      refreshStatus.textContent =
        "Couldn't refresh — open this page via start_dashboard.bat instead of double-clicking index.html for the Refresh button to work.";
    } finally {
      refreshBtn.disabled = false;
    }
  });

  /* ---------- news ---------- */
  $("risks-content").innerHTML = mdRender(mdSection("Risks & What to Watch"));
  $("situation-content").innerHTML = mdRender(mdSection("Market Situation"));
  newsList($("news-top"), D.news.top_headlines);
  newsList($("news-market"), D.news.market_news);
  newsList($("news-sector"), D.news.sector_news);

  /* ---------- suggested ---------- */
  const catClass = (c) => {
    c = String(c || "").toLowerCase();
    if (c.includes("core")) return "core";
    if (c.includes("growth")) return "growth";
    if (c.includes("defen") || c.includes("income")) return "defensive";
    if (c.includes("spec")) return "speculative";
    if (c.includes("etf") || c.includes("divers")) return "etf";
    return "";
  };
  const picks = D.suggested.picks || [];
  $("picks-cards").innerHTML = picks.length
    ? picks
        .map((p) => {
          const f = D.suggested.fundamentals[String(p.ticker).toUpperCase()] || {};
          const bits = [];
          if (f.price) bits.push(`Price <b>${money(f.price)}</b>`);
          if (f.peTTM) bits.push(`P/E <b>${Number(f.peTTM).toFixed(1)}</b>`);
          if (f.marketCap) bits.push(`MCap <b>${mcap(f.marketCap)}</b>`);
          if (f.analystTargetConsensus) bits.push(`Target <b>${money(f.analystTargetConsensus)}</b>`);
          return `<div class="pick-card">
            <div class="head"><span class="tk">${esc(p.ticker)}</span>
            <span class="cat ${catClass(p.category)}">${esc(p.category || "")}</span></div>
            <div class="muted" style="font-size:12px">${esc(p.horizon || "")}</div>
            <div class="thesis">${esc(p.thesis || "")}</div>
            ${bits.length ? `<div class="fund">${bits.join(" · ")}</div>` : ""}
          </div>`;
        })
        .join("")
    : '<p class="empty">No picks extracted from today\'s report.</p>';

  $("tickers-content").innerHTML = mdRender(mdSection("Best Tickers to Invest In"));
  $("allocation-content").innerHTML = mdRender(mdSection("Suggested Portfolio Allocation"));

  const sc = D.suggested.scorecard || [];
  $("scorecard-table").innerHTML = sc.length
    ? table(
        ["Ticker", "Picked On", "Entry", "Now", "Change"],
        sc.map((s) => [
          `<b>${esc(s.ticker)}</b>`, esc(s.picked_on), money(s.price_at_pick), money(s.price_now),
          `<span class="${pctClass(s.change_pct_since_pick)}">${pct(s.change_pct_since_pick)}</span>`,
        ])
      )
    : '<p class="empty">No prior picks tracked yet — the scorecard fills in as daily runs accumulate.</p>';

  /* ---------- overall ---------- */
  $("macro-stats").innerHTML = (D.overall.macro || [])
    .map((m) => {
      const isYield = String(m.symbol).includes("TNX");
      const level = isYield ? (m.price / 10).toFixed(2) + "%" : Number(m.price).toLocaleString();
      return `<div class="stat"><div class="k">${esc(m.name)}</div><div class="v">${level}</div>
        <div class="s ${pctClass(m.changePercentage)}">${pct(m.changePercentage)}</div></div>`;
    })
    .join("");

  const sectors = (D.overall.sector_performance || []).slice().sort((a, b) => b.averageChange - a.averageChange);
  const maxAbs = Math.max(0.01, ...sectors.map((s) => Math.abs(s.averageChange)));
  $("sector-bars").innerHTML = sectors.length
    ? sectors
        .map((s) => {
          const w = (Math.abs(s.averageChange) / maxAbs) * 100;
          const color = s.averageChange >= 0 ? "var(--accent)" : "var(--red)";
          return `<div class="sector-bar-row"><span class="name">${esc(s.sector)}</span>
            <span class="bar-zone"><span class="bar" style="width:${w}%;background:${color}"></span></span>
            <span class="val ${pctClass(s.averageChange)}">${pct(s.averageChange)}</span></div>`;
        })
        .join("")
    : '<p class="empty">No sector data (markets may be closed).</p>';

  const moverRows = (rows) =>
    (rows || []).map((r) => [
      `<b>${esc(r.symbol)}</b>`, esc(r.name), money(r.price),
      `<span class="${pctClass(r.changesPercentage)}">${pct(r.changesPercentage)}</span>`,
      r.marketCap ? mcap(r.marketCap) : "—",
    ]);
  const moverHead = ["Symbol", "Name", "Price", "Change", "MCap"];
  $("gainers-table").innerHTML = table(moverHead, moverRows(D.overall.gainers));
  $("losers-table").innerHTML = table(moverHead, moverRows(D.overall.losers));
  $("active-table").innerHTML = table(moverHead, moverRows(D.overall.most_active));

  $("earnings-table").innerHTML = table(
    ["Symbol", "Date", "Est. EPS", "Est. Revenue"],
    (D.overall.earnings_calendar || []).slice(0, 20).map((e) => [
      `<b>${esc(e.symbol)}</b>`, esc(e.date), e.epsEstimated ?? "—",
      e.revenueEstimated ? mcap(e.revenueEstimated) : "—",
    ])
  );

  /* ---------- full report ---------- */
  $("full-report").innerHTML = marked.parse(D.report_markdown || "");
})();
