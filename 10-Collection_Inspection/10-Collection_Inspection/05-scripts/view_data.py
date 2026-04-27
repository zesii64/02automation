"""Data view patch set for Collection report HTML."""

import re


def apply_data_view_patches(html: str) -> str:
    """Apply Data-view specific HTML replacements (Anomaly, Recovery Trend cards, Agent Overview)."""
    # Subtab button label
    html = html.replace(
        "<button class=\"subtab-btn active\" id=\"subtab-anomaly\" onclick=\"switchDataSubTab('anomaly')\">Anomaly Detection</button>",
        "<button class=\"subtab-btn active\" id=\"subtab-anomaly\" onclick=\"switchDataSubTab('anomaly')\">Under-performing</button>",
    )
    # Add Agent Overview as the 3rd subtab
    html = html.replace(
        "<button class=\"subtab-btn\" id=\"subtab-trend\" onclick=\"switchDataSubTab('trend')\">Recovery Trend</button>",
        "<button class=\"subtab-btn\" id=\"subtab-trend\" onclick=\"switchDataSubTab('trend')\">Recovery Trend</button>\n                <button class=\"subtab-btn\" id=\"subtab-agent-overview\" onclick=\"switchDataSubTab('agent-overview')\">Agent Overview</button>",
    )

    # Group card heading + helper text
    html = html.replace(
        "Group — Continuous Unmet Target (3+ Days)",
        "Group — Continuous Unmet Target (2+ Weeks)",
    )
    html = html.replace(
        "Groups with 3+ consecutive days below daily target, sorted by consecutive days (descending).",
        "Groups with 2+ consecutive weeks below weekly target, sorted by consecutive weeks (descending).",
    )

    # Group empty-state copy
    html = html.replace(
        "No groups with 3+ consecutive unmet days",
        "No groups with 2+ consecutive unmet weeks",
    )

    # Agent card copy stays 3+ days, but fix subtitle wording.
    html = html.replace(
        "Agent — Continuous Unmet Target (3+ Days)",
        "Individual — Continuous Unmet Target (3+ Days)",
    )

    # ---- 13. loadTrendChart: actual/target -> rate + null-safe avg ----
    old_trend_vals = """\
                    if (d < dailyData.length) {
                        actualValues.push(dailyData[d].actual);
                        targetValues.push(dailyData[d].target);
                        avgDailyTarget += dailyData[d].target;
                        targetCount++;
                    } else {"""
    new_trend_vals = """\
                    if (d < dailyData.length) {
                        actualValues.push(dailyData[d].repayRate !== null && dailyData[d].repayRate !== undefined ? dailyData[d].repayRate : null);
                        targetValues.push(dailyData[d].targetRepayRate !== null && dailyData[d].targetRepayRate !== undefined ? dailyData[d].targetRepayRate : null);
                        if (dailyData[d].targetRepayRate !== null && dailyData[d].targetRepayRate !== undefined) {
                            avgDailyTarget += dailyData[d].targetRepayRate;
                            targetCount++;
                        }
                    } else {"""
    html = html.replace(old_trend_vals, new_trend_vals)

    # ---- 14. loadTrendChart: tooltip -> % ----
    html = html.replace(
        "                    tooltip: { trigger: 'axis', formatter: params => {\n                        return params[0].name + '<br>' + params.map(p => p.marker + p.seriesName + ': ' + (p.value ? formatNumber(p.value) : '-')).join('<br>');\n                    }},",
        "                    tooltip: { trigger: 'axis', formatter: params => {\n                        return params[0].name + '<br>' + params.map(p => p.marker + p.seriesName + ': ' + (p.value !== null && p.value !== undefined ? p.value.toFixed(2) + '%' : '-')).join('<br>');\n                    }},",
    )

    # ---- 15. loadTrendChart: Y-axis -> % ----
    html = html.replace(
        "                    yAxis: { type: 'value', axisLabel: { formatter: v => formatNumber(v), fontSize: 10 } },",
        "                    yAxis: { type: 'value', axisLabel: { formatter: v => v !== null && v !== undefined ? v.toFixed(2) + '%' : '', fontSize: 10 } },",
    )

    # ---- 16. loadTrendChart: card metric -> rate format ----
    html = html.replace(
        "                        '<span>Daily Target: ' + formatNumber(Math.round(avgDailyTarget)) + ' (Natural Month Repay)</span>' +",
        "                        '<span>Avg Daily Target Rate: ' + avgDailyTarget.toFixed(2) + '% (Natural Month Repay)</span>' +",
    )

    # ---- 16.1 loadTrendChart: remove "today" red dot marker ----
    html = re.sub(
        r"(?s)\n\s*markPoint:\s*\{\s*data:\s*\[\s*\{\s*coord:\s*\[currentDayOfMonth - 1,\s*actualValues\[currentDayOfMonth - 1\]\s*\|\|\s*0\],\s*value:\s*'Today',.*?symbolSize:\s*10\s*\}\s*",
        "\n",
        html,
        count=1,
    )
    html = html.replace(" Red line = today.", "")

    # ---- 22. riskModuleGroups table: PTP null-safe + Call Loss column ----
    html = html.replace(
        "g.ptpRate.toFixed(1) + '%</td>' +",
        "(g.ptpRate !== null && g.ptpRate !== undefined ? g.ptpRate.toFixed(1) + '%' : '--') + '</td>' +",
    )
    old_risk_row_end = (
        "                        '<td style=\"padding: 8px; text-align: right;\">' + g.attendance + '%</td>' +"
    )
    new_risk_row_end = (
        "                        '<td style=\"padding: 8px; text-align: right;\">' + (g.callLossRate !== null && g.callLossRate !== undefined ? g.callLossRate.toFixed(1) + '%' : '--') + '</td>' +"
        "\n                        '<td style=\"padding: 8px; text-align: right;\">' + g.attendance + '%</td>' +"
    )
    html = html.replace(old_risk_row_end, new_risk_row_end)
    old_risk_header = (
        "                        <th style=\"padding: 8px; text-align: right; background: #f1f5f9;\">Attendance</th>"
    )
    new_risk_header = (
        "                        <th style=\"padding: 8px; text-align: right; background: #f1f5f9;\">Call Loss</th>\n"
        "                        <th style=\"padding: 8px; text-align: right; background: #f1f5f9;\">Attendance</th>"
    )
    html = html.replace(old_risk_header, new_risk_header)

    # Recovery Trend / Risk review: hide M2 modules (requires getVisibleModules from TL #26b inject)
    html = html.replace(
        """            const daysInMonth = dateLabels.length;

            REAL_DATA.modules.forEach(module => {
                // Dynamic At-Risk calculation based on projection
                const risk = calculateAtRisk(module);""",
        """            const daysInMonth = dateLabels.length;

            getVisibleModules().forEach(module => {
                // Dynamic At-Risk calculation based on projection
                const risk = calculateAtRisk(module);""",
    )
    html = html.replace(
        """            const riskModules = [];
            REAL_DATA.modules.forEach(module => {
                const risk = calculateAtRisk(module);
                risk.module = module;
                if (risk.isAtRisk) {
                    riskModules.push(module);
                }
            });""",
        """            const riskModules = [];
            getVisibleModules().forEach(module => {
                const risk = calculateAtRisk(module);
                risk.module = module;
                if (risk.isAtRisk) {
                    riskModules.push(module);
                }
            });""",
    )

    # Rewrite Data View loader to use weekly-groups (2+ weeks) + individuals (3+ days); M2 filtered
    old_load_anomaly = """        function loadAnomalyData() {
            // Load Group anomaly data (3+ days only, sorted by days desc)
            const groupTbody = document.getElementById('anomaly-group-table');
            const groupEmpty = document.getElementById('anomaly-group-empty');
            groupTbody.innerHTML = '';
            const groups = [...REAL_DATA.anomalyGroups].filter(g => g.days >= 3).sort((a, b) => b.days - a.days);

            if (groups.length === 0) {
                groupEmpty.style.display = 'block';
            } else {
                groupEmpty.style.display = 'none';
                groups.forEach(item => {
                    const mtdAch = item.mtdTarget > 0 ? (item.mtdActual / item.mtdTarget * 100) : 0;
                    const achColor = mtdAch >= 100 ? '#22c55e' : mtdAch >= 90 ? '#d97706' : '#ef4444';
                    const dailyGap = item.dailyTarget - item.dailyActual;
                    groupTbody.innerHTML += '<tr class="drilldown-row red-row">' +
                        '<td style="padding: 12px; font-weight: 500;">' + item.name + '</td>' +
                        '<td style="padding: 12px; text-align: center;">' + item.module + '</td>' +
                        '<td style="padding: 12px; text-align: center; font-weight: 700; color: #ef4444;">' + item.days + '</td>' +
                        '<td style="padding: 12px; text-align: right;">' + formatNumber(item.dailyTarget) + '</td>' +
                        '<td style="padding: 12px; text-align: right;">' + formatNumber(item.dailyActual) + '</td>' +
                        '<td style="padding: 12px; text-align: right; color: #ef4444; font-weight: 600;">-' + formatNumber(dailyGap) + '</td>' +
                        '<td style="padding: 12px; text-align: right;">' + formatNumber(item.mtdTarget) + '</td>' +
                        '<td style="padding: 12px; text-align: right;">' + formatNumber(item.mtdActual) + '</td>' +
                        '<td style="padding: 12px; text-align: right; color: ' + achColor + '; font-weight: 600;">' + mtdAch.toFixed(1) + '%</td>' +
                        '</tr>';
                });
            }

            // Load Agent anomaly data (3+ days only, sorted by days desc)
            const agentTbody = document.getElementById('anomaly-agent-table');
            const agentEmpty = document.getElementById('anomaly-agent-empty');
            agentTbody.innerHTML = '';
            const agents = [...REAL_DATA.anomalyAgents].filter(a => a.days >= 3).sort((a, b) => b.days - a.days);

            if (agents.length === 0) {
                agentEmpty.style.display = 'block';
            } else {
                agentEmpty.style.display = 'none';
                agents.forEach(item => {
                    const dailyGap = item.dailyTarget - item.dailyActual;
                    agentTbody.innerHTML += '<tr class="drilldown-row red-row">' +
                        '<td style="padding: 12px; font-weight: 500;">' + item.name + '</td>' +
                        '<td style="padding: 12px;">' + item.group + '</td>' +
                        '<td style="padding: 12px; text-align: center;">' + item.module + '</td>' +
                        '<td style="padding: 12px; text-align: center; font-weight: 700; color: #ef4444;">' + item.days + '</td>' +
                        '<td style="padding: 12px; text-align: right;">' + formatNumber(item.dailyTarget) + '</td>' +
                        '<td style="padding: 12px; text-align: right;">' + formatNumber(item.dailyActual) + '</td>' +
                        '<td style="padding: 12px; text-align: right; color: #ef4444; font-weight: 600;">-' + formatNumber(dailyGap) + '</td>' +
                        '<td style="padding: 12px; text-align: right;">' + item.calls + '</td>' +
                        '<td style="padding: 12px; text-align: right;">' + item.connectRate.toFixed(1) + '%</td>' +
                        '<td style="padding: 12px; text-align: right;">' + item.attendance + '%</td>' +
                        '</tr>';
                });
            }
        }"""

    new_load_anomaly = """        function loadAnomalyData() {
            const selectedDate = REAL_DATA.dataDate;
            const selectedWeek = REAL_DATA.defaultStlWeek;
            const datesAsc = (REAL_DATA.availableDates || []).slice().reverse();

            const computeAgentStreakByDate = (groupId, agentName, anchorDate) => {
                const hist = REAL_DATA.agentPerformanceByDate && REAL_DATA.agentPerformanceByDate[groupId] && REAL_DATA.agentPerformanceByDate[groupId][agentName]
                    ? REAL_DATA.agentPerformanceByDate[groupId][agentName]
                    : null;
                if (!hist) return 0;
                const endIdx = datesAsc.indexOf(anchorDate);
                if (endIdx < 0) return 0;
                let streak = 0;
                for (let i = endIdx; i >= 0; i--) {
                    const d = datesAsc[i];
                    const row = hist[d];
                    if (!row || row.achievement === null || row.achievement === undefined) break;
                    if (row.achievement < 100) streak += 1;
                    else break;
                }
                return streak;
            };

            const getAgentMetricsByDate = (groupId, agentName, anchorDate, fallback) => {
                const dm = REAL_DATA.agentPerformanceByDate && REAL_DATA.agentPerformanceByDate[groupId] && REAL_DATA.agentPerformanceByDate[groupId][agentName]
                    ? REAL_DATA.agentPerformanceByDate[groupId][agentName][anchorDate]
                    : null;
                return {
                    target: dm && dm.target !== undefined ? dm.target : fallback.target,
                    actual: dm && dm.actual !== undefined ? dm.actual : fallback.actual,
                    achievement: dm && dm.achievement !== undefined ? dm.achievement : fallback.achievement,
                    connectRate: dm && dm.connectRate !== undefined ? dm.connectRate : fallback.connectRate,
                    coverTimes: dm && dm.coverTimes !== undefined ? dm.coverTimes : fallback.coverTimes,
                    callTimes: dm && dm.callTimes !== undefined ? dm.callTimes : fallback.callTimes,
                    artCallTimes: dm && dm.artCallTimes !== undefined ? dm.artCallTimes : fallback.artCallTimes,
                    callBillmin: dm && dm.callBillmin !== undefined ? dm.callBillmin : fallback.callBillmin,
                    singleCallDuration: dm && dm.singleCallDuration !== undefined ? dm.singleCallDuration : fallback.singleCallDuration,
                    ptp: dm && dm.ptp !== undefined ? dm.ptp : fallback.ptp,
                    callLossRate: dm && dm.callLossRate !== undefined ? dm.callLossRate : fallback.callLossRate,
                    attendance: dm && dm.attendance !== undefined ? dm.attendance : fallback.attendance
                };
            };

            const buildRecent3DayRows = (groupId, agentName, anchorDate, fallback) => {
                const endIdx = datesAsc.indexOf(anchorDate);
                if (endIdx < 0) return [];
                const rows = [];
                for (let i = endIdx; i >= 0 && rows.length < 3; i--) {
                    const d = datesAsc[i];
                    const metrics = getAgentMetricsByDate(groupId, agentName, d, fallback);
                    rows.push({
                        date: d,
                        ...metrics
                    });
                }
                return rows;
            };

            const buildRecent2WeekGroupRows = (module, groupName, anchorWeekLabel) => {
                const weeks = (REAL_DATA.availableWeeks || []).slice();
                if (weeks.length === 0) return [];
                const anchorIdx = weeks.indexOf(anchorWeekLabel);
                const endIdx = anchorIdx >= 0 ? anchorIdx : (weeks.length - 1);
                const startIdx = Math.max(0, endIdx - 1);
                const rows = [];
                for (let i = endIdx; i >= startIdx; i--) {
                    const weekLabel = weeks[i];
                    const wm = REAL_DATA.groupPerformanceByWeek && REAL_DATA.groupPerformanceByWeek[module] && REAL_DATA.groupPerformanceByWeek[module][groupName]
                        ? REAL_DATA.groupPerformanceByWeek[module][groupName][weekLabel]
                        : null;
                    if (!wm) continue;
                    rows.push({
                        weekLabel: weekLabel,
                        target: wm.target,
                        actual: wm.actual,
                        achievement: wm.achievement,
                        connectRate: wm.connectRate,
                        coverTimes: wm.coverTimes,
                        callTimes: wm.callTimes,
                        artCallTimes: wm.artCallTimes,
                        callBillmin: wm.callBillmin,
                        singleCallDuration: wm.singleCallDuration,
                        callLossRate: wm.callLossRate
                    });
                }
                return rows;
            };

            const moduleSort = (a, b) => {
                const rank = { 'S0': 0, 'S1': 1, 'S2': 2, 'M1': 3 };
                const abase = String(a || '').split('-')[0];
                const bbase = String(b || '').split('-')[0];
                const ra = Object.prototype.hasOwnProperty.call(rank, abase) ? rank[abase] : 999;
                const rb = Object.prototype.hasOwnProperty.call(rank, bbase) ? rank[bbase] : 999;
                if (ra !== rb) return ra - rb;
                return String(a || '').localeCompare(String(b || ''));
            };

            // Build under-performing groups from selected week map (2+ consecutive unmet weeks)
            const groups = [];
            (REAL_DATA.modules || []).filter(m => !isM2Module(m)).sort(moduleSort).forEach(module => {
                const rows = REAL_DATA.groupPerformance[module] || [];
                rows.forEach(group => {
                    const cwMap = REAL_DATA.groupConsecutiveWeeksByWeek && REAL_DATA.groupConsecutiveWeeksByWeek[module] && REAL_DATA.groupConsecutiveWeeksByWeek[module][group.name]
                        ? REAL_DATA.groupConsecutiveWeeksByWeek[module][group.name]
                        : null;
                    const streak = cwMap && cwMap[selectedWeek] !== undefined ? cwMap[selectedWeek] : (group.consecutiveWeeks || 0);
                    if (streak < 2) return;
                    const wm = REAL_DATA.groupPerformanceByWeek && REAL_DATA.groupPerformanceByWeek[module] && REAL_DATA.groupPerformanceByWeek[module][group.name]
                        ? REAL_DATA.groupPerformanceByWeek[module][group.name][selectedWeek]
                        : null;
                    const weeklyTarget = wm && wm.target !== undefined ? wm.target : group.target;
                    const weeklyActual = wm && wm.actual !== undefined ? wm.actual : group.actual;
                    groups.push({
                        module: module,
                        name: group.name,
                        weeks: streak,
                        weeklyTarget: weeklyTarget || 0,
                        weeklyActual: weeklyActual || 0
                    });
                });
            });
            groups.sort((a, b) => {
                const mr = moduleSort(a.module, b.module);
                if (mr !== 0) return mr;
                return (b.weeks || 0) - (a.weeks || 0);
            });

            const groupTbody = document.getElementById('anomaly-group-table');
            const groupEmpty = document.getElementById('anomaly-group-empty');
            groupTbody.innerHTML = '';
            if (groups.length === 0) {
                groupEmpty.style.display = 'block';
            } else {
                groupEmpty.style.display = 'none';
                let currentModule = '';
                groups.forEach((item, idx) => {
                    if (item.module !== currentModule) {
                        currentModule = item.module;
                        groupTbody.innerHTML += '<tr><td colspan=\"8\" style=\"padding:10px 12px; background:#eef2ff; color:#1e3a8a; font-weight:700;\">' + currentModule + '</td></tr>';
                    }
                    const wTgt = item.weeklyTarget || 0;
                    const wAct = item.weeklyActual || 0;
                    const wAch = wTgt > 0 ? (wAct / wTgt * 100) : 0;
                    const achColor = wAch >= 100 ? '#22c55e' : wAch >= 90 ? '#d97706' : '#ef4444';
                    const wGap = Math.max(0, wTgt - wAct);
                    const rowClass = (item.weeks || 0) >= 3 ? 'drilldown-row red-row' : 'drilldown-row yellow-row';
                    const detailId = 'anomaly-group-detail-' + idx;
                    groupTbody.innerHTML += '<tr class=\"' + rowClass + '\">' +
                        '<td style=\"padding: 12px; font-weight: 500;\">' + item.name + '</td>' +
                        '<td style=\"padding: 12px; text-align: center;\">' + item.module + '</td>' +
                        '<td style=\"padding: 12px; text-align: center; font-weight: 700;\">' + item.weeks + '</td>' +
                        '<td style=\"padding: 12px; text-align: right;\">' + formatNumber(wTgt) + '</td>' +
                        '<td style=\"padding: 12px; text-align: right;\">' + formatNumber(wAct) + '</td>' +
                        '<td style=\"padding: 12px; text-align: right; color: #ef4444; font-weight: 600;\">-' + formatNumber(wGap) + '</td>' +
                        '<td style=\"padding: 12px; text-align: right; color: ' + achColor + '; font-weight: 600;\">' + wAch.toFixed(1) + '%</td>' +
                        '<td style=\"padding: 12px; text-align: center;\"><button onclick=\"toggleAnomalyGroupDetail('' + detailId + '')\" style=\"border:1px solid #cbd5e1;background:#fff;color:#334155;padding:4px 8px;border-radius:6px;cursor:pointer;font-size:12px;\">Recent 2 Weeks</button></td>' +
                        '</tr>';

                    const recentWeeks = buildRecent2WeekGroupRows(item.module, item.name, selectedWeek);
                    let detailHtml = '<tr id=\"' + detailId + '\" style=\"display:none;background:#f8fafc;\">';
                    detailHtml += '<td colspan=\"8\" style=\"padding:10px 12px;\">';
                    detailHtml += '<div style=\"font-size:12px;color:#64748b;margin-bottom:8px;\">Drilldown (recent 2 weeks)</div>';
                    detailHtml += '<div style=\"overflow-x:auto;\"><table style=\"width:100%; border-collapse:collapse; font-size:12px;\">';
                    detailHtml += '<tr style=\"background:#eef2ff;border-bottom:1px solid #c7d2fe;\">'
                        + '<th style=\"padding:6px 8px; text-align:left;\">Week</th>'
                        + '<th style=\"padding:6px 8px; text-align:right;\">Weekly Target</th>'
                        + '<th style=\"padding:6px 8px; text-align:right;\">Weekly Actual</th>'
                        + '<th style=\"padding:6px 8px; text-align:right;\">Weekly Achievement</th>'
                        + '<th style=\"padding:6px 8px; text-align:right;\">Conn. Rate</th>'
                        + '<th style=\"padding:6px 8px; text-align:right;\">Cover Times</th>'
                        + '<th style=\"padding:6px 8px; text-align:right;\">Call Times</th>'
                        + '<th style=\"padding:6px 8px; text-align:right;\">Art Call Times</th>'
                        + '<th style=\"padding:6px 8px; text-align:right;\">Call Billmin</th>'
                        + '<th style=\"padding:6px 8px; text-align:right;\">Single Call Duration</th>'
                        + '<th style=\"padding:6px 8px; text-align:right;\">Call Loss</th>'
                        + '</tr>';
                    recentWeeks.forEach(r => {
                        const ach = (r.achievement !== null && r.achievement !== undefined) ? r.achievement.toFixed(1) + '%' : '--';
                        detailHtml += '<tr style=\"border-bottom:1px solid #e2e8f0;\">'
                            + '<td style=\"padding:6px 8px;\">' + r.weekLabel + '</td>'
                            + '<td style=\"padding:6px 8px; text-align:right;\">' + (r.target !== null && r.target !== undefined ? formatNumber(r.target) : '--') + '</td>'
                            + '<td style=\"padding:6px 8px; text-align:right;\">' + (r.actual !== null && r.actual !== undefined ? formatNumber(r.actual) : '--') + '</td>'
                            + '<td style=\"padding:6px 8px; text-align:right;\">' + ach + '</td>'
                            + '<td style=\"padding:6px 8px; text-align:right;\">' + (r.connectRate !== null && r.connectRate !== undefined ? r.connectRate.toFixed(1) + '%' : '--') + '</td>'
                            + '<td style=\"padding:6px 8px; text-align:right;\">' + (r.coverTimes !== null && r.coverTimes !== undefined ? formatNumber(r.coverTimes) : '--') + '</td>'
                            + '<td style=\"padding:6px 8px; text-align:right;\">' + (r.callTimes !== null && r.callTimes !== undefined ? formatNumber(r.callTimes) : '--') + '</td>'
                            + '<td style=\"padding:6px 8px; text-align:right;\">' + (r.artCallTimes !== null && r.artCallTimes !== undefined ? formatNumber(r.artCallTimes) : '--') + '</td>'
                            + '<td style=\"padding:6px 8px; text-align:right;\">' + (r.callBillmin !== null && r.callBillmin !== undefined ? r.callBillmin.toFixed(2) : '--') + '</td>'
                            + '<td style=\"padding:6px 8px; text-align:right;\">' + (r.singleCallDuration !== null && r.singleCallDuration !== undefined ? r.singleCallDuration.toFixed(2) : '--') + '</td>'
                            + '<td style=\"padding:6px 8px; text-align:right;\">' + (r.callLossRate !== null && r.callLossRate !== undefined ? r.callLossRate.toFixed(1) + '%' : '--') + '</td>'
                            + '</tr>';
                    });
                    detailHtml += '</table></div></td></tr>';
                    groupTbody.innerHTML += detailHtml;
                });
            }

            // Build under-performing individuals from selected date history (3+ consecutive unmet days)
            const agents = [];
            (REAL_DATA.groups || []).forEach(groupId => {
                const module = REAL_DATA.tlData[groupId] ? REAL_DATA.tlData[groupId].groupModule : '';
                if (isM2Module(module)) return;
                const rows = REAL_DATA.agentPerformance[groupId] || [];
                rows.forEach(agent => {
                    const streak = computeAgentStreakByDate(groupId, agent.name, selectedDate);
                    if (streak < 3) return;
                    const m = getAgentMetricsByDate(groupId, agent.name, selectedDate, agent);
                    agents.push({
                        module: module,
                        group: groupId,
                        name: agent.name,
                        days: streak,
                        ...m
                    });
                });
            });
            agents.sort((a, b) => {
                const mr = moduleSort(a.module, b.module);
                if (mr !== 0) return mr;
                return (b.days || 0) - (a.days || 0);
            });

            const agentTbody = document.getElementById('anomaly-agent-table');
            const agentEmpty = document.getElementById('anomaly-agent-empty');
            agentTbody.innerHTML = '';
            if (agents.length === 0) {
                agentEmpty.style.display = 'block';
            } else {
                agentEmpty.style.display = 'none';
                let currentModule = '';
                agents.forEach((item, idx) => {
                    if (item.module !== currentModule) {
                        currentModule = item.module;
                        agentTbody.innerHTML += '<tr><td colspan=\"12\" style=\"padding:10px 12px; background:#eef2ff; color:#1e3a8a; font-weight:700;\">' + currentModule + '</td></tr>';
                    }
                    const dailyGap = Math.max(0, (item.target || 0) - (item.actual || 0));
                    const callLoss = (item.callLossRate !== null && item.callLossRate !== undefined) ? item.callLossRate.toFixed(1) + '%' : '--';
                    const rowId = 'anomaly-agent-row-' + idx;
                    const detailId = 'anomaly-agent-detail-' + idx;
                    agentTbody.innerHTML += '<tr id=\"' + rowId + '\" class=\"drilldown-row red-row\">' +
                        '<td style=\"padding: 12px; font-weight: 500;\">' + item.name + '</td>' +
                        '<td style=\"padding: 12px;\">' + item.group + '</td>' +
                        '<td style=\"padding: 12px; text-align: center;\">' + item.module + '</td>' +
                        '<td style=\"padding: 12px; text-align: center; font-weight: 700; color: #ef4444;\">' + item.days + '</td>' +
                        '<td style=\"padding: 12px; text-align: right;\">' + formatNumber(item.target) + '</td>' +
                        '<td style=\"padding: 12px; text-align: right;\">' + formatNumber(item.actual) + '</td>' +
                        '<td style=\"padding: 12px; text-align: right; color: #ef4444; font-weight: 600;\">-' + formatNumber(dailyGap) + '</td>' +
                        '<td style=\"padding: 12px; text-align: right;\">' + (item.artCallTimes !== null && item.artCallTimes !== undefined ? formatNumber(item.artCallTimes) : '--') + '</td>' +
                        '<td style=\"padding: 12px; text-align: right;\">' + (item.connectRate !== null && item.connectRate !== undefined ? item.connectRate.toFixed(1) + '%' : '--') + '</td>' +
                        '<td style=\"padding: 12px; text-align: right;\">' + callLoss + '</td>' +
                        '<td style=\"padding: 12px; text-align: right;\">' + (item.attendance !== null && item.attendance !== undefined ? item.attendance + '%' : '--') + '</td>' +
                        '<td style=\"padding: 12px; text-align: center;\"><button onclick=\"toggleAnomalyAgentDetail('' + detailId + '')\" style=\"border:1px solid #cbd5e1;background:#fff;color:#334155;padding:4px 8px;border-radius:6px;cursor:pointer;font-size:12px;\">Recent 3 Days</button></td>' +
                        '</tr>';

                    const recentRows = buildRecent3DayRows(item.group, item.name, selectedDate, item);
                    let detailHtml = '<tr id=\"' + detailId + '\" style=\"display:none;background:#f8fafc;\">';
                    detailHtml += '<td colspan=\"12\" style=\"padding:10px 12px;\">';
                    detailHtml += '<div style=\"font-size:12px;color:#64748b;margin-bottom:8px;\">Drilldown (recent 3 days)</div>';
                    detailHtml += '<div style=\"overflow-x:auto;\"><table style=\"width:100%; border-collapse:collapse; font-size:12px;\">';
                    detailHtml += '<tr style=\"background:#eef2ff;border-bottom:1px solid #c7d2fe;\">'
                        + '<th style=\"padding:6px 8px; text-align:left;\">Date</th>'
                        + '<th style=\"padding:6px 8px; text-align:right;\">Target</th>'
                        + '<th style=\"padding:6px 8px; text-align:right;\">Actual</th>'
                        + '<th style=\"padding:6px 8px; text-align:right;\">Achievement</th>'
                        + '<th style=\"padding:6px 8px; text-align:right;\">Conn. Rate</th>'
                        + '<th style=\"padding:6px 8px; text-align:right;\">Cover Times</th>'
                        + '<th style=\"padding:6px 8px; text-align:right;\">Call Times</th>'
                        + '<th style=\"padding:6px 8px; text-align:right;\">Art Call Times</th>'
                        + '<th style=\"padding:6px 8px; text-align:right;\">Call Billmin</th>'
                        + '<th style=\"padding:6px 8px; text-align:right;\">Single Call Duration</th>'
                        + '<th style=\"padding:6px 8px; text-align:right;\">PTP</th>'
                        + '<th style=\"padding:6px 8px; text-align:right;\">Call Loss</th>'
                        + '<th style=\"padding:6px 8px; text-align:right;\">Attendance</th>'
                        + '</tr>';
                    recentRows.forEach(r => {
                        const ach = (r.achievement !== null && r.achievement !== undefined) ? r.achievement.toFixed(1) + '%' : '--';
                        detailHtml += '<tr style=\"border-bottom:1px solid #e2e8f0;\">'
                            + '<td style=\"padding:6px 8px;\">' + r.date + '</td>'
                            + '<td style=\"padding:6px 8px; text-align:right;\">' + (r.target !== null && r.target !== undefined ? formatNumber(r.target) : '--') + '</td>'
                            + '<td style=\"padding:6px 8px; text-align:right;\">' + (r.actual !== null && r.actual !== undefined ? formatNumber(r.actual) : '--') + '</td>'
                            + '<td style=\"padding:6px 8px; text-align:right;\">' + ach + '</td>'
                            + '<td style=\"padding:6px 8px; text-align:right;\">' + (r.connectRate !== null && r.connectRate !== undefined ? r.connectRate.toFixed(1) + '%' : '--') + '</td>'
                            + '<td style=\"padding:6px 8px; text-align:right;\">' + (r.coverTimes !== null && r.coverTimes !== undefined ? formatNumber(r.coverTimes) : '--') + '</td>'
                            + '<td style=\"padding:6px 8px; text-align:right;\">' + (r.callTimes !== null && r.callTimes !== undefined ? formatNumber(r.callTimes) : '--') + '</td>'
                            + '<td style=\"padding:6px 8px; text-align:right;\">' + (r.artCallTimes !== null && r.artCallTimes !== undefined ? formatNumber(r.artCallTimes) : '--') + '</td>'
                            + '<td style=\"padding:6px 8px; text-align:right;\">' + (r.callBillmin !== null && r.callBillmin !== undefined ? r.callBillmin.toFixed(2) : '--') + '</td>'
                            + '<td style=\"padding:6px 8px; text-align:right;\">' + (r.singleCallDuration !== null && r.singleCallDuration !== undefined ? r.singleCallDuration.toFixed(2) : '--') + '</td>'
                            + '<td style=\"padding:6px 8px; text-align:right;\">' + (r.ptp !== null && r.ptp !== undefined ? r.ptp.toFixed(1) + '%' : '--') + '</td>'
                            + '<td style=\"padding:6px 8px; text-align:right;\">' + (r.callLossRate !== null && r.callLossRate !== undefined ? r.callLossRate.toFixed(1) + '%' : '--') + '</td>'
                            + '<td style=\"padding:6px 8px; text-align:right;\">' + (r.attendance !== null && r.attendance !== undefined ? r.attendance + '%' : '--') + '</td>'
                            + '</tr>';
                    });
                    detailHtml += '</table></div></td></tr>';
                    agentTbody.innerHTML += detailHtml;
                });
            }
        }

        function toggleAnomalyAgentDetail(rowId) {
            const row = document.getElementById(rowId);
            if (!row) return;
            row.style.display = row.style.display === 'none' ? 'table-row' : 'none';
        }

        function toggleAnomalyGroupDetail(rowId) {
            const row = document.getElementById(rowId);
            if (!row) return;
            row.style.display = row.style.display === 'none' ? 'table-row' : 'none';
        }"""

    html = html.replace(old_load_anomaly, new_load_anomaly)

    # Add Agent Overview subtab container (before existing trend subtab)
    html = html.replace(
        "            <!-- Recovery Trend Sub-tab -->",
        """            <!-- Agent Overview Sub-tab -->
            <div id="data-agent-overview" class="data-subtab-content" style="display: none;">
                <div class="card" style="margin-bottom: 20px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom: 8px;">
                        <h2 style="font-size: 18px; font-weight: 700; color: #1e293b; margin: 0;">Agent Overview</h2>
                        <div style="display:flex; align-items:center; gap:8px;">
                            <label style="font-size: 13px; color: #64748b;">Date:</label>
                            <select id="data-agent-date" onchange="loadAgentOverviewData()" style="padding:6px 10px; border:1px solid #cbd5e1; border-radius:6px; font-size:13px;"></select>
                        </div>
                    </div>
                    <p style="color: #64748b; font-size: 13px; margin-bottom: 0;">Per module, agents are sorted by daily actual repay amount (high to low).</p>
                </div>
                <div id="agent-overview-content"></div>
            </div>

            <!-- Recovery Trend Sub-tab -->""",
    )

    # Data subtab switching: include agent-overview branch
    html = html.replace(
        """        function switchDataSubTab(subtab) {
            document.querySelectorAll('.subtab-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById('subtab-' + subtab).classList.add('active');
            document.querySelectorAll('.data-subtab-content').forEach(c => c.style.display = 'none');
            document.getElementById('data-' + subtab).style.display = 'block';
            if (subtab === 'trend') loadTrendData();
        }""",
        """        function switchDataSubTab(subtab) {
            document.querySelectorAll('.subtab-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById('subtab-' + subtab).classList.add('active');
            document.querySelectorAll('.data-subtab-content').forEach(c => c.style.display = 'none');
            document.getElementById('data-' + subtab).style.display = 'block';
            if (subtab === 'trend') loadTrendData();
            else if (subtab === 'agent-overview') loadAgentOverviewData();
        }""",
    )

    # Agent Overview renderer/functions (insert before loadTrendData)
    html = html.replace(
        "        function loadTrendData() {",
        """        function initAgentOverviewDateSelector() {
            const sel = document.getElementById('data-agent-date');
            if (!sel) return;
            const dates = REAL_DATA.availableDates || [];
            sel.innerHTML = '';
            dates.forEach(d => {
                sel.innerHTML += '<option value=\"' + d + '\">' + d + '</option>';
            });
            if (dates.length > 0) {
                const defDate = (REAL_DATA.dataDate && dates.includes(REAL_DATA.dataDate)) ? REAL_DATA.dataDate : dates[0];
                sel.value = defDate;
            }
        }

        function computeAgentConsecutiveDaysByDate(groupId, agentId, selectedDate) {
            const hist = REAL_DATA.agentPerformanceByDate && REAL_DATA.agentPerformanceByDate[groupId] && REAL_DATA.agentPerformanceByDate[groupId][agentId]
                ? REAL_DATA.agentPerformanceByDate[groupId][agentId]
                : null;
            if (!hist) return 0;
            const dates = (REAL_DATA.availableDates || []).slice().reverse(); // oldest -> newest
            const endIdx = dates.indexOf(selectedDate);
            if (endIdx < 0) return 0;
            let streak = 0;
            for (let i = endIdx; i >= 0; i--) {
                const d = dates[i];
                const row = hist[d];
                if (!row || row.achievement === null || row.achievement === undefined) break;
                if (row.achievement < 100) streak += 1;
                else break;
            }
            return streak;
        }

        function loadAgentOverviewData() {
            const container = document.getElementById('agent-overview-content');
            const sel = document.getElementById('data-agent-date');
            if (!container || !sel) return;
            const selectedDate = sel.value || REAL_DATA.dataDate;
            container.innerHTML = '';
            window.agentOverviewExpanded = window.agentOverviewExpanded || {};

            const modulePriority = ['S0', 'S1', 'S2', 'M1'];
            const moduleRank = {};
            modulePriority.forEach((m, i) => { moduleRank[m] = i; });

            function parseModuleParts(module) {
                const text = String(module || '').trim();
                const parts = text.split('-');
                const base = (parts[0] || '').trim();
                const rawTier = (parts[1] || '').trim().toLowerCase();
                const tier = (rawTier === 'large' || rawTier.includes('大额'))
                    ? 'large'
                    : ((rawTier === 'small' || rawTier.includes('小额')) ? 'small' : rawTier);
                return { base, tier };
            }

            function sortModules(a, b) {
                const pa = parseModuleParts(a);
                const pb = parseModuleParts(b);
                const ra = Object.prototype.hasOwnProperty.call(moduleRank, pa.base) ? moduleRank[pa.base] : 999;
                const rb = Object.prototype.hasOwnProperty.call(moduleRank, pb.base) ? moduleRank[pb.base] : 999;
                if (ra !== rb) return ra - rb;
                if (pa.base !== pb.base) return pa.base.localeCompare(pb.base);
                const ta = pa.tier === 'large' ? 0 : (pa.tier === 'small' ? 1 : 2);
                const tb = pb.tier === 'large' ? 0 : (pb.tier === 'small' ? 1 : 2);
                if (ta !== tb) return ta - tb;
                return String(a).localeCompare(String(b));
            }

            function renderModuleTable(module) {
                const groupsInModule = (REAL_DATA.groups || []).filter(g => REAL_DATA.tlData[g] && REAL_DATA.tlData[g].groupModule === module);
                let rows = [];
                groupsInModule.forEach(groupId => {
                    const agents = REAL_DATA.agentPerformance[groupId] || [];
                    agents.forEach(agent => {
                        const dm = REAL_DATA.agentPerformanceByDate && REAL_DATA.agentPerformanceByDate[groupId] && REAL_DATA.agentPerformanceByDate[groupId][agent.name]
                            ? REAL_DATA.agentPerformanceByDate[groupId][agent.name][selectedDate]
                            : null;
                        const actual = dm && dm.actual !== undefined ? dm.actual : agent.actual;
                        const target = dm && dm.target !== undefined ? dm.target : agent.target;
                        const achievement = dm && dm.achievement !== undefined ? dm.achievement : agent.achievement;
                        rows.push({
                            name: agent.name,
                            group: groupId,
                            actual: actual || 0,
                            target: target || 0,
                            achievement: achievement || 0,
                            consecutiveDays: computeAgentConsecutiveDaysByDate(groupId, agent.name, selectedDate)
                        });
                    });
                });

                rows.sort((a, b) => (b.actual || 0) - (a.actual || 0));
                rows = rows.map((r, idx) => ({ ...r, rank: idx + 1 }));
                const expanded = !!window.agentOverviewExpanded[module];
                const showTopN = 10;
                const visibleRows = expanded ? rows : rows.slice(0, showTopN);

                let section = '<div class=\"card\">';
                section += '<h3 style=\"font-size:16px; font-weight:600; margin-bottom:10px; color:#1e293b;\">' + module + '</h3>';
                if (rows.length === 0) {
                    section += '<div class=\"empty-state\" style=\"display:block;\"><div class=\"empty-state-title\">No agent data</div><div class=\"empty-state-sub\">No records available for selected date.</div></div>';
                } else {
                    section += '<div style=\"width:100%; overflow-x:auto;\">';
                    section += '<table style=\"width:100%; border-collapse:collapse;\">';
                    section += '<thead><tr style=\"background:#f8fafc; border-bottom:2px solid #e2e8f0;\">'
                        + '<th style=\"padding:12px; text-align:center; font-size:12px; color:#64748b; white-space:nowrap;\">Rank</th>'
                        + '<th style=\"padding:12px; text-align:left; font-size:12px; color:#64748b; white-space:nowrap;\">Agent</th>'
                        + '<th style=\"padding:12px; text-align:left; font-size:12px; color:#64748b; white-space:nowrap;\">Group</th>'
                        + '<th style=\"padding:12px; text-align:right; font-size:12px; color:#64748b; white-space:nowrap;\">Daily Actual</th>'
                        + '<th style=\"padding:12px; text-align:right; font-size:12px; color:#64748b; white-space:nowrap;\">Daily Target</th>'
                        + '<th style=\"padding:12px; text-align:right; font-size:12px; color:#64748b; white-space:nowrap;\">Achievement</th>'
                        + '<th style=\"padding:12px; text-align:center; font-size:12px; color:#64748b; white-space:nowrap;\">Consecutive Days</th>'
                        + '</tr></thead><tbody>';
                    visibleRows.forEach(r => {
                        const achColor = r.achievement >= 100 ? '#16a34a' : '#dc2626';
                        section += '<tr class=\"drilldown-row\">'
                            + '<td style=\"padding:12px; text-align:center; font-weight:600; white-space:nowrap;\">' + r.rank + '</td>'
                            + '<td style=\"padding:12px; font-weight:500; white-space:nowrap;\">' + r.name + '</td>'
                            + '<td style=\"padding:12px; white-space:nowrap;\">' + r.group + '</td>'
                            + '<td style=\"padding:12px; text-align:right; white-space:nowrap;\">' + formatNumber(r.actual) + '</td>'
                            + '<td style=\"padding:12px; text-align:right; white-space:nowrap;\">' + formatNumber(r.target) + '</td>'
                            + '<td style=\"padding:12px; text-align:right; color:' + achColor + '; font-weight:600; white-space:nowrap;\">' + r.achievement.toFixed(1) + '%</td>'
                            + '<td style=\"padding:12px; text-align:center; font-weight:600; white-space:nowrap;\">' + r.consecutiveDays + '</td>'
                            + '</tr>';
                    });
                    section += '</tbody></table>';
                    section += '</div>';
                    if (rows.length > showTopN) {
                        const btnText = expanded ? 'Show Top 10' : ('Show All (' + rows.length + ')');
                        section += '<div style=\"display:flex; justify-content:flex-end; margin-top:10px;\">'
                            + '<button onclick="toggleAgentOverviewModule(\'' + module + '\')" style="border:1px solid #cbd5e1; background:#fff; color:#334155; padding:6px 10px; border-radius:6px; cursor:pointer; font-size:12px;">'
                            + btnText
                            + '</button></div>';
                    }
                }
                section += '</div>';
                return section;
            }

            function toggleAgentOverviewModule(module) {
                window.agentOverviewExpanded[module] = !window.agentOverviewExpanded[module];
                loadAgentOverviewData();
            }
            window.toggleAgentOverviewModule = toggleAgentOverviewModule;

            const orderedModules = getVisibleModules().slice().sort(sortModules);
            const groupedByBase = {};
            orderedModules.forEach(module => {
                const p = parseModuleParts(module);
                if (!groupedByBase[p.base]) groupedByBase[p.base] = [];
                groupedByBase[p.base].push(module);
            });

            const baseOrder = Object.keys(groupedByBase).sort((a, b) => {
                const ra = Object.prototype.hasOwnProperty.call(moduleRank, a) ? moduleRank[a] : 999;
                const rb = Object.prototype.hasOwnProperty.call(moduleRank, b) ? moduleRank[b] : 999;
                if (ra !== rb) return ra - rb;
                return a.localeCompare(b);
            });

            baseOrder.forEach(base => {
                const modules = groupedByBase[base];
                if (base === 'S0') {
                    modules.forEach(module => {
                        container.innerHTML += '<div style=\"margin-bottom:16px;\">' + renderModuleTable(module) + '</div>';
                    });
                    return;
                }
                const largeModule = modules.find(m => parseModuleParts(m).tier === 'large');
                const smallModule = modules.find(m => parseModuleParts(m).tier === 'small');
                const otherModules = modules.filter(m => {
                    const t = parseModuleParts(m).tier;
                    return t !== 'large' && t !== 'small';
                });

                if (largeModule && smallModule) {
                    let rowHtml = '<div style=\"display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:16px; align-items:start;\">';
                    rowHtml += '<div>' + renderModuleTable(largeModule) + '</div>';
                    rowHtml += '<div>' + renderModuleTable(smallModule) + '</div>';
                    rowHtml += '</div>';
                    container.innerHTML += rowHtml;
                    otherModules.forEach(module => {
                        container.innerHTML += '<div style=\"margin-bottom:16px;\">' + renderModuleTable(module) + '</div>';
                    });
                } else {
                    modules.forEach(module => {
                        container.innerHTML += '<div style=\"margin-bottom:16px;\">' + renderModuleTable(module) + '</div>';
                    });
                }
            });
        }

        function loadTrendData() {""",
    )

    # Init Data view: also init Agent Overview date selector
    html = html.replace(
        """        function initDataView() {
            loadAnomalyData();
        }""",
        """        function initDataView() {
            loadAnomalyData();
            initAgentOverviewDateSelector();
        }""",
    )

    # Update group under-performing table headers to weekly schema (keep tbody id)
    old_underperf_group_header = """                            <tr style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;">
                                <th style="padding: 12px; text-align: left; font-size: 12px; color: #64748b;">Group</th>
                                <th style="padding: 12px; text-align: center; font-size: 12px; color: #64748b;">Module</th>
                                <th style="padding: 12px; text-align: center; font-size: 12px; color: #64748b;">Consecutive Days</th>
                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Daily Target</th>
                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Daily Actual</th>
                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Daily Gap</th>
                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">MTD Target</th>
                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">MTD Actual</th>
                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">MTD Achievement</th>
                            </tr>"""
    new_underperf_group_header = """                            <tr style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;">
                                <th style="padding: 12px; text-align: left; font-size: 12px; color: #64748b;">Group</th>
                                <th style="padding: 12px; text-align: center; font-size: 12px; color: #64748b;">Module</th>
                                <th style="padding: 12px; text-align: center; font-size: 12px; color: #64748b;">Consecutive Weeks</th>
                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Weekly Target</th>
                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Weekly Actual</th>
                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Weekly Gap</th>
                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Weekly Achievement</th>
                                <th style="padding: 12px; text-align: center; font-size: 12px; color: #64748b;">Drilldown</th>
                            </tr>"""
    html = html.replace(old_underperf_group_header, new_underperf_group_header)

    # ---- 26. Data date ----
    html = html.replace(
        "document.getElementById('data-date').textContent = new Date(Date.now() - 86400000).toISOString().split('T')[0];",
        "document.getElementById('data-date').textContent = REAL_DATA.dataDate;",
    )

    return html
