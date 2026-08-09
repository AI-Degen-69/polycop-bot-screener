let allTargets = [];
let filteredTargets = [];
let currentModalIndex = 0;
let currentModalAddr = "";
let radarChartInstance = null;
let showGemsOnly = false;

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

    document.addEventListener("keydown", (e) => {
        const modal = document.getElementById("detailModal");
        if (!modal || !modal.classList.contains("active")) return;
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

// ==========================================================================
// TAB NAVIGATION & LATENCY PROFILER PAGE INTERACTIVITY
// ==========================================================================
let globeAnimFrameId = null;
let packetsList = [];
let isTestActive = false;

function switchTab(tabId) {
    console.log("Switching tab to:", tabId);
    document.querySelectorAll(".sidebar-nav .nav-item").forEach(btn => btn.classList.remove("active"));
    document.querySelectorAll(".page-view").forEach(view => view.classList.remove("active"));

    if (tabId === "screener") {
        document.getElementById("navScreener")?.classList.add("active");
        document.getElementById("pageScreener")?.classList.add("active");
    } else if (tabId === "latency") {
        document.getElementById("navLatency")?.classList.add("active");
        document.getElementById("pageLatency")?.classList.add("active");
        try {
            initGlobeAnimation();
            renderGaugeMeter(370.75); // Initial sample gauge state
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

    // Gauge Meter Needle Angle Calculation
    let pct = 0;
    let tierText = "🟡 AVERAGE";
    let tierClass = "tier-average";

    if (rttMs < 100) {
        pct = (rttMs / 100) * 0.2;
        tierText = "⚡ FAST";
        tierClass = "tier-fast";
    } else if (rttMs < 250) {
        pct = 0.2 + ((rttMs - 100) / 150) * 0.2;
        tierText = "🟢 GOOD";
        tierClass = "tier-good";
    } else if (rttMs < 500) {
        pct = 0.4 + ((rttMs - 250) / 250) * 0.2;
        tierText = "🟡 AVERAGE";
        tierClass = "tier-average";
    } else if (rttMs < 1000) {
        pct = 0.6 + ((rttMs - 500) / 500) * 0.2;
        tierText = "🟠 SLOW";
        tierClass = "tier-slow";
    } else {
        pct = 0.8 + Math.min(0.2, ((rttMs - 1000) / 1000) * 0.2);
        tierText = "🔴 POOR";
        tierClass = "tier-poor";
    }

    const needleAngle = Math.PI + (pct * Math.PI);

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

    // Update Status Badge Element
    const badgeEl = document.getElementById("latencyStatusBadge");
    if (badgeEl) {
        badgeEl.className = `latency-badge ${tierClass}`;
        badgeEl.innerText = `${tierText} (${rttMs.toFixed(1)} ms)`;
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
        const wsStats = data.latency?.ws_rtt_ms || { avg: 0 };

        document.getElementById("kpiHttpAvg").innerText = `${httpStats.avg.toFixed(1)} ms`;
        document.getElementById("kpiHttpMin").innerText = `${httpStats.min.toFixed(1)} ms`;
        document.getElementById("kpiHttpMax").innerText = `${httpStats.max.toFixed(1)} ms`;
        document.getElementById("kpiWsAvg").innerText = `${wsStats.avg.toFixed(1)} ms`;

        // Update Gauge Needle
        renderGaugeMeter(httpStats.avg);

        // Update Slippage Table
        const m5Slippage = data.markets?.5m_markets?.slippage_pct || {};
        const m15Slippage = data.markets?.15m_markets?.slippage_pct || {};
        const sizes = ["$10", "$25", "$50", "$100", "$250"];

        let html = "";
        sizes.forEach(size => {
            const v5 = m5Slippage[size] ?? 0;
            const v15 = m15Slippage[size] ?? 0;
            const maxVal = Math.max(v5, v15);
            let badgeHtml = '<span class="friction-badge badge-clean">Zero Friction</span>';
            if (maxVal > 0.3) badgeHtml = '<span class="friction-badge badge-med">Moderate Friction</span>';
            else if (maxVal > 0.0) badgeHtml = '<span class="friction-badge badge-low">Low Friction</span>';

            html += `
                <tr>
                    <td class="size-col">${size}.00</td>
                    <td>${v5.toFixed(2)}%</td>
                    <td>${v15.toFixed(2)}%</td>
                    <td>${badgeHtml}</td>
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

