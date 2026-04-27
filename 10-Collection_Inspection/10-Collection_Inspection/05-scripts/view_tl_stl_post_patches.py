"""TL/STL 大块补丁：在 apply_data_view_patches 之后应用（自 generate_v2_7 迁出）。"""

import sys


_patch_seq = 0

def _r1(html, old, new):
    """Replace once, warn if 0 or >1 occurrences."""
    global _patch_seq
    import traceback
    frame = traceback.extract_stack()[-2]
    patch_id = f"post_{frame.lineno}_{_patch_seq}"
    _patch_seq += 1
    n = html.count(old)
    if n == 0:
        print(f"  [WARN][{patch_id}] 锚点未找到: ...{old[:60].replace(chr(10), '\\n')!r}...", file=sys.stderr)
        return html
    if n > 1:
        print(f"  [WARN][{patch_id}] 锚点出现 {n} 次(期望1): ...{old[:60].replace(chr(10), '\\n')!r}...", file=sys.stderr)
    return html.replace(old, new, 1)


def apply_tl_stl_post_data_view_patches(html: str) -> str:
    """TL Recovery Trend 全月轴、tooltip、STL 等（原 generate 5b-17 段顺序不变）。"""
    # ---- 5b. TL Recovery Trend: X-axis full month; target continues; actual null for future ----
    old_tl_month_block = """\
                // Filter to only show selected date's month
                const selectedMonth = selectedDate ? selectedDate.slice(0, 7) : ''; // YYYY-MM

                const dates = [];
                const series = [];
                const legendData = ['Module Target'];

                // Get date labels and module target from first group's data, filtered by month
                let monthData = [];
                let moduleTargetValues = [];
                if (REAL_DATA.tlData[allGroupsInModule[0]] && REAL_DATA.tlData[allGroupsInModule[0]].days) {
                    monthData = REAL_DATA.tlData[allGroupsInModule[0]].days.filter(d => d.date.startsWith(selectedMonth));
                    monthData.forEach(d => dates.push(d.date.slice(5))); // MM-DD format
                    // Get module target from first day of filtered data
                    if (monthData.length > 0) {
                        moduleTargetValues = monthData.map(d => d.targetRepayRate !== null && d.targetRepayRate !== undefined ? d.targetRepayRate : null);
                    }
                }
    """
    new_tl_month_block = """\
                // Selected month (YYYY-MM). X-axis shows full month; actual may be null for future days.
                const selectedMonth = selectedDate ? selectedDate.slice(0, 7) : REAL_DATA.dataDate.slice(0, 7); // YYYY-MM
                const cutoffDate = (selectedDate && selectedDate < REAL_DATA.dataDate) ? selectedDate : REAL_DATA.dataDate;

                const dates = [];
                const series = [];
                const legendData = ['Module Target'];

                // Build full month labels: MM-DD
                const ymParts = selectedMonth.split('-');
                const year = parseInt(ymParts[0], 10);
                const month = parseInt(ymParts[1], 10); // 1-12
                const daysInMonth = new Date(year, month, 0).getDate();
                for (let d = 1; d <= daysInMonth; d++) {
                    const mm = String(month).padStart(2, '0');
                    const dd = String(d).padStart(2, '0');
                    dates.push(mm + '-' + dd);
                }

                // Module target should be available for the full month (even if actual stops at dataDate)
                let moduleTargetValues = [];
                const trendData = (REAL_DATA.moduleDailyTrends && REAL_DATA.moduleDailyTrends[module]) ? REAL_DATA.moduleDailyTrends[module] : null;
                const targetRows = (trendData && trendData.daily) ? trendData.daily.filter(d => d.date.startsWith(selectedMonth)) : [];
                const targetByLabel = {};
                targetRows.forEach(r => {
                    targetByLabel[r.date.slice(5)] = (r.targetRepayRate !== null && r.targetRepayRate !== undefined) ? r.targetRepayRate : null;
                });
                moduleTargetValues = dates.map(lbl => (Object.prototype.hasOwnProperty.call(targetByLabel, lbl) ? targetByLabel[lbl] : null));
    """
    html = _r1(html, old_tl_month_block, new_tl_month_block)

    old_tl_group_days = """\
                    // Filter data by selected month
                    const filteredDays = groupData.days.filter(d => d.date.startsWith(selectedMonth));
                    if (filteredDays.length === 0) return;

                    const isSelected = g === group;
                    const actuals = filteredDays.map(d => d.nmRepayRate !== null && d.nmRepayRate !== undefined ? d.nmRepayRate : (d.repayRate !== null && d.repayRate !== undefined ? d.repayRate : null));
    """
    new_tl_group_days = """\
                    // Filter actuals to selected month up to dataDate cutoff; fill future days with nulls
                    const filteredDays = groupData.days.filter(d => d.date.startsWith(selectedMonth) && d.date <= cutoffDate);
                    if (filteredDays.length === 0) return;

                    const isSelected = g === group;
                    const actualByLabel = {};
                    filteredDays.forEach(d => {
                        const v = (d.nmRepayRate !== null && d.nmRepayRate !== undefined) ? d.nmRepayRate : ((d.repayRate !== null && d.repayRate !== undefined) ? d.repayRate : null);
                        actualByLabel[d.date.slice(5)] = v;
                    });
                    const actuals = dates.map(lbl => (Object.prototype.hasOwnProperty.call(actualByLabel, lbl) ? actualByLabel[lbl] : null));
    """
    html = _r1(html, old_tl_group_days, new_tl_group_days)

    # ---- 6. renderTLChart: moduleTarget -> targetRepayRate ----
    html = _r1(html,
        "            const legendData = ['Module Target'];",
        "            const legendData = ['Module Target'];"
    )
    html = _r1(html,
        "            let moduleTarget = 0;",
        "            let moduleTargetValues = [];"
    )
    html = _r1(html,
        "                    moduleTarget = monthData[0].target;",
        "                    moduleTargetValues = monthData.map(d => d.targetRepayRate !== null && d.targetRepayRate !== undefined ? d.targetRepayRate : null);"
    )
    html = _r1(html,
        "                    moduleTarget = (monthData[0].targetRepayRate !== null && monthData[0].targetRepayRate !== undefined) ? monthData[0].targetRepayRate : 0;",
        "                    moduleTargetValues = monthData.map(d => d.targetRepayRate !== null && d.targetRepayRate !== undefined ? d.targetRepayRate : null);"
    )

    # ---- 7. renderTLChart: target line fill (rate, no rounding) ----
    html = _r1(html,
        "                data: Array(dates.length).fill(Math.round(moduleTarget));",
        "                data: moduleTargetValues,"
    )
    html = _r1(html,
        "                data: Array(dates.length).fill(moduleTarget);",
        "                data: moduleTargetValues,"
    )
    html = _r1(html,
        "                data: Array(dates.length).fill(Math.round(moduleTarget)),",
        "                data: moduleTargetValues,"
    )
    html = _r1(html,
        "            // Add SINGLE module-level target line (dashed green)\n            series.push({\n                name: 'Module Target',",
        "            // Add SINGLE module-level target line (dashed green)\n            series.push({\n                name: 'Module Target',"
    )

    # ---- 8. Shared tooltip: amount -> rate % (TL + STL charts) ----
    old_shared_tooltip = """\
                    tooltip: { trigger: 'axis', formatter: params => {
                        const date = params[0].name;
                        let html = date + '<br>';
                        // Show target first
                        const targetParam = params.find(p => p.seriesName === 'Module Target');
                        if (targetParam) {
                            html += targetParam.marker + ' Module Target: ' + formatNumber(targetParam.value) + '<br>';
                        }
                        // Then show groups
                        params.forEach(p => {
                            if (p.seriesName === 'Module Target') return;
                            html += p.marker + ' ' + p.seriesName + ': ' + formatNumber(p.value) + '<br>';
                        });
                        return html;
                    }},"""
    new_shared_tooltip = """\
                    tooltip: { trigger: 'axis', formatter: params => {
                        const date = params[0].name;
                        let html = date + '<br>';
                        const sortedParams = params.slice().sort((a, b) => {
                            const av = (a.value !== null && a.value !== undefined) ? a.value : -999999;
                            const bv = (b.value !== null && b.value !== undefined) ? b.value : -999999;
                            return bv - av; // desc
                        });
                        sortedParams.forEach(p => {
                            html += p.marker + ' ' + p.seriesName + ': ' + (p.value !== null && p.value !== undefined ? p.value.toFixed(2) + '%' : '-') + '<br>';
                        });
                        return html;
                    }},"""
    html = _r1(html, old_shared_tooltip, new_shared_tooltip)

    # ---- 9. TL+STL Y-axis -> % ----
    html = _r1(html,
        "                yAxis: { type: 'value', axisLabel: { formatter: v => formatNumber(v) } },",
        "                yAxis: { type: 'value', axisLabel: { formatter: v => v !== null && v !== undefined ? v.toFixed(2) + '%' : '' } },"
    )

    # ---- 10. renderSTLChart: target values -> targetRepayRate ----
    html = _r1(html,
        "            const targetValues = dailyData.map(d => d.target);",
        "            const targetValues = dailyData.map(d => d.targetRepayRate !== null && d.targetRepayRate !== undefined ? d.targetRepayRate : null);"
    )
    html = _r1(html,
        "            const monthStr = weekLabel.split('/')[0]; // Get month from \"MM/DD - MM/DD\"",
        "            const weekParts = weekLabel.split(' - ');\n            const endPart = weekParts.length > 1 ? weekParts[1] : weekParts[0];\n            const monthStr = endPart.split('/')[0]; // Use week-end month for cross-month week labels"
    )
    html = _r1(html,
        "            // Generate daily data for the selected month (like TL does for daily trend)\n            // Generate dates for the month of selected week\n            const today = new Date();\n            const currentYear = today.getFullYear();\n            const month = parseInt(monthStr) - 1; // 0-indexed\n            const daysInMonth = new Date(currentYear, month + 1, 0).getDate();\n\n            const dates = [];",
        "            // Use selected month data up to dataDate cutoff\n            const cutoffDate = REAL_DATA.dataDate;\n            const dates = [];"
    )

    # ---- 10b. STL Recovery Trend: X-axis full month; target continues; actual null for future ----
    old_stl_dates_block = """\
                // Use selected month data up to dataDate cutoff
                const cutoffDate = REAL_DATA.dataDate;
                const dates = [];

                // Get module from selector
                const module = document.getElementById('stl-module-select').value;

                // Get daily data from moduleDailyTrends (contains natural month repay target)
                const trendData = REAL_DATA.moduleDailyTrends[module];
                const selectedYearMonth = REAL_DATA.dataDate.slice(0, 4) + '-' + monthStr.padStart(2, '0');
                const dailyData = trendData ? trendData.daily.filter(d => d.date.startsWith(selectedYearMonth) && d.date <= cutoffDate) : [];
                dailyData.forEach(d => dates.push(d.date.slice(5)));
    """
    new_stl_dates_block = """\
                // X-axis shows full month; actual may be null for future days.
                const cutoffDate = REAL_DATA.dataDate;
                const dates = [];

                // Get module from selector
                const module = document.getElementById('stl-module-select').value;

                // Build full month labels: MM-DD for selected month
                const selectedYearMonth = REAL_DATA.dataDate.slice(0, 4) + '-' + monthStr.padStart(2, '0');
                const ymParts = selectedYearMonth.split('-');
                const year = parseInt(ymParts[0], 10);
                const month = parseInt(ymParts[1], 10); // 1-12
                const daysInMonth = new Date(year, month, 0).getDate();
                for (let d = 1; d <= daysInMonth; d++) {
                    const mm = String(month).padStart(2, '0');
                    const dd = String(d).padStart(2, '0');
                    dates.push(mm + '-' + dd);
                }

                // Get daily data from moduleDailyTrends (contains natural month repay target)
                const trendData = REAL_DATA.moduleDailyTrends[module];
                const dailyAll = trendData ? trendData.daily.filter(d => d.date.startsWith(selectedYearMonth)) : [];
                const dailyActual = dailyAll.filter(d => d.date <= cutoffDate);

                const targetByLabel = {};
                dailyAll.forEach(r => {
                    targetByLabel[r.date.slice(5)] = (r.targetRepayRate !== null && r.targetRepayRate !== undefined) ? r.targetRepayRate : null;
                });

                const moduleActualByLabel = {};
                dailyActual.forEach(r => {
                    moduleActualByLabel[r.date.slice(5)] = (r.repayRate !== null && r.repayRate !== undefined) ? r.repayRate : null;
                });
    """
    html = _r1(html, old_stl_dates_block, new_stl_dates_block)

    # Target line: from full-month targetByLabel (not truncated by dataDate)
    html = _r1(html,
        "            const targetValues = dailyData.map(d => d.targetRepayRate !== null && d.targetRepayRate !== undefined ? d.targetRepayRate : null);",
        "            const targetValues = dates.map(lbl => (Object.prototype.hasOwnProperty.call(targetByLabel, lbl) ? targetByLabel[lbl] : null));"
    )

    # Module total: actual only up to dataDate, rest null
    html = _r1(html,
        "            const moduleActuals = dailyData.map(d => d.repayRate !== null && d.repayRate !== undefined ? d.repayRate : null);",
        "            const moduleActuals = dates.map(lbl => (Object.prototype.hasOwnProperty.call(moduleActualByLabel, lbl) ? moduleActualByLabel[lbl] : null));"
    )

    # Per-group series: align to full-month dates
    old_stl_group_series = """\
                    const repayRates = gData.days
                        .filter(d => d.date.startsWith(selectedYearMonth) && d.date <= cutoffDate)
                        .map(d => d.nmRepayRate !== null && d.nmRepayRate !== undefined ? d.nmRepayRate : (d.repayRate !== null && d.repayRate !== undefined ? d.repayRate : null));
    """
    new_stl_group_series = """\
                    const filteredDays = gData.days
                        .filter(d => d.date.startsWith(selectedYearMonth) && d.date <= cutoffDate);
                    const repayByLabel = {};
                    filteredDays.forEach(d => {
                        const v = (d.nmRepayRate !== null && d.nmRepayRate !== undefined) ? d.nmRepayRate : ((d.repayRate !== null && d.repayRate !== undefined) ? d.repayRate : null);
                        repayByLabel[d.date.slice(5)] = v;
                    });
                    const repayRates = dates.map(lbl => (Object.prototype.hasOwnProperty.call(repayByLabel, lbl) ? repayByLabel[lbl] : null));
    """
    html = _r1(html, old_stl_group_series, new_stl_group_series)

    # ---- 10c. TL+STL recovery trend finalization (robust patching) ----
    # TL: ensure full-month x-axis + cutoffDate defined + target continues beyond actuals
    html = _r1(html,
        "            const selectedMonth = selectedDate ? selectedDate.slice(0, 7) : ''; // YYYY-MM",
        "            const selectedMonth = selectedDate ? selectedDate.slice(0, 7) : REAL_DATA.dataDate.slice(0, 7); // YYYY-MM\n            const cutoffDate = (selectedDate && selectedDate < REAL_DATA.dataDate) ? selectedDate : REAL_DATA.dataDate;"
    )
    html = _r1(html,
        "                monthData.forEach(d => dates.push(d.date.slice(5))); // MM-DD format",
        "                const ymParts = selectedMonth.split('-');\n                const year = parseInt(ymParts[0], 10);\n                const month = parseInt(ymParts[1], 10); // 1-12\n                const daysInMonth = new Date(year, month, 0).getDate();\n                for (let d = 1; d <= daysInMonth; d++) {\n                    const mm = String(month).padStart(2, '0');\n                    const dd = String(d).padStart(2, '0');\n                    dates.push(mm + '-' + dd);\n                }"
    )
    html = _r1(html,
        "                    moduleTargetValues = monthData.map(d => d.targetRepayRate !== null && d.targetRepayRate !== undefined ? d.targetRepayRate : null);",
        "                    const trendData = (REAL_DATA.moduleDailyTrends && REAL_DATA.moduleDailyTrends[module]) ? REAL_DATA.moduleDailyTrends[module] : null;\n                    const targetRows = (trendData && trendData.daily) ? trendData.daily.filter(d => d.date.startsWith(selectedMonth)) : [];\n                    const targetByLabel = {};\n                    targetRows.forEach(r => { targetByLabel[r.date.slice(5)] = (r.targetRepayRate !== null && r.targetRepayRate !== undefined) ? r.targetRepayRate : null; });\n                    moduleTargetValues = dates.map(lbl => (Object.prototype.hasOwnProperty.call(targetByLabel, lbl) ? targetByLabel[lbl] : null));"
    )

    # STL: replace month-date block to full-month dates + build target/actual maps
    old_stl_month_block = """\
                // Use selected month data up to dataDate cutoff
                const cutoffDate = REAL_DATA.dataDate;
                const dates = [];

                // Get module from selector
                const module = document.getElementById('stl-module-select').value;

                // Get daily data from moduleDailyTrends (contains natural month repay target)
                const trendData = REAL_DATA.moduleDailyTrends[module];
                const selectedYearMonth = REAL_DATA.dataDate.slice(0, 4) + '-' + monthStr.padStart(2, '0');
                const dailyData = trendData ? trendData.daily.filter(d => d.date.startsWith(selectedYearMonth) && d.date <= cutoffDate) : [];
                dailyData.forEach(d => dates.push(d.date.slice(5)));
    """
    new_stl_month_block = """\
                // X-axis shows full month; actual may be null for future days.
                const cutoffDate = REAL_DATA.dataDate;
                const dates = [];

                // Get module from selector
                const module = document.getElementById('stl-module-select').value;

                const selectedYearMonth = REAL_DATA.dataDate.slice(0, 4) + '-' + monthStr.padStart(2, '0');
                const ymParts = selectedYearMonth.split('-');
                const year = parseInt(ymParts[0], 10);
                const month = parseInt(ymParts[1], 10); // 1-12
                const daysInMonth = new Date(year, month, 0).getDate();
                for (let d = 1; d <= daysInMonth; d++) {
                    const mm = String(month).padStart(2, '0');
                    const dd = String(d).padStart(2, '0');
                    dates.push(mm + '-' + dd);
                }

                // Get daily data from moduleDailyTrends (contains natural month repay target)
                const trendData = REAL_DATA.moduleDailyTrends[module];
                const dailyAll = trendData ? trendData.daily.filter(d => d.date.startsWith(selectedYearMonth)) : [];
                const dailyData = dailyAll.filter(d => d.date <= cutoffDate);

                const targetByLabel = {};
                dailyAll.forEach(r => { targetByLabel[r.date.slice(5)] = (r.targetRepayRate !== null && r.targetRepayRate !== undefined) ? r.targetRepayRate : null; });

                const moduleActualByLabel = {};
                dailyData.forEach(r => { moduleActualByLabel[r.date.slice(5)] = (r.repayRate !== null && r.repayRate !== undefined) ? r.repayRate : null; });
    """
    html = _r1(html, old_stl_month_block, new_stl_month_block)

    # STL target + module total + per-group aligned to full-month dates
    html = _r1(html,
        "            const targetValues = dailyData.map(d => d.targetRepayRate !== null && d.targetRepayRate !== undefined ? d.targetRepayRate : null);",
        "            const targetValues = dates.map(lbl => (Object.prototype.hasOwnProperty.call(targetByLabel, lbl) ? targetByLabel[lbl] : null));"
    )
    html = _r1(html,
        "            const moduleActuals = dailyData.map(d => d.repayRate !== null && d.repayRate !== undefined ? d.repayRate : null);",
        "            const moduleActuals = dates.map(lbl => (Object.prototype.hasOwnProperty.call(moduleActualByLabel, lbl) ? moduleActualByLabel[lbl] : null));"
    )
    html = _r1(html,
        "                const repayRates = gData.days\n                    .filter(d => d.date.startsWith(selectedYearMonth) && d.date <= cutoffDate)\n                    .map(d => d.nmRepayRate !== null && d.nmRepayRate !== undefined ? d.nmRepayRate : (d.repayRate !== null && d.repayRate !== undefined ? d.repayRate : null));",
        "                const filteredDays = gData.days\n                    .filter(d => d.date.startsWith(selectedYearMonth) && d.date <= cutoffDate);\n                const repayByLabel = {};\n                filteredDays.forEach(d => {\n                    const v = (d.nmRepayRate !== null && d.nmRepayRate !== undefined) ? d.nmRepayRate : ((d.repayRate !== null && d.repayRate !== undefined) ? d.repayRate : null);\n                    repayByLabel[d.date.slice(5)] = v;\n                });\n                const repayRates = dates.map(lbl => (Object.prototype.hasOwnProperty.call(repayByLabel, lbl) ? repayByLabel[lbl] : null));"
    )
    # NOTE: STL recovery trend month-axis is handled by the full-month patch above (10c).

    # ---- 11. renderSTLChart: per-group data -> real repayRate from tlData ----
    old_stl_simulated = """\
                // Add each group's daily trend for the month (line chart, like TL)
                groupsInModule.forEach((g, idx) => {
                    // Generate simulated daily data for this group
                    const groupDailyData = dailyData.map(d => ({
                        date: d.date,
                        actual: Math.floor(d.actual * (0.3 + Math.random() * 0.4)) // Distribute module total to groups
                    }));

                    const color = idx % 2 === 0 ? '#1e3a5f' : '#3b82f6';
                    const actuals = groupDailyData.map(d => Math.round(d.actual));

                    series.push({
                        name: g,
                        type: 'line',
                        data: actuals,
                        smooth: true,
                        lineStyle: { color: color, width: 1.5, opacity: 0.6 },
                        itemStyle: { color: color },
                        symbol: 'none',
                        z: idx + 1
                    });
                    legendData.unshift(g);
                });"""
    new_stl_real = """\
                // Add each group's daily repay rate from natural_month_repay
                groupsInModule.forEach((g, idx) => {
                    const gData = REAL_DATA.tlData[g];
                    if (!gData || !gData.days) return;
                    const color = idx % 2 === 0 ? '#1e3a5f' : '#3b82f6';
                    const repayRates = gData.days
                        .filter(d => d.date.startsWith(selectedYearMonth) && d.date <= cutoffDate)
                        .map(d => d.nmRepayRate !== null && d.nmRepayRate !== undefined ? d.nmRepayRate : (d.repayRate !== null && d.repayRate !== undefined ? d.repayRate : null));

                    series.push({
                        name: g,
                        type: 'line',
                        data: repayRates,
                        smooth: true,
                        lineStyle: { color: color, width: 1.5, opacity: 0.6 },
                        itemStyle: { color: color },
                        symbol: 'none',
                        z: idx + 1
                    });
                    legendData.unshift(g);
                });"""
    html = _r1(html, old_stl_simulated, new_stl_real)

    # ---- 12. renderSTLChart: module total -> repayRate ----
    html = _r1(html,
        "            const moduleActuals = dailyData.map(d => Math.round(d.actual));",
        "            const moduleActuals = dailyData.map(d => d.repayRate !== null && d.repayRate !== undefined ? d.repayRate : null);"
    )

    # ---- 17. TL Date selector -> REAL_DATA.availableDates ----
    old_date_sel = """\
                // Populate date selector: last 30 days
                const dateSel = document.getElementById('tl-date-select');
                dateSel.innerHTML = '';
                const defaultDate = getDefaultDate();
                for (let i = 1; i <= 30; i++) {
                    const d = new Date();
                    d.setDate(d.getDate() - i);
                    const val = d.toISOString().split('T')[0];
                    const selected = val === defaultDate ? ' selected' : '';
                    dateSel.innerHTML += '<option value="' + val + '"' + selected + '>' + val + '</option>';
                }"""
    new_date_sel = """\
                // Populate TL date selector from real agent_repay dates
                const dateSel = document.getElementById('tl-date-select');
                dateSel.innerHTML = '';
                REAL_DATA.availableDates.forEach((dateStr, i) => {
                    const selected = i === 0 ? ' selected' : '';
                    dateSel.innerHTML += '<option value="' + dateStr + '"' + selected + '>' + dateStr + '</option>';
                });"""
    html = _r1(html, old_date_sel, new_date_sel)
    return html
