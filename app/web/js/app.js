let allTargets = [];
let filteredTargets = [];
let currentModalIndex = 0;
let currentModalAddr = "";
let radarChartInstance = null;
let showGemsOnly = false;

document.addEventListener("DOMContentLoaded", () => {
    loadDataset();
    document.getElementById("searchInput").addEventListener("input", filterAndRender);
    document.getElementById("sortSelect").addEventListener("change", filterAndRender);
    document.getElementById("btnToggleGem").addEventListener("click", toggleGemsFilter);
    document.getElementById("btnStartScan").addEventListener("click", startLeaderboardScan);
    document.getElementById("btnClearData").addEventListener("click", clearScanData);

    document.addEventListener("keydown", (e) => {
        const modal = document.getElementById("detailModal");
        if (!modal.classList.contains("active")) return;
        if (e.key === "Escape") closeModal();
        if (e.key === "ArrowLeft") navigateModal(-1);
        if (e.key === "ArrowRight") navigateModal(1);
    });
});

async function loadDataset() {
    try {
        const resp = await fetch("/data/phase2_verified_targets.json?t=" + Date.now(), { cache: "no-store" });
        if (!resp.ok) throw new Error("Dataset file not found");
        const data = await resp.json();
        allTargets = data.verified_targets || [];
        updateSummaryHeader(data);
        filterAndRender();
    } catch (e) {
        console.warn("Could not load /data/phase2_verified_targets.json:", e);
        allTargets = [];
        updateSummaryHeader({});
        document.getElementById("walletsGrid").innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 3rem; color: #9ca3af;">
                <h3>⚠️ No Cached Scan Data Found</h3>
                <p style="margin-top: 0.5rem;">Click <strong>⚡ Scan Leaderboard API</strong> above to perform an automated scan of all PolyCop profiles with PolyCop Score > 60.</p>
            </div>
        `;
    }
}

function updateSummaryHeader(data = {}) {
    const totalScanned = data.total_scraped_profiles ?? (allTargets.length > 0 ? allTargets.length : 0);
    const totalVerified = data.total_verified_targets ?? allTargets.length;
    const sTierCount = data.s_tier_count ?? allTargets.filter(t => t.final_score >= 90).length;
    const gemsCount = data.hidden_gems_count ?? allTargets.filter(t => t.is_hidden_gem).length;

    document.getElementById("statTotalScanned").innerText = totalScanned;
    document.getElementById("statVerified").innerText = totalVerified;
    document.getElementById("statSTier").innerText = sTierCount;
    document.getElementById("statGems").innerText = gemsCount;
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
        return matchesSearch && matchesGem;
    });

    if (sortVal === "score-desc") filteredTargets.sort((a, b) => b.final_score - a.final_score);
    else if (sortVal === "score-asc") filteredTargets.sort((a, b) => a.final_score - b.final_score);
    else if (sortVal === "pnl-desc") filteredTargets.sort((a, b) => b.metrics.copy_pnl - a.metrics.copy_pnl);
    else if (sortVal === "wr-desc") filteredTargets.sort((a, b) => b.metrics.r20_win_rate - a.metrics.r20_win_rate);
    else if (sortVal === "polycop-desc") filteredTargets.sort((a, b) => b.metrics.polycop_site_score - a.metrics.polycop_site_score);

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
                    <div class="summary-cell">
                        <span class="summary-lbl">Grade</span>
                        <span class="summary-val" style="color: var(--accent-cyan)">${t.grade.split(' ')[0]}</span>
                    </div>
                    <div class="summary-cell">
                        <span class="summary-lbl">Recent 20 Win Rate</span>
                        <span class="summary-val">${t.metrics.r20_win_rate}%</span>
                    </div>
                    <div class="summary-cell">
                        <span class="summary-lbl">Avg Invest</span>
                        <span class="summary-val">$${t.metrics.avg_invest}</span>
                    </div>
                </div>
            </div>
        `;
    }).join("");
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
    document.getElementById("modalGradeBadge").innerText = target.grade;
    document.getElementById("modalScreenerScore").innerText = `${target.final_score} / 100 Pts`;
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

async function startLeaderboardScan() {
    const overlay = document.getElementById("scanOverlay");
    const progressFill = document.getElementById("scanProgressFill");
    const logFeed = document.getElementById("scanLogFeed");
    const statusText = document.getElementById("scanStatusText");

    overlay.classList.add("active");
    logFeed.innerHTML = "=== STARTING AUTOMATED POLYCOP LEADERBOARD SCAN ===<br>";
    logFeed.innerHTML += "Executing Python Phase 1 & Phase 2 Pipeline on backend...<br>";
    progressFill.style.width = "25%";

    try {
        logFeed.innerHTML += "Scraping PolyCop leaderboard API and screening wallets against hard gates...<br>";
        progressFill.style.width = "50%";

        const resp = await fetch("/api/rescan");
        if (!resp.ok) {
            const errData = await resp.json().catch(() => ({}));
            throw new Error(errData.error || `Server returned status ${resp.status}`);
        }

        const data = await resp.json();
        allTargets = data.verified_targets || [];

        progressFill.style.width = "90%";
        logFeed.innerHTML += `Screening complete! <strong>${allTargets.length} verified targets PASS 100% of hard rejection gates.</strong><br>`;
        logFeed.innerHTML += `Dataset successfully saved to disk (app/data/phase2_verified_targets.json).<br>`;
        logFeed.scrollTop = logFeed.scrollHeight;

        // Reset gems filter so user sees all targets immediately
        if (showGemsOnly) {
            showGemsOnly = false;
            const btn = document.getElementById("btnToggleGem");
            if (btn) {
                btn.classList.remove("active");
                const labelSpan = btn.querySelector(".btn-label");
                if (labelSpan) labelSpan.innerHTML = '💎 Hidden Gems Only';
            }
        }

        updateSummaryHeader(data);
        filterAndRender();

        progressFill.style.width = "100%";
        statusText.innerText = "Scan Complete!";

        setTimeout(() => {
            overlay.classList.remove("active");
        }, 1200);

    } catch (e) {
        logFeed.innerHTML += `<span style="color:#ef4444">Scan Error: ${e.message}</span><br>`;
        statusText.innerText = "Scan Failed!";
        setTimeout(() => overlay.classList.remove("active"), 2500);
    }
}

async function clearScanData() {
    if (!confirm("Are you sure you want to clear all cached scan datasets?")) return;
    try {
        const resp = await fetch("/api/clear_data");
        const data = await resp.json();
        alert(data.message || "Data cache cleared.");
        window.location.reload();
    } catch (e) {
        alert("Failed to clear scan data: " + e.message);
    }
}
