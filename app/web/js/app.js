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
//
// The feed is the server's compact v1 projection, not the raw scan file: the
// raw file is ~6 MB and 92% of it is a skip log the page shows 12 rows of.
// The projection caps those lists and carries the true totals alongside, so
// the "…and N more" lines below stay honest.
//
// The cap of 12 below must stay equal to MODAL_LIST_CAP in
// app/src/server/feed_projection.py — the server caps the lists, the page
// renders the cap.
const FEED_URL = "/api/feed/v1";

function normaliseTarget(row) {
    // The rest of the page was written against the triage feed's field names.
    // Map once here rather than touching every reader.
    return Object.assign({}, row, {
        final_score: row.triage_copyability_score ?? 0,
        grade: row.triage_grade || "Ungraded"
    });
}

function renderCapSweepSummary(data) {
    // How many backtested wallets would upgrade tier at each wider per-position
    // cap. The pipeline counts the upgrades against each wallet's headline
    // tier, so the browser only renders the counts — no second engine.
    const upgrades = data.cap_sweep_upgrades || [];
    const backtested = data.cap_sweep_backtested || 0;
    // With nothing backtested there is no answer to show. With backtests but
    // zero upgrades, the zero chips below are the answer — it must not be
    // hidden just because no wallet changed tier.
    if (backtested === 0) return "";

    const profile = data.copy_execution_profile || {};
    // The pipeline states the baseline cap it compared against, so the label
    // matches the measurement even when the binding cap differs from the
    // stated per-token field.
    const baseline = data.cap_sweep_baseline_cap !== undefined
        ? `$${Number(data.cap_sweep_baseline_cap).toFixed(0)}`
        : (profile.per_token_cap_usd !== undefined
            ? `$${Number(profile.per_token_cap_usd).toFixed(0)}`
            : "the current cap");
    const chips = upgrades.map(u => {
        const n = Number(u.upgrades);
        const cls = n > 0 ? "capsweep-chip" : "capsweep-chip is-zero";
        const label = n > 0 ? `+${n}` : "0";
        const tip = `${n} of ${backtested} backtested wallet${backtested === 1 ? "" : "s"} earn a better tier at a $${Number(u.cap_usd).toFixed(0)} cap`;
        return `<span class="${cls}" title="${tip}">${label} @ $${Number(u.cap_usd).toFixed(0)}</span>`;
    }).join(" ");

    return `
        <div class="provenance-capsweep"
             title="A wallet upgrades when the tier its backtest earns at a wider per-position cap outranks its headline tier.">
            <span class="provenance-capsweep-label">💸 Position Cap Backtest</span>
            ${chips}
            <span class="provenance-capsweep-note">of ${backtested} backtested, vs the ${baseline} cap</span>
        </div>
    `;
}

function renderProvenanceBanner(data) {
    const banner = document.getElementById("provenanceBanner");
    if (!banner) return;

    const profile = data.copy_execution_profile || {};
    const ratio = profile.copy_ratio !== undefined ? `${(profile.copy_ratio * 100).toFixed(1)}%` : "—";
    const bankroll = profile.bankroll_usd !== undefined ? `$${profile.bankroll_usd}` : "—";
    const slippage = profile.slippage_pct !== undefined ? `${profile.slippage_pct}%` : "—";
    const fingerprint = profile.fingerprint ? profile.fingerprint.slice(0, 12) : "unknown";
    const capSweepLine = renderCapSweepSummary(data);

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
        // A degraded scan can be partial: wallets simulated before the outage
        // keep their verdicts, and only the unreached ones fall back to triage
        // order. The banner must not tell a reader that no tier on the page is
        // simulated when some are.
        const anySimulated = (data.simulated_targets || []).some(t => t.verdict_source === "simulation");
        const headline = anySimulated
            ? "⚠️ Simulation interrupted — some wallets are triage order only"
            : "⚠️ Showing triage order, not simulated results";
        // fallback_reason comes from caught sweep exceptions and failed fetch
        // errors, so it must be escaped before the banner interpolates it
        // (CodeRabbit review, PR #28).
        const fallbackReason = data.fallback_reason ? `: ${escapeHtml(data.fallback_reason)}` : "";
        const detail = anySimulated
            ? `The endpoint stopped answering mid-scan${fallbackReason}. Wallets simulated before the outage keep their verdicts; the rest are ordered by Copyability Score, which triages candidates but is not a verdict.`
            : `The simulation could not run${fallbackReason}. Wallets below are ordered by Copyability Score, which triages candidates but is not a verdict. No Tier on this page was produced by a simulation.`;
        banner.innerHTML = `
            <div class="provenance-headline">${headline}</div>
            <div class="provenance-detail">${detail}</div>
            ${profileLine}
            ${capSweepLine}
        `;
    } else {
        banner.className = "provenance-banner";
        banner.innerHTML = `
            <div class="provenance-headline">Ranked by simulated performance on your bankroll</div>
            ${profileLine}
            ${capSweepLine}
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
        // The scan's cap levels feed the modal control's default, so the
        // control always reflects what the scan actually ran.
        if (data.cap_sweep_levels && data.cap_sweep_levels.length > 0) {
            scanCapLevels = data.cap_sweep_levels;
        }
        if (data.cap_sweep_baseline_cap !== undefined) {
            capSweepBaselineCap = data.cap_sweep_baseline_cap;
        }
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
    else if (sortVal === "pnl-desc") {
        // The verdict's PnL is the simulated figure. An unsimulated wallet has
        // no simulated PnL to rank on, so it sorts below every simulated
        // wallet rather than being treated as a zero.
        filteredTargets.sort((a, b) =>
            ((b.simulated_copy_pnl_10 ?? -Infinity) - (a.simulated_copy_pnl_10 ?? -Infinity)));
    }
    else if (sortVal === "wr-desc") filteredTargets.sort((a, b) => (b.metrics.days_win_rate || 0) - (a.metrics.days_win_rate || 0));
    else if (sortVal === "polycop-desc") filteredTargets.sort((a, b) => (b.metrics.aggregator_opinion || 0) - (a.metrics.aggregator_opinion || 0));
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

function renderVerdictMetricCell(t, field, label, format) {
    // A verdict figure no simulation produced is not a figure of zero: the
    // row says so, telling a triage-only row from a measured verdict row.
    // `format` renders the measured value (percent by default; PnL passes a
    // dollar formatter).
    const fmt = format || ((v) => `${v}%`);
    const val = t[field];
    if (t.verdict_source !== "simulation") {
        return `
            <div class="summary-cell">
                <span class="summary-lbl">${label}</span>
                <span class="summary-val tier-unsimulated">Not simulated</span>
            </div>
        `;
    }
    if (val === null || val === undefined) {
        return `
            <div class="summary-cell">
                <span class="summary-lbl">${label}</span>
                <span class="summary-val tier-unsimulated">Not measured</span>
            </div>
        `;
    }
    return `
        <div class="summary-cell">
            <span class="summary-lbl">${label}</span>
            <span class="summary-val">${fmt(val)}</span>
        </div>
    `;
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

function renderRankCell(t) {
    // Where the wallet sits in this scan, alongside its verdict. Stamped by
    // the pipeline from the final ordering, so it is never recomputed here.
    if (t.scan_rank === null || t.scan_rank === undefined) {
        return `
            <div class="summary-cell">
                <span class="summary-lbl">Scan Rank</span>
                <span class="summary-val tier-unsimulated">—</span>
            </div>
        `;
    }
    return `
        <div class="summary-cell">
            <span class="summary-lbl">Scan Rank</span>
            <span class="summary-val rank-number">#${t.scan_rank}</span>
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
        const gemBadgeHtml = isGem ? `                <div class="badge-gem-wrapper">
                <span class="badge-gem">💎 GEM</span>
                <div class="gem-tooltip-text">
                    <strong>💎 Hidden Gem Detected!</strong><br>
                    PolyCop under-rated site score (&lt;75), but passes all 7 Hard Rejection Gates with an <strong>A-Tier Screener Score (&ge;71)</strong>!
                </div>
            </div>
        ` : '';

        const lastActive = formatLastActive(t);
        // How the wallet was measured, as distinct from what the measurement
        // said. A score built on six hours of fills and one built on four
        // months are not comparable, and a reader can only know which is which
        // if the card says so (ADR 0012, feed v2).
        const annotations = t.annotations || {};
        const coverageDays = annotations.coverage_days;
        const provenanceBits = [];
        if (annotations.classification) {
            provenanceBits.push(annotations.classification === "bot" ? "🤖 bot-shaped" : "🧑 human-shaped");
        }
        if (typeof coverageDays === "number") {
            provenanceBits.push(`${coverageDays.toFixed(0)}d measured`);
        }
        if (annotations.history_truncated) {
            provenanceBits.push("⚠️ truncated window");
        }
        const provenanceHtml = provenanceBits.length ? `
            <div class="wallet-card-provenance" title="How this wallet was measured, from its own Polymarket fills">
                ${provenanceBits.join(" · ")}
            </div>
        ` : '';
        // Measured from the wallet's own fills: the share of them struck at
        // 3c/97c. It replaces an average buy price the aggregator reported,
        // and it is the sharper signal — an average hides a wallet that mixes
        // real positions with near-certainties, and a share does not.
        const extremeShare = t.metrics ? t.metrics.extreme_price_share : null;
        const highBuyBadgeHtml = (typeof extremeShare === "number" && extremeShare > 0.15) ? `
            <div class="badge-high-buy-wrapper" style="display:inline-block;">
                <span class="badge-high-buy">⚠️ Extremes ${(extremeShare * 100).toFixed(0)}%</span>
                <div class="gem-tooltip-text" style="border-color: #f59e0b;">
                    <strong>⚠️ ${(extremeShare * 100).toFixed(0)}% of fills at 3c/97c!</strong><br>
                    A wallet buying near-certainties wins often and gains almost nothing per fill —
                    the shape that tops the leaderboard and cannot be copied.
                    Set <strong>Max Price: 0.95</strong> in backtest controls.
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
                        ${provenanceHtml}
                    </div>
                    <div class="score-badge">${t.final_score} Pts</div>
                </div>
                <div class="card-metrics-summary">
                    <div class="summary-cell">
                        <span class="summary-lbl">Modelled Copy PnL</span>
                        <span class="summary-val" style="color: ${t.metrics.copy_pnl >= 0 ? '#10b981' : '#ef4444'}">
                            $${t.metrics.copy_pnl.toLocaleString('en-US', {minimumFractionDigits: 2})}
                        </span>
                    </div>
                    ${renderVerdictMetricCell(t, 'simulated_copy_pnl_10', 'Simulated Copy PnL',
                        (v) => '$' + v.toLocaleString('en-US', {minimumFractionDigits: 2}))}
                    ${renderTierCell(t)}
                    ${renderRetentionCell(t)}
                    <div class="summary-cell">
                        <span class="summary-lbl">Copyable Window Share</span>
                        <span class="summary-val">${formatShare(t.copyable_window_share)}</span>
                    </div>
                    ${renderVerdictMetricCell(t, 'simulated_daily_green_rate', 'Simulated Daily Green')}
                    ${renderVerdictMetricCell(t, 'simulated_max_drawdown', 'Simulated Drawdown')}
                    <div class="summary-cell">
                        <span class="summary-lbl">Avg Invest</span>
                        <span class="summary-val">$${t.metrics.avg_invest}</span>
                    </div>
                    ${renderRankCell(t)}
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
    // entry here is a miss and an empty list means the bankroll held. The feed
    // caps this list at 12 and carries the true total alongside, so the count
    // and the "…and N more" line use the total, never the cap.
    const missed = target.balance_miss_details || [];
    const missedTotal = target.balance_miss_total ?? missed.length;
    if (missedTotal === 0) {
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
        <div class="bm-headline">⚠️ ${missedTotal} trade${missedTotal === 1 ? "" : "s"} missed for lack of balance</div>
        ${rows}
        ${missedTotal > 12 ? `<div class="bm-empty">…and ${missedTotal - 12} more.</div>` : ""}
    `;
}

function renderSkipReasons(target) {
    // The simulation's decision log, condensed to the refusals — the entries
    // where an entry signal did not become a copy. The message names the
    // failing filter, so a reader sees why a trade was skipped rather than
    // inferring it (spec #13).
    const host = document.getElementById("modalSkipReasons");
    if (!host) return;

    if (target.verdict_source !== "simulation") {
        host.innerHTML = `<div class="bm-empty">No Simulated Copy Run, so no skip log exists.</div>`;
        return;
    }

    // The feed caps this list at 12 and carries the true total alongside, so
    // the count and the "…and N more" line use the total, never the cap.
    const reasons = target.skip_reasons || [];
    const reasonsTotal = target.skip_reasons_total ?? reasons.length;
    if (reasonsTotal === 0) {
        host.innerHTML = `<div class="bm-ok">✅ Every entry signal was copied — nothing was skipped.</div>`;
        return;
    }

    const actionLabels = { SKIP_FILTER: "Window refused", SKIP_CAP: "Risk cap" };
    const rows = reasons.slice(0, 12).map(r => `
        <div class="bm-row sr-row">
            <span class="bm-market">${escapeHtml(actionLabels[r.action] || r.action)}</span>
            <span class="bm-amount">${escapeHtml(r.msg || "")}</span>
        </div>
    `).join("");

    host.innerHTML = `
        <div class="bm-headline">⚠️ ${reasonsTotal} signal${reasonsTotal === 1 ? "" : "s"} did not become a copy</div>
        ${rows}
        ${reasonsTotal > 12 ? `<div class="bm-empty">…and ${reasonsTotal - 12} more.</div>` : ""}
    `;
}

// --- Position Cap Backtest card: canned scan levels + custom-caps control ---
// The card's row markup is shared by the canned view (levels the scan
// published) and the custom view (levels the control just backtested live),
// so the two can never render the same number differently.

// The scan's cap levels and baseline come from the feed, so the control's
// default matches what the scan actually ran, whatever they are.
let scanCapLevels = [5, 10, 15, 20];
let capSweepBaselineCap = 5;

// The last successful custom-caps run is remembered across reloads so the
// control pre-fills with it next visit. Storage can be unavailable (private
// mode, disabled), so every access is guarded — the control just forgets.
const CAP_CAPS_STORAGE_KEY = "polycopCapBacktestCaps";

function loadSavedCustomCaps() {
    try {
        const raw = localStorage.getItem(CAP_CAPS_STORAGE_KEY);
        if (!raw) return null;
        const parsed = parseCapsInput(raw);
        if (parsed.caps) return parsed.caps.join(", ");
        // A stored value that no longer parses is pruned rather than left to
        // fail silently on every visit.
        localStorage.removeItem(CAP_CAPS_STORAGE_KEY);
        return null;
    } catch (e) {
        return null;
    }
}

function saveCustomCaps(caps) {
    try {
        localStorage.setItem(CAP_CAPS_STORAGE_KEY, caps.join(", "));
    } catch (e) {
        /* storage unavailable; the control just won't remember */
    }
}

function clearSavedCustomCaps() {
    try {
        localStorage.removeItem(CAP_CAPS_STORAGE_KEY);
    } catch (e) {
        /* ignore */
    }
}

function capSweepTierColor(tier) {
    // The app's own tier palette, not a second copy of the band logic: the
    // letter is already the pipeline's verdict; this only colours it.
    const letter = (tier || "F").split(" ")[0];
    if (letter.startsWith("S")) return "var(--tier-s)";
    if (letter.startsWith("A")) return "var(--tier-a)";
    if (letter.startsWith("B")) return "var(--tier-b)";
    return "var(--tier-c)";
}

function capSweepFmtPnl(v) {
    return (v === null || v === undefined) ? "—" : "$" + Number(v).toLocaleString("en-US", {maximumFractionDigits: 0});
}

function capSweepFmtRet(v) {
    return (v === null || v === undefined) ? "—" : (v * 100).toFixed(0) + "%";
}

// Display-only ordering of the pipeline's tier letters, used solely to colour
// the ▲/▼ move indicator in the custom-caps comparison. The letters are the
// pipeline's verdicts; this map never produces a verdict of its own.
const CAP_SWEEP_TIER_ORDER = { S: 5, A: 4, B: 3, C: 2, F: 1 };

function capSweepTierRank(tier) {
    if (!tier) return 0;
    return CAP_SWEEP_TIER_ORDER[tier.split(" ")[0][0]] || 0;
}

function capSweepRowsHtml(sweep, deltaHtmlFor) {
    // `deltaHtmlFor(s, i)` is optional: the canned view passes none (its rows
    // are the scan's published levels, shown as-is), the custom view passes a
    // per-level ▲/▼ decorator for the comparison.
    return sweep.map((s, i) => {
        const deltaHtml = deltaHtmlFor ? deltaHtmlFor(s, i) : "";
        return `
        <div class="cs-row">
            <span class="cs-cap">$${Number(s.cap_usd).toFixed(0)}</span>
            <span class="cs-window">≤ $${Number(s.window_max_usd).toFixed(0)}</span>
            <span class="cs-pnl">${s.is_rejected ? "—" : capSweepFmtPnl(s.simulated_copy_pnl_10)}</span>
            <span class="cs-ret">${s.is_rejected ? "rejected" : capSweepFmtRet(s.edge_retention)}</span>
            <span class="cs-tier" style="color:${capSweepTierColor(s.tier)}">${s.tier ? s.tier.split(" ")[0] : "F"}${deltaHtml}</span>
        </div>
    `;
    }).join("");
}

function capSweepControlHtml(resetVisible, defaultCaps) {
    // The input default is feed-derived, so it is escaped before reaching the
    // attribute the same way every other feed-derived string is.
    return `
        <div class="cs-control">
            <input id="csCustomCapsInput" class="cs-input" value="${escapeHtml(String(defaultCaps))}"
                   placeholder="e.g. 8, 20, 30" aria-label="Custom cap levels in dollars"
                   onkeydown="if (event.key === 'Enter') { rerunCapBacktest(); }" />
            <button class="cs-btn" onclick="rerunCapBacktest()" id="csRunBtn">⚡ Rerun at caps</button>
            <button class="cs-btn cs-btn-reset" onclick="resetCapBacktest()" id="csResetBtn" ${resetVisible ? "" : "hidden"}>↺ Scan caps</button>
        </div>
        <div id="csStatus" class="bm-empty" role="status"></div>
    `;
}

function renderCapSweep(target) {
    // The per-position cap backtest: the same wallet replayed under rising
    // caps ($5 / $10 / $15 / $20), so a reader sees how the verdict would
    // have moved if the position cap were wider. The card's headline tier
    // stays the $5 verdict; this shows the sensitivity.
    const host = document.getElementById("modalCapSweep");
    if (!host) return;

    if (target.verdict_source !== "simulation") {
        host.innerHTML = `<div class="bm-empty">No Simulated Copy Run, so no cap backtest exists.</div>`;
        return;
    }

    const sweep = target.cap_sweep || [];
    if (sweep.length === 0) {
        host.innerHTML = `<div class="bm-empty">No cap backtest was published for this wallet.</div>`;
        return;
    }
    if (sweep[0].error) {
        host.innerHTML = `<div class="bm-empty">Cap backtest unavailable: ${escapeHtml(sweep[0].error)}</div>`;
        return;
    }

    // The control's default is the remembered custom caps when there are
    // any; otherwise the scan's own wider levels, so a click without editing
    // re-runs what the scan already published.
    const defaultCaps = loadSavedCustomCaps() || (scanCapLevels
        .filter(c => Number(c) !== Number(capSweepBaselineCap))
        .join(", ") || "10, 15, 20");

    host.innerHTML = `
        <div class="cs-head">
            <span>Cap</span><span>Window</span><span>PnL @10%</span><span>Retention</span><span>Tier</span>
        </div>
        <div id="csRows">${capSweepRowsHtml(sweep)}</div>
        ${capSweepControlHtml(false, defaultCaps)}
        <div class="bm-empty" style="margin-top:6px">The headline tier is the $${Number(capSweepBaselineCap).toFixed(0)} verdict; a wider cap is the backtested alternative. Enter comma-separated caps to backtest this wallet live — the scan profile is not changed.</div>
    `;
}

function renderCapSweepCustom(levels, caps) {
    // The result of a live custom-caps run: the same rows, stamped as custom
    // so a reader can tell it from the scan's published levels. Each level's
    // tier is compared against the headline verdict (the $5 cap): ▲ means the
    // wallet would earn a strictly better tier at that cap, ▼ strictly worse.
    // The comparison anchor is the headline because custom caps rarely match
    // the scan's levels — a level-to-level pairing would mostly compare
    // nothing.
    const host = document.getElementById("modalCapSweep");
    if (!host || !levels || levels.length === 0) return;

    const target = filteredTargets[currentModalIndex];
    const headlineTier = (target && target.verdict_source === "simulation") ? target.tier : null;
    const headlineRank = headlineTier ? capSweepTierRank(headlineTier) : 0;
    const baselineLabel = `$${Number(capSweepBaselineCap).toFixed(0)}`;

    // Deltas are precomputed before the rows are rendered so the badge count
    // and the row arrows read the same pass.
    const deltas = levels.map(s => {
        const rank = capSweepTierRank(s.tier);
        if (headlineRank === 0 || rank === 0 || rank === headlineRank) return null;
        return rank > headlineRank ? "up" : "down";
    });
    const ups = deltas.filter(d => d === "up").length;
    const downs = deltas.filter(d => d === "down").length;
    const moveSummary = (ups === 0 && downs === 0)
        ? "no tier moves"
        : [ups ? `${ups} ▲ upgraded` : "", downs ? `${downs} ▼ downgraded` : ""].filter(Boolean).join(" · ");

    const deltaHtmlFor = (s, i) => {
        const delta = deltas[i];
        if (!delta) return "";
        const letter = (s.tier || "F").split(" ")[0];
        const headlineLetter = (headlineTier || "").split(" ")[0] || "?";
        const verb = delta === "up" ? "Upgrade" : "Downgrade";
        return ` <span class="cs-delta cs-delta-${delta}" title="${verb} vs the ${baselineLabel} verdict: ${headlineLetter} → ${letter}">${delta === "up" ? "▲" : "▼"}</span>`;
    };

    host.innerHTML = `
        <div class="cs-badge">Live backtest · ${moveSummary}</div>
        <div class="cs-head">
            <span>Cap</span><span>Window</span><span>PnL @10%</span><span>Retention</span><span>Tier</span>
        </div>
        <div id="csRows">${capSweepRowsHtml(levels, deltaHtmlFor)}</div>
        ${capSweepControlHtml(true, caps.join(", "))}
        <div class="bm-empty" style="margin-top:6px">Live backtest at custom caps — the scan profile defaults were not changed. ▲/▼ compare each level against the ${baselineLabel} headline verdict.</div>
    `;
}

function parseCapsInput(raw) {
    const parts = String(raw).split(",").map(p => p.trim()).filter(Boolean);
    if (parts.length === 0) return { error: "Enter at least one cap, e.g. 8, 20, 30." };
    const caps = [];
    for (const p of parts) {
        const v = Number(p);
        if (!Number.isFinite(v) || v <= 0) return { error: `"${p}" is not a positive dollar amount.` };
        caps.push(v);
    }
    // Mirrors the server's MAX_CUSTOM_CAP_LEVELS; the server is the enforcer,
    // this only catches the obvious typo before a fetch.
    if (caps.length > 6) return { error: "At most 6 caps per run." };
    return { caps: [...new Set(caps)].sort((a, b) => a - b) };
}

async function rerunCapBacktest() {
    // Backtest the wallet in the modal at the caps typed into the control.
    // The endpoint derives a profile per cap, so CURRENT_PROFILE — and every
    // verdict already on the page — is untouched.
    const input = document.getElementById("csCustomCapsInput");
    const btn = document.getElementById("csRunBtn");
    const status = document.getElementById("csStatus");
    if (!input || !btn || !status) return;

    const parsed = parseCapsInput(input.value);
    if (parsed.error) {
        status.classList.add("cs-error");
        status.textContent = parsed.error;
        return;
    }
    const caps = parsed.caps;
    const wallet = currentModalAddr;
    if (!wallet) return;

    btn.disabled = true;
    status.classList.remove("cs-error");
    status.textContent = `Running live backtest at $${caps.join(", $")}… (uncached caps simulate against the CLOB; may take a minute)`;

    try {
        const resp = await fetch(`/api/cap_backtest?wallet=${encodeURIComponent(wallet)}&caps=${encodeURIComponent(caps.join(","))}&t=${Date.now()}`);
        const data = await resp.json();
        if (!resp.ok || data.error) throw new Error(data.error || ("HTTP " + resp.status));
        if (wallet !== currentModalAddr) return; // the modal moved on; drop the stale result
        saveCustomCaps(caps);
        renderCapSweepCustom(data.levels, caps);
        status.textContent = "";
    } catch (err) {
        if (wallet === currentModalAddr) {
            status.classList.add("cs-error");
            status.textContent = "Backtest failed: " + err.message;
        }
    } finally {
        btn.disabled = false;
    }
}

function resetCapBacktest() {
    // Back to the scan's published levels for this wallet. Choosing the scan
    // caps also forgets the remembered custom caps, so the next visit starts
    // at the scan defaults again.
    clearSavedCustomCaps();
    const target = filteredTargets[currentModalIndex];
    if (target) renderCapSweep(target);
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
    document.getElementById("modalRankBadge").innerText = target.scan_rank ? `#${target.scan_rank}` : "—";
    document.getElementById("modalScreenerScore").innerText = `${target.final_score} / 100 Pts`;
    renderBalanceMiss(target);
    renderSkipReasons(target);
    renderCapSweep(target);
    const aggregatorOpinion = target.metrics.aggregator_opinion;
    // Labelled as an opinion because that is all it is now: it reaches no
    // gate and no scored parameter, and survives only so a Hidden Gem can be
    // defined as the two opinions disagreeing (ADR 0012).
    document.getElementById("modalPolyCopScore").innerText =
        (typeof aggregatorOpinion === "number") ? `${aggregatorOpinion} / 100 Site` : "not rated";
    
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
    // The copy-adjusted green-day rate, which is what the screen measures. The
    // recent-20 win rate it replaces came precomputed from the aggregator and
    // has no first-party equivalent.
    const greenRate = target.metrics.days_win_rate;
    document.getElementById("cardWinRate").innerText =
        (typeof greenRate === "number") ? `${greenRate.toFixed(1)}%` : "unmeasured";
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
    const labels = target.breakdown_labels || {};
    const points = target.breakdown_points || {};

    // The eleven parameters are keyed by stable ids (engine parameter order).
    // Labels and maxima come from the feed, so the UI has no hardcoded weight
    // or percentage literals — a reweight cannot leave the page stale.
    const keys = Object.keys(labels);
    if (!keys.some(k => b[k] !== undefined)) {
        container.innerHTML = `<div class="bm-empty">No breakdown was carried through for this wallet.</div>`;
        return;
    }

    container.innerHTML = keys.map(key => {
        const score = b[key] || 0.0;
        const max = points[key] || 0;
        const pct = max > 0 ? Math.min((score / max) * 100, 100) : 0;

        return `
            <div class="param-bar-item">
                <div class="param-bar-header">
                    <span class="param-bar-title">${labels[key] || key}</span>
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
    const labels = target.radar_labels || {};
    const points = target.breakdown_points || {};

    // Radar labels and maxima come from the feed, matching the stable ids.
    const keys = Object.keys(labels);
    const radarValues = keys.map(k => getScorePct(b[k] || 0, points[k] || 0));

    radarChartInstance = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: keys.map(k => labels[k]),
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
        // The endpoint returns the Phase 3 payload, which is what the feed
        // file now holds too, so the page rereads it through the one path
        // that knows how to normalise it. Reading the response here instead
        // meant a second copy of that knowledge, and it had already drifted:
        // it looked for `verified_targets`, which no payload has ever had,
        // so a finished scan emptied the grid it was supposed to fill.
        await loadDataset();
        alert(`Scan Complete!\nTargets evaluated: ${data.total_targets_evaluated ?? 0}\nSimulated survivors: ${data.simulated_survivors_count ?? 0}`);
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
window.rerunCapBacktest = rerunCapBacktest;
window.resetCapBacktest = resetCapBacktest;

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

