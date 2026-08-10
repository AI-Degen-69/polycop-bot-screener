let allTargets = [];
let filteredTargets = [];
let currentModalIndex = 0;
let currentModalAddr = "";
let radarChartInstance = null;
let showGemsOnly = false;
let activityFilter = "all";
let copyReadyOnly = false;

// Upper age bound in hours per sidebar activity bucket. "all" means no filter.
const ACTIVITY_MAX_HOURS = { live: 6, today: 24, d3: 72, d7: 168 };

// `min_target_order_floor_usd` is the smallest target order whose proportional
// copy still clears Polymarket's $1.00 minimum. The $300 avg-invest hard gate
// already caps that floor at $100, so $100 would filter nothing. $25 is the
// level where a $100 bankroll still copies the target's *small* trades instead
// of silently skipping them.
const COPY_READY_FLOOR_USD = 25.0;

// Defence-in-depth: market titles arrive from a third-party API via the
// pipeline. Escaping before innerHTML insertion prevents stored XSS if that
// source is ever compromised or returns unexpected markup.
function escapeHtml(str) {
    const el = document.createElement("span");
    el.textContent = str;
    return el.innerHTML;
}

document.addEventListener("DOMContentLoaded", () => {
    loadDataset();
    document.getElementById("searchInput")?.addEventListener("input", filterAndRender);
    document.getElementById("sortSelect")?.addEventListener("change", filterAndRender);
    document.getElementById("btnToggleGem")?.addEventListener("click", toggleGemsFilter);
    document.getElementById("btnStartScan")?.addEventListener("click", startLeaderboardScan);
    document.getElementById("btnClearData")?.addEventListener("click", clearScanData);
    document.getElementById("navScreener")?.addEventListener("click", () => switchTab("screener"));
    document.getElementById("navLatency")?.addEventListener("click", () => switchTab("latency"));
    document.getElementById("btnRunLatencyTest")?.addEventListener("click", runLatencyTest);
    document.getElementById("chkCopyReady")?.addEventListener("change", (e) => {
        copyReadyOnly = e.target.checked;
        filterAndRender();
    });
    document.getElementById("btnResetFilters")?.addEventListener("click", resetFilters);
    document.querySelectorAll(".activity-filter").forEach(btn => {
        btn.addEventListener("click", () => setActivityFilter(btn.dataset.activity));
    });

    document.addEventListener("keydown", (e) => {
        const modal = document.getElementById("detailModal");
        if (!modal || !modal.classList.contains("active")) return;
        if (e.key === "Escape") closeModal();
        if (e.key === "ArrowLeft") navigateModal(-1);
        if (e.key === "ArrowRight") navigateModal(1);
    });

    // Dismiss any focused tooltip on Escape (close but keep modal logic above intact)
    document.addEventListener("keydown", (e) => {
        if (e.key !== "Escape") return;
        const active = document.activeElement;
        if (active && active.classList && (
            active.classList.contains("kpi-card") ||
            active.classList.contains("latency-badge-wrapper") ||
            active.classList.contains("th-info") ||
            active.classList.contains("friction-badge")
        )) {
            active.blur();
        }
    });
});

// Everything on the page comes precomputed from the pipeline. The browser does
// no scoring: a second engine here could disagree with the first, and when two
// numbers disagree the one on screen is the one that gets acted on.
const FEED_URL = "/data/phase3_simulated_targets.json";

function normaliseTarget(row) {
    // The rest of the page was written against the triage feed's field names.
    // Map once here rather than touching every reader.
    return Object.assign({}, row, {
        final_score: row.triage_copyability_score ?? 0,
        grade: row.triage_grade || "Ungraded"
    });
}

function renderProvenanceBanner(data) {
    const banner = document.getElementById("provenanceBanner");
    if (!banner) return;

    const profile = data.copy_execution_profile || {};
    const ratio = profile.copy_ratio !== undefined ? `${(profile.copy_ratio * 100).toFixed(1)}%` : "—";
    const bankroll = profile.bankroll_usd !== undefined ? `$${profile.bankroll_usd}` : "—";
    const slippage = profile.slippage_pct !== undefined ? `${profile.slippage_pct}%` : "—";
    const fingerprint = profile.fingerprint ? profile.fingerprint.slice(0, 12) : "unknown";

    const profileLine = `
        <div class="provenance-profile">
            Computed under bankroll <strong>${bankroll}</strong>,
            copy ratio <strong>${ratio}</strong>,
            slippage <strong>${slippage}</strong>
            <span class="provenance-fingerprint" title="Copy Execution Profile fingerprint">${fingerprint}</span>
        </div>
    `;

    if (data.reduced_confidence) {
        banner.className = "provenance-banner degraded";
        banner.innerHTML = `
            <div class="provenance-headline">
                ⚠️ Showing triage order, not simulated results
            </div>
            <div class="provenance-detail">
                The simulation could not run${data.fallback_reason ? `: ${data.fallback_reason}` : ""}.
                Wallets below are ordered by Copyability Score, which triages candidates
                but is not a verdict. No Tier on this page was produced by a simulation.
            </div>
            ${profileLine}
        `;
    } else {
        banner.className = "provenance-banner";
        banner.innerHTML = `
            <div class="provenance-headline">Ranked by simulated performance on your bankroll</div>
            ${profileLine}
        `;
    }
    banner.hidden = false;
}

async function loadDataset() {
    try {
        const resp = await fetch(FEED_URL + "?t=" + Date.now(), { cache: "no-store" });
        if (!resp.ok) throw new Error("Dataset file not found");
        const data = await resp.json();
        allTargets = (data.simulated_targets || []).map(normaliseTarget);
        renderProvenanceBanner(data);
        updateSummaryHeader(data);
        filterAndRender();
    } catch (e) {
        console.warn(`Could not load ${FEED_URL}:`, e);
        allTargets = [];
        const banner = document.getElementById("provenanceBanner");
        if (banner) banner.hidden = true;
        updateSummaryHeader({});
        document.getElementById("walletsGrid").innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 3rem; color: #9ca3af;">
                <h3>⚠️ No Cached Scan Data Found</h3>
                <p style="margin-top: 0.5rem;">Click <strong>⚡ Scan Leaderboard API</strong> above to scrape the leaderboard, triage it, and simulate the survivors against your Copy Execution Profile.</p>
            </div>
        `;
    }
}

function updateSummaryHeader(data = {}) {
    const totalScanned = data.total_targets_evaluated ?? allTargets.length;
    const totalVerified = data.simulated_survivors_count ?? allTargets.length;
    // Counted from simulated verdicts only. A degraded run has no simulated
    // tiers at all, so this reads zero rather than counting triage grades.
    const sTierCount = allTargets.filter(t => t.verdict_source === "simulation"
        && typeof t.tier === "string" && t.tier.startsWith("S-Tier")).length;
    const gemsCount = allTargets.filter(t => t.is_hidden_gem).length;

    document.getElementById("statTotalScanned").innerText = totalScanned;
    document.getElementById("statVerified").innerText = totalVerified;
    document.getElementById("statSTier").innerText = sTierCount;
    document.getElementById("statGems").innerText = gemsCount;
}

function activityHours(t) {
    const h = t.activity ? t.activity.hours_since_active : null;
    return (h === null || h === undefined) ? Infinity : h;
}

function matchesActivityFilter(t) {
    if (activityFilter === "all") return true;
    const maxHours = ACTIVITY_MAX_HOURS[activityFilter];
    if (maxHours === undefined) return true;
    return activityHours(t) < maxHours;
}

function isCopyReady(t) {
    const floor = t.bankroll_analysis ? t.bankroll_analysis.min_target_order_floor_usd : 0;
    return floor > 0 && floor <= COPY_READY_FLOOR_USD;
}

function setActivityFilter(key) {
    activityFilter = key || "all";
    document.querySelectorAll(".activity-filter").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.activity === activityFilter);
    });
    filterAndRender();
}

function resetFilters() {
    copyReadyOnly = false;
    const chk = document.getElementById("chkCopyReady");
    if (chk) chk.checked = false;
    const search = document.getElementById("searchInput");
    if (search) search.value = "";
    if (showGemsOnly) toggleGemsFilter();
    setActivityFilter("all");
}

function updateActivityCounts() {
    const counts = { all: allTargets.length, live: 0, today: 0, d3: 0, d7: 0 };
    allTargets.forEach(t => {
        const h = activityHours(t);
        // Buckets are cumulative: anything live also counts as "today".
        if (h < ACTIVITY_MAX_HOURS.live) counts.live++;
        if (h < ACTIVITY_MAX_HOURS.today) counts.today++;
        if (h < ACTIVITY_MAX_HOURS.d3) counts.d3++;
        if (h < ACTIVITY_MAX_HOURS.d7) counts.d7++;
    });
    Object.keys(counts).forEach(key => {
        const el = document.querySelector(`.af-count[data-count="${key}"]`);
        if (el) el.innerText = counts[key];
    });
}

function formatLastActive(t) {
    const h = activityHours(t);
    if (!isFinite(h)) return { text: "Unknown", tier: "stale" };
    if (h < 1) return { text: `${Math.round(h * 60)}m ago`, tier: "live" };
    if (h < 24) return { text: `${Math.round(h)}h ago`, tier: h < 6 ? "live" : "today" };
    const days = Math.floor(h / 24);
    return { text: `${days}d ago`, tier: days < 3 ? "d3" : (days < 7 ? "d7" : "stale") };
}

function toggleGemsFilter(e) {
    if (e && e.target && e.target.closest('.gem-info-bubble-wrapper')) return;

    showGemsOnly = !showGemsOnly;
    const btn = document.getElementById("btnToggleGem");
    const labelSpan = btn.querySelector(".btn-label");

    if (showGemsOnly) {
        btn.classList.add("active");
        if (labelSpan) labelSpan.innerHTML = '💎 Hidden Gems Active <span style="font-size:0.75rem; opacity:0.8;">(Click to show all)</span>';
    } else {
        btn.classList.remove("active");
        if (labelSpan) labelSpan.innerHTML = '💎 Hidden Gems Only';
    }
    filterAndRender();
}

function filterAndRender() {
    const search = document.getElementById("searchInput").value.toLowerCase();
    const sortVal = document.getElementById("sortSelect").value;

    filteredTargets = allTargets.filter(t => {
        const formattedTitle = formatTraderName(t).title.toLowerCase();
        const matchesSearch = t.name.toLowerCase().includes(search) || t.address.toLowerCase().includes(search) || formattedTitle.includes(search);
        const matchesGem = !showGemsOnly || t.is_hidden_gem;
        const matchesCopyReady = !copyReadyOnly || isCopyReady(t);
        return matchesSearch && matchesGem && matchesActivityFilter(t) && matchesCopyReady;
    });

    if (sortVal === "retention-desc") {
        // An unsimulated wallet has no retention to rank on, so it sorts below
        // every wallet that does rather than being treated as a zero.
        filteredTargets.sort((a, b) =>
            ((b.edge_retention ?? -1) - (a.edge_retention ?? -1)) || (b.final_score - a.final_score));
    }
    else if (sortVal === "score-desc") filteredTargets.sort((a, b) => b.final_score - a.final_score);
    else if (sortVal === "score-asc") filteredTargets.sort((a, b) => a.final_score - b.final_score);
    else if (sortVal === "pnl-desc") filteredTargets.sort((a, b) => b.metrics.copy_pnl - a.metrics.copy_pnl);
    else if (sortVal === "wr-desc") filteredTargets.sort((a, b) => b.metrics.r20_win_rate - a.metrics.r20_win_rate);
    else if (sortVal === "polycop-desc") filteredTargets.sort((a, b) => b.metrics.polycop_site_score - a.metrics.polycop_site_score);
    else if (sortVal === "activity-desc") filteredTargets.sort((a, b) => activityHours(a) - activityHours(b));
    else if (sortVal === "trades7d-desc") filteredTargets.sort((a, b) => ((b.activity?.trades_7d) || 0) - ((a.activity?.trades_7d) || 0));

    updateActivityCounts();
    renderGrid();
}

function formatTraderName(t) {
    let name = (t.name || "").trim();
    const addr = t.address || "";
    const last4 = addr.length >= 4 ? addr.slice(-4) : "";
    
    const isGeneric = !name || /^polycop/i.test(name) || /^0x/i.test(name);
    
    if (isGeneric) {
        return {
            title: `Trader (${last4})`,
            subText: ""
        };
    } else {
        return {
            title: name,
            subText: addr ? `${addr.slice(0, 6)}...${addr.slice(-4)}` : ""
        };
    }
}

function formatShare(value) {
    // A share nobody measured is not a share of zero.
    return (value === null || value === undefined) ? "Not measured" : `${(value * 100).toFixed(0)}%`;
}

function renderTierCell(t) {
    // The letter alone cannot tell a reader whether a simulation produced it.
    // A triage grade shown in a Tier column is the whole failure this page is
    // meant to avoid, so an unsimulated wallet says so instead of showing one.
    if (t.verdict_source === "simulation" && t.tier) {
        return `
            <div class="summary-cell">
                <span class="summary-lbl">Tier (simulated)</span>
                <span class="summary-val" style="color: var(--accent-cyan)">${t.tier.split(' ')[0]}</span>
            </div>
        `;
    }
    return `
        <div class="summary-cell">
            <span class="summary-lbl">Tier</span>
            <span class="summary-val tier-unsimulated" title="No Simulated Copy Run produced a verdict for this wallet. ${t.grade} is its triage grade, which is not a verdict.">Not simulated</span>
        </div>
    `;
}

function renderRetentionCell(t) {
    const retention = t.edge_retention;
    if (retention === null || retention === undefined) {
        return `
            <div class="summary-cell">
                <span class="summary-lbl">Edge Retention</span>
                <span class="summary-val tier-unsimulated">Not simulated</span>
            </div>
        `;
    }
    return `
        <div class="summary-cell">
            <span class="summary-lbl">Edge Retention</span>
            <span class="summary-val" style="color: ${retention >= 0.7 ? '#10b981' : (retention >= 0.4 ? '#f59e0b' : '#ef4444')}">
                ${(retention * 100).toFixed(0)}%
            </span>
        </div>
    `;
}

function renderGrid() {
    const grid = document.getElementById("walletsGrid");
    if (filteredTargets.length === 0) {
        grid.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 3rem; color: #9ca3af;">
                <h3>No wallets match your criteria</h3>
            </div>
        `;
        return;
    }

    grid.innerHTML = filteredTargets.map((t, idx) => {
        const isGem = t.is_hidden_gem;
        const cardClass = isGem ? "wallet-card card-gem" : "wallet-card";
        const nameInfo = formatTraderName(t);
        const subAddrHtml = nameInfo.subText ? `
            <div class="wallet-card-addr-row" style="display: flex; align-items: center; gap: 6px; margin-top: 4px;">
                <div class="wallet-card-addr">${nameInfo.subText}</div>
                <button class="btn-copy-mini" onclick="copyAddressToClipboard(event, '${t.address}')" title="Copy address to clipboard">📋</button>
            </div>
        ` : `
            <div class="wallet-card-addr-row" style="display: flex; align-items: center; gap: 6px; margin-top: 4px;">
                <button class="btn-copy-mini" onclick="copyAddressToClipboard(event, '${t.address}')" title="Copy address to clipboard">📋 Copy Address</button>
            </div>
        `;
        const gemBadgeHtml = isGem ? `
            <div class="badge-gem-wrapper">
                <span class="badge-gem">💎 GEM</span>
                <div class="gem-tooltip-text">
                    <strong>💎 Hidden Gem Detected!</strong><br>
                    PolyCop under-rated site score (&lt;75), but passes all 8 Hard Rejection Gates with a <strong>God-Tier Screener Score (&ge;80.0)</strong>!
                </div>
            </div>
        ` : '';

        const lastActive = formatLastActive(t);
        const buyPrice = t.metrics ? (t.metrics.buy_price || 0.0) : 0.0;
        const highBuyBadgeHtml = buyPrice > 0.85 ? `
            <div class="badge-high-buy-wrapper" style="display:inline-block;">
                <span class="badge-high-buy">⚠️ High Buy ($${buyPrice.toFixed(2)})</span>
                <div class="gem-tooltip-text" style="border-color: #f59e0b;">
                    <strong>⚠️ High Entry Price Warning ($${buyPrice.toFixed(2)})!</strong><br>
                    This trader buys at $0.85–$0.99 (Dust Yield Farming). Set <strong>Max Price: 0.95</strong> in backtest controls!
                </div>
            </div>
        ` : '';

        return `
            <div class="${cardClass}" onclick="openModal(${idx})">
                <div class="wallet-card-top">
                    <div>
                        <div class="wallet-card-name">
                            ${nameInfo.title}
                            ${gemBadgeHtml}
                            ${highBuyBadgeHtml}
                        </div>
                        ${subAddrHtml}
                    </div>
                    <div class="score-badge">${t.final_score} Pts</div>
                </div>
                <div class="card-metrics-summary">
                    <div class="summary-cell">
                        <span class="summary-lbl">Backtest Copy PnL</span>
                        <span class="summary-val" style="color: ${t.metrics.copy_pnl >= 0 ? '#10b981' : '#ef4444'}">
                            $${t.metrics.copy_pnl.toLocaleString('en-US', {minimumFractionDigits: 2})}
                        </span>
                    </div>
                    ${renderTierCell(t)}
                    ${renderRetentionCell(t)}
                    <div class="summary-cell">
                        <span class="summary-lbl">Copyable Window Share</span>
                        <span class="summary-val">${formatShare(t.copyable_window_share)}</span>
                    </div>
                    <div class="summary-cell">
                        <span class="summary-lbl">Avg Invest</span>
                        <span class="summary-val">$${t.metrics.avg_invest}</span>
                    </div>
                    <div class="summary-cell">
                        <span class="summary-lbl">Last Active</span>
                        <span class="summary-val activity-val" data-tier="${lastActive.tier}">${lastActive.text}</span>
                    </div>
                    <div class="summary-cell">
                        <span class="summary-lbl">Trades (7d)</span>
                        <span class="summary-val">${t.activity?.trades_7d ?? 0}</span>
                    </div>
                </div>
            </div>
        `;
    }).join("");
}

function renderBalanceMiss(target) {
    // Trades the simulation could not follow because the bankroll was already
    // deployed. Direct evidence of capital exhaustion at this account size,
    // and the one figure on the page that is about the follower rather than
    // the target.
    const host = document.getElementById("modalBalanceMiss");
    if (!host) return;

    if (target.verdict_source !== "simulation") {
        host.innerHTML = `<div class="bm-empty">No Simulated Copy Run, so no per-market record exists.</div>`;
        return;
    }

    // The pipeline already dropped the markets that funded everything, so every
    // entry here is a miss and an empty list means the bankroll held.
    const missed = target.balance_miss_details || [];
    if (missed.length === 0) {
        host.innerHTML = `<div class="bm-ok">✅ Every copyable trade was funded — the bankroll never ran dry.</div>`;
        return;
    }

    const rows = missed.slice(0, 12).map(l => `
        <div class="bm-row">
            <span class="bm-market">${escapeHtml(l.market || "Unnamed market")}</span>
            <span class="bm-amount">${l.amount !== undefined ? `$${Number(l.amount).toFixed(2)}` : ""}</span>
        </div>
    `).join("");

    host.innerHTML = `
        <div class="bm-headline">⚠️ ${missed.length} trade${missed.length === 1 ? "" : "s"} missed for lack of balance</div>
        ${rows}
        ${missed.length > 12 ? `<div class="bm-empty">…and ${missed.length - 12} more.</div>` : ""}
    `;
}

function openModal(idx) {
    currentModalIndex = idx;
    const target = filteredTargets[idx];
    if (!target) return;

    currentModalAddr = target.address;

    const modal = document.getElementById("detailModal");
    const modalContainer = modal.querySelector(".modal-container");
    
    if (target.is_hidden_gem) modalContainer.classList.add("modal-gem");
    else modalContainer.classList.remove("modal-gem");

    const nameInfo = formatTraderName(target);
    document.getElementById("modalTitle").innerText = nameInfo.title;
    document.getElementById("modalAddr").innerText = `${target.address.slice(0, 8)}...${target.address.slice(-6)}`;
    // Labelled as triage so the badge is never mistaken for a simulated verdict.
    document.getElementById("modalGradeBadge").innerText = target.verdict_source === "simulation" && target.tier
        ? `${target.tier} (simulated)`
        : `${target.grade} (triage only)`;
    document.getElementById("modalScreenerScore").innerText = `${target.final_score} / 100 Pts`;
    renderBalanceMiss(target);
    document.getElementById("modalPolyCopScore").innerText = `${target.metrics.polycop_site_score} / 100 Site`;
    
    // Set correct external profile & platform links
    document.getElementById("modalPolymarketLink").href = `https://polymarket.com/@${target.address}`;
    document.getElementById("modalPolyCopLink").href = `https://polycop.fun/copy-backtest_${target.address}`;

    const plRatio = target.metrics.pl_ratio || 0;
    let plColor = "#10b981";
    if (plRatio < 0.3) plColor = "#ef4444";
    else if (plRatio < 1.0) plColor = "#f59e0b";

    document.getElementById("cardCopyPnl").innerText = `$${target.metrics.copy_pnl.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
    document.getElementById("cardCopyPnl").style.color = target.metrics.copy_pnl >= 0 ? "#10b981" : "#ef4444";
    document.getElementById("cardPlRatio").innerText = `${plRatio.toFixed(2)}x`;
    document.getElementById("cardPlRatio").style.color = plColor;
    document.getElementById("cardWinRate").innerText = `${target.metrics.r20_win_rate}%`;
    document.getElementById("cardRoi").innerText = `${target.metrics.pnl_vol_ratio}%`;
    document.getElementById("cardMarkets").innerText = `${target.metrics.markets} / $${(target.metrics.copy_pnl * 5).toLocaleString('en-US', {maximumFractionDigits:0})}`;
    document.getElementById("cardFloorMin").innerText = `$${target.bankroll_analysis.min_target_order_floor_usd.toFixed(2)}`;

    renderParamBars(target);
    renderRadarChart(target);

    modal.classList.add("active");
}

function copyAddressToClipboard(event, address) {
    if (event) event.stopPropagation();
    if (!address) return;
    navigator.clipboard.writeText(address).then(() => {
        const btn = event.currentTarget || event.target;
        const origHtml = btn.innerHTML;
        btn.innerHTML = "✓ Copied!";
        btn.classList.add("copied");
        setTimeout(() => {
            btn.innerHTML = origHtml;
            btn.classList.remove("copied");
        }, 1500);
    }).catch(err => {
        console.error("Clipboard write failed:", err);
    });
}

function closeModal() {
    document.getElementById("detailModal").classList.remove("active");
}

function navigateModal(direction) {
    if (filteredTargets.length === 0) return;
    currentModalIndex = (currentModalIndex + direction + filteredTargets.length) % filteredTargets.length;
    openModal(currentModalIndex);
}

function renderParamBars(target) {
    const container = document.getElementById("paramBarsContainer");
    const b = target.breakdown || {};

    const maxScores = {
        "1. Slippage Cost Rate (20%)": 20,
        "2. Recent 20 PnL & Slip (15%)": 15,
        "3. Hedged Control < 3% (15%)": 15,
        "4. Daily Green Rate (15%)": 15,
        "5. Recent 20 Win Rate (10%)": 10,
        "6. Profit/Loss Ratio (10%)": 10,
        "7. Capital Efficiency (5%)": 5,
        "8. Markets Sample (5%)": 5,
        "9. Continuous Sizing Fit ($25 Peak) (5%)": 5
    };

    container.innerHTML = Object.keys(maxScores).map(key => {
        const score = b[key] || 0.0;
        const max = maxScores[key];
        const pct = Math.min((score / max) * 100, 100);

        return `
            <div class="param-bar-item">
                <div class="param-bar-header">
                    <span class="param-bar-title">${key}</span>
                    <span class="param-bar-score">${score} / ${max} pts</span>
                </div>
                <div class="bar-track-outer">
                    <div class="bar-fill-inner" style="width: ${pct}%"></div>
                </div>
            </div>
        `;
    }).join("");
}

function renderRadarChart(target) {
    const ctx = document.getElementById("radarChartCanvas").getContext("2d");
    if (radarChartInstance) radarChartInstance.destroy();

    const getScorePct = (score, max) => Math.round(Math.min(Math.max((score / max) * 100, 0), 100));
    const b = target.breakdown || {};

    const radarValues = [
        getScorePct(b["1. Slippage Cost Rate (20%)"] || 0, 20),
        getScorePct(b["2. Recent 20 PnL & Slip (15%)"] || 0, 15),
        getScorePct(b["3. Hedged Control < 3% (15%)"] || 0, 15),
        getScorePct(b["4. Daily Green Rate (15%)"] || 0, 15),
        getScorePct(b["5. Recent 20 Win Rate (10%)"] || 0, 10),
        getScorePct(b["6. Profit/Loss Ratio (10%)"] || 0, 10),
        getScorePct(b["7. Capital Efficiency (5%)"] || 0, 5),
        getScorePct(b["8. Markets Sample (5%)"] || 0, 5),
        getScorePct(b["9. Continuous Sizing Fit ($25 Peak) (5%)"] || 0, 5)
    ];

    radarChartInstance = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: [
                'Slippage Cost (20%)',
                'Recent 20 PnL (15%)',
                'Hedged Control (15%)',
                'Daily Green (15%)',
                'Win Rate (10%)',
                'P/L Ratio (10%)',
                'Efficiency (5%)',
                'Sample Size (5%)',
                'Sizing Fit (5%)'
            ],
            datasets: [{
                label: 'Screener Score %',
                data: radarValues,
                fill: true,
                backgroundColor: 'rgba(6, 182, 212, 0.25)',
                borderColor: '#06b6d4',
                pointBackgroundColor: '#8b5cf6',
                pointBorderColor: '#fff',
                pointHoverBackgroundColor: '#fff',
                pointHoverBorderColor: '#8b5cf6'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    angleLines: { color: 'rgba(255, 255, 255, 0.1)' },
                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                    pointLabels: { color: '#9ca3af', font: { size: 10 } },
                    ticks: { display: false },
                    suggestedMin: 0,
                    suggestedMax: 100,
                    min: 0,
                    max: 100
                }
            },
            plugins: { legend: { display: false } }
        }
    });
}

// ==========================================================================
// LEADERBOARD SCANNER & DATA MANAGEMENT
// ==========================================================================
async function startLeaderboardScan() {
    const btn = document.getElementById("btnStartScan");
    if (!btn) return;

    btn.disabled = true;
    const origHtml = btn.innerHTML;
    btn.innerHTML = `<span class="pulse-dot"></span> Scanning PolyCop Leaderboard...`;

    try {
        const resp = await fetch("/api/rescan?t=" + Date.now());
        if (!resp.ok) throw new Error("Rescan API returned status " + resp.status);
        const data = await resp.json();
        allTargets = data.verified_targets || [];
        updateSummaryHeader(data);
        filterAndRender();
        alert(`Scan Complete!\nTotal Scraped: ${data.total_scraped_profiles || 0}\nVerified Targets: ${data.total_verified_targets || 0}`);
    } catch (err) {
        console.error("Leaderboard scan error:", err);
        alert("Scan failed: " + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = origHtml;
    }
}

async function clearScanData() {
    if (!confirm("Are you sure you want to clear cached scan data?")) return;

    try {
        const resp = await fetch("/api/clear_data?t=" + Date.now());
        if (!resp.ok) throw new Error("Clear data API error");
        allTargets = [];
        filteredTargets = [];
        updateSummaryHeader({});
        loadDataset();
    } catch (err) {
        console.error("Clear data error:", err);
        alert("Failed to clear data: " + err.message);
    }
}

window.startLeaderboardScan = startLeaderboardScan;
window.clearScanData = clearScanData;

// ==========================================================================
// TAB NAVIGATION & LATENCY PROFILER PAGE INTERACTIVITY
// ==========================================================================
let globeAnimFrameId = null;
let packetsList = [];
let isTestActive = false;

function switchTab(tabId) {
    document.querySelectorAll(".sidebar-nav .nav-item").forEach(btn => btn.classList.remove("active"));
    document.querySelectorAll(".page-view").forEach(view => view.classList.remove("active"));

    if (tabId === "screener") {
        document.getElementById("navScreener")?.classList.add("active");
        document.getElementById("pageScreener")?.classList.add("active");
        if (globeAnimFrameId) {
            cancelAnimationFrame(globeAnimFrameId);
            globeAnimFrameId = null;
        }
    } else if (tabId === "latency") {
        document.getElementById("navLatency")?.classList.add("active");
        document.getElementById("pageLatency")?.classList.add("active");
        try {
            initGlobeAnimation();
            renderGaugeMeter(0);
            renderDistributionPanel(0, 0, 0);
        } catch (e) {
            console.error("Canvas render error:", e);
        }
    }
}
window.switchTab = switchTab;

// ==========================================================================
// ANIMATED PACKET GLOBE VISUALIZER (CANVAS)
// ==========================================================================
function initGlobeAnimation() {
    const canvas = document.getElementById("globeCanvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (globeAnimFrameId) cancelAnimationFrame(globeAnimFrameId);

    let angle = 0;
    
    // Create initial packet particles
    packetsList = [];
    for (let i = 0; i < 6; i++) {
        packetsList.push({
            progress: Math.random(),
            speed: 0.008 + Math.random() * 0.005,
            direction: i % 2 === 0 ? 1 : -1
        });
    }

    function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        const cx = canvas.width / 2;
        const cy = canvas.height / 2;
        const radius = 70;

        // Draw outer glow
        ctx.beginPath();
        ctx.arc(cx, cy, radius + 10, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(0, 242, 254, 0.03)";
        ctx.fill();

        // Draw Wireframe Globe Latitudes / Longitudes
        angle += 0.005;
        ctx.strokeStyle = "rgba(0, 242, 254, 0.18)";
        ctx.lineWidth = 1;

        for (let i = -2; i <= 2; i++) {
            const radSq = radius * radius - (i * 22) * (i * 22);
            if (radSq > 0) {
                const r = Math.sqrt(radSq);
                ctx.beginPath();
                ctx.ellipse(cx, cy + i * 22, r, Math.max(0.1, r * 0.35), 0, 0, Math.PI * 2);
                ctx.stroke();
            }
        }

        for (let i = 0; i < 6; i++) {
            const rot = angle + (i * Math.PI / 3);
            const radiusX = Math.max(0.1, radius * Math.abs(Math.cos(rot)));
            ctx.beginPath();
            ctx.ellipse(cx, cy, radiusX, radius, 0, 0, Math.PI * 2);
            ctx.stroke();
        }

        // Host Node (Left) & Polymarket Gateway Node (Right)
        const hostX = cx - 180;
        const hostY = cy;
        const targetX = cx + 180;
        const targetY = cy;

        // Host Node
        ctx.beginPath();
        ctx.arc(hostX, hostY, 8, 0, Math.PI * 2);
        ctx.fillStyle = "#00f2fe";
        ctx.fill();
        ctx.shadowColor = "#00f2fe";
        ctx.shadowBlur = 10;
        ctx.font = "bold 11px Outfit, sans-serif";
        ctx.fillStyle = "#fff";
        ctx.fillText("CLIENT NODE", hostX - 35, hostY + 22);

        // Target CLOB Node
        ctx.beginPath();
        ctx.arc(targetX, targetY, 8, 0, Math.PI * 2);
        ctx.fillStyle = "#00e676";
        ctx.fill();
        ctx.shadowColor = "#00e676";
        ctx.shadowBlur = 10;
        ctx.fillText("POLY CLOB GATEWAY", targetX - 50, targetY + 22);
        ctx.shadowBlur = 0;

        // Connecting Packet Transmission Arcs
        ctx.beginPath();
        ctx.moveTo(hostX, hostY);
        ctx.quadraticCurveTo(cx, cy - 60, targetX, targetY);
        ctx.strokeStyle = "rgba(0, 242, 254, 0.25)";
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 4]);
        ctx.stroke();
        ctx.setLineDash([]);

        // Animate Traveling Packets
        packetsList.forEach(p => {
            p.progress += isTestActive ? p.speed * 2.5 : p.speed;
            if (p.progress > 1) p.progress = 0;

            const t = p.progress;
            const px = (1 - t) * (1 - t) * hostX + 2 * (1 - t) * t * cx + t * t * targetX;
            const py = (1 - t) * (1 - t) * hostY + 2 * (1 - t) * t * (cy - 60) + t * t * targetY;

            ctx.beginPath();
            ctx.arc(px, py, 4, 0, Math.PI * 2);
            ctx.fillStyle = p.direction === 1 ? "#00f2fe" : "#00e676";
            ctx.shadowColor = ctx.fillStyle;
            ctx.shadowBlur = 12;
            ctx.fill();
            ctx.shadowBlur = 0;
        });

        globeAnimFrameId = requestAnimationFrame(draw);
    }
    draw();
}

// ==========================================================================
// 5-LEVEL LATENCY GAUGE METER RENDERER
// ==========================================================================

// Single source of truth for tier classification. Used by the gauge, the
// distribution panel endpoint dots, and the in-panel status badge.
// Returns: { tier, label, cssTier, gaugePct, color, emoji }
function classifyTier(rttMs) {
    if (rttMs < 100)  return { tier: "fast", label: "FAST",     cssTier: "fast",     gaugePct: (rttMs / 100) * 0.2,    color: "#00e676", emoji: "⚡" };
    if (rttMs < 250)  return { tier: "good", label: "GOOD",     cssTier: "good",     gaugePct: 0.2 + ((rttMs - 100) / 150) * 0.2, color: "#69f0ae", emoji: "🟢" };
    if (rttMs < 500)  return { tier: "avg",  label: "AVERAGE",  cssTier: "average",  gaugePct: 0.4 + ((rttMs - 250) / 250) * 0.2, color: "#ffd600", emoji: "🟡" };
    if (rttMs < 1000) return { tier: "slow", label: "SLOW",     cssTier: "slow",     gaugePct: 0.6 + ((rttMs - 500) / 500) * 0.2, color: "#ff9100", emoji: "🟠" };
    return                  { tier: "poor", label: "POOR",     cssTier: "poor",     gaugePct: 0.8 + Math.min(0.2, ((rttMs - 1000) / 1000) * 0.2), color: "#ff1744", emoji: "🔴" };
}

function renderGaugeMeter(rttMs) {
    const canvas = document.getElementById("gaugeCanvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const cx = canvas.width / 2;
    const cy = canvas.height - 15;
    const radius = 100;
    const lineWidth = 18;

    // 5-Level Color Scale Segments (PI to 2*PI semi-circle)
    const segments = [
        { label: "Fast", color: "#00e676", endPct: 0.2 },
        { label: "Good", color: "#69f0ae", endPct: 0.4 },
        { label: "Average", color: "#ffd600", endPct: 0.6 },
        { label: "Slow", color: "#ff9100", endPct: 0.8 },
        { label: "Poor", color: "#ff1744", endPct: 1.0 }
    ];

    let startAngle = Math.PI;
    segments.forEach(s => {
        const endAngle = Math.PI + (s.endPct * Math.PI);
        ctx.beginPath();
        ctx.arc(cx, cy, radius, startAngle, endAngle);
        ctx.lineWidth = lineWidth;
        ctx.strokeStyle = s.color;
        ctx.lineCap = "butt";
        ctx.stroke();
        startAngle = endAngle;
    });

    // Classify via the shared helper and use its gaugePct for needle angle.
    const cls = classifyTier(rttMs);
    const needleAngle = Math.PI + (cls.gaugePct * Math.PI);

    // Draw Needle Pointer
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(needleAngle);

    ctx.beginPath();
    ctx.moveTo(0, -4);
    ctx.lineTo(radius - 12, 0);
    ctx.lineTo(0, 4);
    ctx.fillStyle = "#ffffff";
    ctx.shadowColor = "#ffffff";
    ctx.shadowBlur = 8;
    ctx.fill();

    ctx.beginPath();
    ctx.arc(0, 0, 7, 0, Math.PI * 2);
    ctx.fillStyle = "#00f2fe";
    ctx.fill();
    ctx.restore();

    // Update Status Badge Element (now in the distribution panel header)
    const badgeEl = document.getElementById("latencyStatusBadge");
    if (badgeEl) {
        badgeEl.className = `latency-badge tier-${cls.cssTier}`;
        badgeEl.innerText = `${cls.emoji} ${cls.label} (${rttMs.toFixed(1)} ms)`;
    }
}

// ==========================================================================
// HTTP REST LATENCY DISTRIBUTION PANEL RENDERER
// ==========================================================================
// Updates the tri-stat row (best / avg / worst), the tier-segmented range
// bar (min endpoint, avg marker, max endpoint), the variance/spread row,
// and the per-stat tier chips. Re-uses classifyTier() for color coding.
function renderDistributionPanel(min, avg, max) {
    const safeMin = +min || 0;
    const safeAvg = +avg || 0;
    const safeMax = +max || 0;

    // ---- Tri-stat values ----
    // Distinguish "no measurement yet" (all three values are exactly 0) from
    // a genuine zero. The previous render unfortunately showed "0.0 ms / FAST"
    // on a fresh tab, misleadingly implying sub-millisecond perfect latency.
    const noData = safeMin === 0 && safeAvg === 0 && safeMax === 0;
    const setVal = (id, v) => {
        const el = document.getElementById(id);
        if (el) el.innerText = noData ? "-- ms" : `${v.toFixed(1)} ms`;
    };
    setVal("httpBestVal",  safeMin);
    setVal("httpAvgVal",   safeAvg);
    setVal("httpWorstVal", safeMax);

    // ---- Per-stat tier chips ----
    const cls = (v) => classifyTier(v);
    const setTierChip = (id, classification) => {
        const el = document.getElementById(id);
        if (!el) return;
        if (noData) {
            el.dataset.tier = "fast";
            el.innerText = "--";
            el.style.color = "";
            el.style.borderColor = "";
            el.style.background = "";
        } else {
            el.dataset.tier = classification.tier;
            el.innerText = `${classification.emoji} ${classification.label}`;
            el.style.color = classification.color;
            el.style.borderColor = classification.color;
            el.style.background = classification.color + "1f"; // ~12% alpha hex suffix
        }
    };
    setTierChip("httpBestTier",  cls(safeMin));
    setTierChip("httpAvgTier",   cls(safeAvg));
    setTierChip("httpWorstTier", cls(safeMax));

    // ---- Range bar geometry ----
    // The bar's tier boundaries stay anchored to absolute ms values (0, 100,
    // 250, 500, 1000) and the right edge extends up to max(practicalScale,
    // actualMax * 1.05) so spikes that exceed 1s stay visually placed at
    // their real position rather than clamped.
    const TIER_BOUNDS = [0, 100, 250, 500, 1000];
    const practicalScale = 2000; // base right edge when nothing exceeds it
    const rightEdge = Math.max(practicalScale, safeMax * 1.05, ...TIER_BOUNDS.slice(-1));
    const toPct = (v) => Math.max(0, Math.min(100, (v / rightEdge) * 100));

    // Tier-segmented gradient that mirrors the gauge's color scale.
    // Each tier occupies [segBounds[i].bound, segBounds[i+1].bound] and is
    // emitted as a pair of stops with the *same color*, so the boundary between
    // two tiers is a hard color edge with no interpolation. All stops are
    // monotonically ascending in percent.
    const tierColors = { fast: "#00e676", good: "#69f0ae", avg: "#ffd600", slow: "#ff9100", poor: "#ff1744" };
    const segBounds = [ // (bound, cssTier)
        [TIER_BOUNDS[0], "fast"],  // 0
        [TIER_BOUNDS[1], "good"],  // 100
        [TIER_BOUNDS[2], "avg"],   // 250
        [TIER_BOUNDS[3], "slow"],  // 500
        [TIER_BOUNDS[4], "poor"],  // 1000
        [rightEdge,      "poor"],  // rightEdge (>= 2000)
    ];
    const stops = [];
    for (let i = 0; i < segBounds.length - 1; i++) {
        const [start, startTier] = segBounds[i];
        const [end,   endTier  ] = segBounds[i + 1];
        const startPct = (start / rightEdge) * 100;
        const endPct   = (end   / rightEdge) * 100;
        stops.push(`${tierColors[startTier]} ${startPct.toFixed(2)}%`);
        stops.push(`${tierColors[startTier]} ${endPct.toFixed(2)}%`);
    }
    const fill = document.getElementById("rangeBarTierFill");
    if (fill) {
        fill.style.background = `linear-gradient(to right, ${stops.join(", ")})`;
        fill.style.opacity = "0.85";
    }

    // Min endpoint dot (positioned by min's actual value; tier-colored by cls)
    const minDot = document.getElementById("rangeBarMin");
    const maxDot = document.getElementById("rangeBarMax");
    const avgMark = document.getElementById("rangeBarAvg");
    if (noData) {
        // Park the markers at the corners and dim them so an empty panel
        // doesn't look like a measurable worst-case result.
        if (minDot)  { minDot.style.left = "0%";   minDot.dataset.tier = "none"; minDot.style.opacity = "0.3"; }
        if (maxDot)  { maxDot.style.left = "100%"; maxDot.dataset.tier = "none"; maxDot.style.opacity = "0.3"; }
        if (avgMark) { avgMark.style.left = "0%";  avgMark.style.opacity = "0.3"; }
    } else {
        if (minDot)  { minDot.style.left = `${toPct(safeMin).toFixed(2)}%`; minDot.dataset.tier = cls(safeMin).tier; minDot.style.opacity = ""; }
        if (maxDot)  { maxDot.style.left = `${toPct(safeMax).toFixed(2)}%`; maxDot.dataset.tier = cls(safeMax).tier; maxDot.style.opacity = ""; }
        // Avg marker (cyan triangle)
        if (avgMark) { avgMark.style.left = `${toPct(safeAvg).toFixed(2)}%`; avgMark.style.opacity = ""; }
    }

    // ---- Spread & stability ----
    const spread = Math.max(0, safeMax - safeMin);
    const ratio  = safeMin > 0 ? (safeMax / safeMin) : 0;
    const spreadValEl = document.getElementById("distSpreadVal");
    const ratioEl = document.getElementById("distSpreadRatio");
    const dotsEl = document.getElementById("distStabilityDots");

    if (noData) {
        if (spreadValEl) spreadValEl.innerText = "-- ms";
        if (ratioEl)     ratioEl.innerText = "(--\u00d7 worse)";
        if (dotsEl) {
            dotsEl.innerText = "\u25cb\u25cb\u25cb\u25cb\u25cb";
            dotsEl.style.color = "";
            dotsEl.title = "Stability: no measurement yet";
            dotsEl.setAttribute("aria-label", "Stability: no measurement yet");
        }
    } else {
        const fillTier = cls(safeAvg).color;
        if (spreadValEl) spreadValEl.innerText = `${spread.toFixed(1)} ms`;
        if (ratioEl) {
            if (ratio < 1.01) ratioEl.innerText = "(negligible)";
            else ratioEl.innerText = `(${ratio.toFixed(2)}\u00d7 worse)`;
        }

        // Stability = relative spread (max-min)/avg. Five anchored buckets so
        // the dots are stable across runs. <0.10 = "rock-solid", >2.00 = "chaotic".
        const relSpread = safeAvg > 0 ? spread / safeAvg : 0;
        let filled;
        if      (relSpread < 0.10) filled = 5;
        else if (relSpread < 0.50) filled = 4;
        else if (relSpread < 1.00) filled = 3;
        else if (relSpread < 2.00) filled = 2;
        else                       filled = 1;

        const stabilityWords = ["", "chaotic", "jittery", "moderate", "stable", "very stable"];
        const word = stabilityWords[filled] || "moderate";
        const dots = "\u25cf".repeat(filled) + "\u25cb".repeat(5 - filled);
        if (dotsEl) {
            dotsEl.innerText = dots;
            dotsEl.style.color = fillTier;
            dotsEl.title = `Stability: ${word} (relative spread ${relSpread.toFixed(2)})`;
            // Screen-reader-friendly text alternative. The dots are decoration;
            // the meaning is in this label.
            dotsEl.setAttribute("aria-label", `Stability: ${word} (${filled} of 5)`);
        }
    }
}

// ==========================================================================
// LIVE LATENCY BENCHMARK RUNNER
// ==========================================================================
async function runLatencyTest() {
    const btn = document.getElementById("btnRunLatencyTest");
    if (!btn) return;

    btn.disabled = true;
    btn.innerHTML = `<span class="pulse-dot"></span> Benchmarking CLOB Latency...`;
    isTestActive = true;

    try {
        const resp = await fetch("/api/measure_latency?t=" + Date.now());
        if (!resp.ok) throw new Error("API response error");
        const data = await resp.json();

        const httpStats = data.latency?.http_rtt_ms || { avg: 0, min: 0, max: 0 };
        const wsStats = data.latency?.ws_rtt_ms || { avg: 0, ok: false };

        // ----- HTTP REST LATENCY DISTRIBUTION PANEL (best / avg / worst on a bar) -----
        renderDistributionPanel(httpStats.min, httpStats.avg, httpStats.max);

        // ----- WebSocket card (server-side via real PING/PONG frames) -----
        const wsCard = document.getElementById("kpiWsAvg");
        if (wsCard) {
            if (wsStats.ok === false) {
                wsCard.innerText = "-- ms (unavailable)";
                wsCard.title = `WebSocket measurement unavailable: ${wsStats.error || 'no successful pings'} (${wsStats.url || ''})`;
            } else {
                const wsAvg = wsStats.avg || 0;
                const wsCompleted = wsStats.samples_completed || 0;
                const wsAttempted = wsStats.samples_attempted || 0;
                wsCard.innerText = `${wsAvg.toFixed(1)} ms`;
                wsCard.title = `${wsCompleted}/${wsAttempted} ping samples completed; ${wsStats.url || ''}`;
            }
        }

        // Update Gauge Needle (it shares classifyTier() with the dist panel)
        renderGaugeMeter(httpStats.avg);

        // Update Slippage Table
        const m5Slippage = data.markets?.["5m_markets"]?.slippage_pct || {};
        const m15Slippage = data.markets?.["15m_markets"]?.slippage_pct || {};
        const sizes = ["$10", "$25", "$50", "$100", "$250"];

        let html = "";
        const tooltipByTier = {
            clean: '<strong>Zero Friction.</strong> VWAP impact &lt; 0.01% &mdash; your trade would fill at or extremely near the best ask. <em>Note: this only covers depth cost; a high-latency run can still let the price move before your order lands.</em>',
            low: '<strong>Low Friction.</strong> VWAP impact 0.01%&ndash;0.30%. Small premium &mdash; cents on the dollar for a $100 bankroll, well within tolerance.',
            med: '<strong>Moderate Friction.</strong> VWAP impact &gt; 0.30%. The orderbook is thin. Consider sizing down or waiting for a deeper book before copying this size.'
        };
        const ariaByTier = {
            clean: 'Zero Friction, VWAP impact under 0.01 percent.',
            low: 'Low Friction, VWAP impact 0.01 to 0.30 percent.',
            med: 'Moderate Friction, VWAP impact greater than 0.30 percent.'
        };
        sizes.forEach(size => {
            const v5 = m5Slippage[size] ?? 0;
            const v15 = m15Slippage[size] ?? 0;
            const maxVal = Math.max(v5, v15);
            let badgeHtml, tipKey;
            if (maxVal > 0.3) { badgeHtml = '<span class="friction-badge badge-med" role="img" aria-label="' + ariaByTier.med + '">Moderate Friction</span>'; tipKey = 'med'; }
            else if (maxVal > 0.0) { badgeHtml = '<span class="friction-badge badge-low" role="img" aria-label="' + ariaByTier.low + '">Low Friction</span>'; tipKey = 'low'; }
            else { badgeHtml = '<span class="friction-badge badge-clean" role="img" aria-label="' + ariaByTier.clean + '">Zero Friction</span>'; tipKey = 'clean'; }

            html += `
                <tr>
                    <td class="size-col">${size}.00</td>
                    <td>${v5.toFixed(2)}%</td>
                    <td>${v15.toFixed(2)}%</td>
                    <td><span class="friction-badge-wrapper" tabindex="0" role="group">${badgeHtml}<span class="friction-tooltip" role="tooltip">${tooltipByTier[tipKey]}</span></span></td>
                </tr>
            `;
        });
        document.getElementById("slippageTableBody").innerHTML = html;

        document.getElementById("lblLastTested").innerText = `Last Tested: ${new Date().toLocaleTimeString()}`;
    } catch (err) {
        console.error("Latency benchmark error:", err);
        alert("Benchmark test failed: " + err.message);
    } finally {
        isTestActive = false;
        btn.disabled = false;
        btn.innerHTML = `<span class="btn-icon">⚡</span> Run Live Benchmark Test`;
    }
}

