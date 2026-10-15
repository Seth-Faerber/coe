let firstSelectedIndex = null;
let lastSelectedIndex = null;
const selectedRows = new Set();
let activePromptData = null;

function initializeDashboard(dashboardData) {
    renderTabs(dashboardData);
    renderOverview(dashboardData.all_prompts);

    dashboardData.prompts.forEach((promptData, i) => {
        renderPromptTimeline(promptData, i);
    });

    if (dashboardData.prompts.length > 0) {
        updateAggregateStats(dashboardData);
    }
}

function updateAggregateStats(dashboardData) {
    const totalRuns = dashboardData.all_prompts.reduce((s, p) => s + p.total_runs, 0);
    const recentRuns = dashboardData.all_prompts.reduce((s, p) => s + p.recent_runs, 0);
    const recentPassed = dashboardData.all_prompts.reduce((s, p) => s + p.recent_passed, 0);
    const rate = recentRuns > 0 ? (recentPassed / recentRuns * 100).toFixed(1) + '%' : '0%';

    const el = document.getElementById('aggregateStats');
    if (el) {
        el.textContent = `${dashboardData.prompts.length} prompts · ${totalRuns} total runs · ${rate} pass rate (last 20)`;
    }
}

function renderTabs(dashboardData) {
    const tabBar = document.getElementById('tabBar');
    tabBar.innerHTML = '';

    const overviewTab = makeTab('Overview', 'tab-overview', true);
    tabBar.appendChild(overviewTab);

    dashboardData.prompts.forEach((promptData, i) => {
        const tab = makeTab(promptData.prompt_name, `tab-prompt-${i}`, false);
        tabBar.appendChild(tab);
    });
}

function makeTab(label, targetId, active) {
    const tab = document.createElement('button');
    tab.className = 'tab' + (active ? ' active' : '');
    tab.textContent = label;
    tab.addEventListener('click', () => switchTab(targetId, tab));
    return tab;
}

function switchTab(targetId, clickedTab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    clickedTab.classList.add('active');

    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    const panel = document.getElementById(targetId);
    if (panel) panel.classList.add('active');

    firstSelectedIndex = null;
    lastSelectedIndex = null;
    selectedRows.clear();
}

function renderOverview(allPrompts) {
    const panel = document.getElementById('tab-overview');
    if (!panel) return;
    panel.innerHTML = '';

    if (allPrompts.length === 0) {
        panel.innerHTML = '<div class="empty-state">No evaluation results yet. Run coe test to get started.</div>';
        return;
    }

    const grid = document.createElement('div');
    grid.className = 'prompt-grid';

    allPrompts.forEach((p, i) => {
        const card = document.createElement('div');
        card.className = 'prompt-card';
        const passNum = parseFloat(p.pass_rate);
        if (passNum >= 80) card.classList.add('good');
        else if (passNum >= 50) card.classList.add('ok');
        else card.classList.add('bad');

        card.innerHTML = `
            <div class="card-name">${escapeHtml(p.prompt_name)}</div>
            <div class="card-rate">${escapeHtml(p.pass_rate)}</div>
            <div class="card-meta">${p.total_runs} runs · ${p.passed} passed · ${p.failed} failed</div>
        `;
        card.addEventListener('click', () => {
            const tab = document.querySelectorAll('.tab')[i + 1];
            if (tab) switchTab(`tab-prompt-${i}`, tab);
        });
        grid.appendChild(card);
    });

    panel.appendChild(grid);
}

function renderPromptTimeline(promptData, index) {
    const panel = document.getElementById(`tab-prompt-${index}`);
    if (!panel) return;
    panel.innerHTML = '';

    const statsEl = document.createElement('div');
    statsEl.className = 'prompt-stats';
    const errorStat = (promptData.errors > 0)
        ? `<div class="stat-item"><span class="stat-label">Errors</span><span class="stat-value error">${promptData.errors}</span></div>`
        : '';
    statsEl.innerHTML = `
        <div class="stat-item"><span class="stat-label">Total Runs</span><span class="stat-value">${promptData.total_runs}</span></div>
        <div class="stat-item"><span class="stat-label">Passed</span><span class="stat-value pass">${promptData.passed}</span></div>
        <div class="stat-item"><span class="stat-label">Failed</span><span class="stat-value fail">${promptData.failed}</span></div>
        ${errorStat}
        <div class="stat-item"><span class="stat-label">Pass Rate (last 20)</span><span class="stat-value">${escapeHtml(promptData.pass_rate)}</span></div>
    `;
    panel.appendChild(statsEl);

    const selectionInfo = document.createElement('div');
    selectionInfo.className = 'selection-info';
    selectionInfo.textContent = 'Shift+click to select a range and view the calculated pass rate.';
    panel.appendChild(selectionInfo);

    const selectionResult = document.createElement('div');
    selectionResult.className = 'selection-result';
    selectionResult.id = `selectionResult-${index}`;
    panel.appendChild(selectionResult);

    const timeline = document.createElement('div');
    timeline.className = 'timeline';

    if (promptData.results.length === 0) {
        timeline.innerHTML = '<div class="empty-state">No results for this prompt yet.</div>';
    } else {
        promptData.results.forEach((result, rowIndex) => {
            const row = createTimelineRow(result, rowIndex, promptData, index);
            timeline.appendChild(row);
            if (rowIndex === promptData.recent_runs - 1 && promptData.total_runs > promptData.recent_runs) {
                const sep = document.createElement('div');
                sep.className = 'recent-separator';
                sep.textContent = 'Runs below are not included in the pass rate';
                timeline.appendChild(sep);
            }
        });
    }

    panel.appendChild(timeline);
}

function createTimelineRow(result, index, promptData, promptIndex) {
    const isError = result.error;
    const passed = result.passed;
    const rowState = isError ? 'error' : (passed ? 'pass' : 'fail');
    const row = document.createElement('div');
    row.className = 'timeline-row ' + rowState;
    row.dataset.index = index;

    if (result.change_marker) {
        row.classList.add('has-change');
    }

    let durationMs = '';
    if (result.duration_seconds != null) {
        const totalSec = Math.round(result.duration_seconds);
        const m = Math.floor(totalSec / 60);
        const s = totalSec % 60;
        durationMs = m > 0 ? `${m}m ${s}s` : `${s}s`;
    }
    const turnsLabel = result.num_turns != null ? `${result.num_turns}t` : '';
    const statusLabel = isError ? 'ERROR' : (passed ? 'PASS' : 'FAIL');

    const header = document.createElement('div');
    header.className = 'row-header';
    header.innerHTML = `
        <span class="row-timestamp">${formatTimestamp(result.timestamp)}</span>
        <span class="row-status ${rowState}">${statusLabel}</span>
        <span class="row-timing">${durationMs}</span>
        ${turnsLabel ? `<span class="row-turns">${turnsLabel}</span>` : ''}
    `;

    const content = document.createElement('div');
    content.appendChild(header);

    if (result.change_marker) {
        const changeIndicator = document.createElement('div');
        changeIndicator.className = 'change-indicator';
        changeIndicator.textContent = `⭐ ${result.change_marker.description}`;
        content.appendChild(changeIndicator);
    }

    const details = document.createElement('div');
    details.className = 'row-details';

    if (result.result_file) {
        const fileSection = document.createElement('div');
        fileSection.className = 'detail-section';
        const fileTitleEl = document.createElement('div');
        fileTitleEl.className = 'detail-title';
        fileTitleEl.textContent = 'Result File';
        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-btn';
        copyBtn.textContent = 'Copy';
        copyBtn.title = 'Copy filename';
        copyBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            navigator.clipboard.writeText(result.result_file);
        });
        fileTitleEl.appendChild(copyBtn);
        const fileContentEl = document.createElement('div');
        fileContentEl.className = 'detail-content';
        fileContentEl.textContent = result.result_file;
        fileSection.appendChild(fileTitleEl);
        fileSection.appendChild(fileContentEl);
        details.appendChild(fileSection);
    }

    if (result.test_input) {
        details.appendChild(makeDetailSection('Test Input',
            typeof result.test_input === 'string'
                ? result.test_input
                : JSON.stringify(result.test_input, null, 2)
        ));
    }

    if (result.output) {
        details.appendChild(makeDetailSection('Model Output', result.output));
    }

    if (result.deterministic_checks && Object.keys(result.deterministic_checks).length > 0) {
        const checksSection = document.createElement('div');
        checksSection.className = 'detail-section';
        checksSection.innerHTML = '<div class="detail-title">Deterministic Checks</div>';

        Object.entries(result.deterministic_checks).forEach(([checkName, checkData]) => {
            const item = document.createElement('div');
            item.className = 'check-item';
            item.innerHTML = `
                <span class="check-status ${checkData.overall_pass ? 'pass' : 'fail'}"></span>
                <span>${escapeHtml(checkName)}</span>
            `;
            checksSection.appendChild(item);

            if (checkData.checks) {
                checkData.checks.forEach(c => {
                    const sub = document.createElement('div');
                    sub.className = 'check-subitem';
                    sub.innerHTML = `<span class="check-status ${c.passed ? 'pass' : 'fail'}"></span><span class="check-value">${escapeHtml(c.value)}</span>`;
                    checksSection.appendChild(sub);
                });
            }
        });

        details.appendChild(checksSection);
    }

    if (result.model_evaluation && result.model_evaluation.enabled) {
        const me = result.model_evaluation;
        const meSection = document.createElement('div');
        meSection.className = 'detail-section';
        if (me.error) {
            meSection.innerHTML = `
                <div class="detail-title">Model Evaluation Error</div>
                <div class="detail-content">${escapeHtml(me.error_detail || 'Unknown error')}</div>
            `;
        } else {
            meSection.innerHTML = `
                <div class="detail-title">Model Evaluation (${escapeHtml(me.model || '')})</div>
                <div class="detail-content">Score: ${me.score}/5 · ${me.pass ? 'PASS' : 'FAIL'}\n\n${escapeHtml(me.reasoning || '')}</div>
            `;
        }
        details.appendChild(meSection);
    }

    if (result.logs && result.logs.length > 0) {
        details.appendChild(makeDetailSection('Activity Log', result.logs.join('\n')));
    }

    content.appendChild(details);
    row.appendChild(content);

    row.addEventListener('click', (e) => {
        if (e.shiftKey) {
            handleShiftClick(index, promptData, promptIndex);
            return;
        }
        if (e.target.closest('.row-header')) {
            row.classList.toggle('expanded');
        }
    });

    return row;
}

function makeDetailSection(title, text) {
    const section = document.createElement('div');
    section.className = 'detail-section';
    const titleEl = document.createElement('div');
    titleEl.className = 'detail-title';
    titleEl.textContent = title;
    const contentEl = document.createElement('div');
    contentEl.className = 'detail-content';
    contentEl.textContent = text;
    section.appendChild(titleEl);
    section.appendChild(contentEl);
    return section;
}

function handleShiftClick(index, promptData, promptIndex) {
    if (firstSelectedIndex === null) {
        firstSelectedIndex = index;
        lastSelectedIndex = index;
    } else {
        lastSelectedIndex = index;
    }
    updateSelection(promptData, promptIndex);
}

function updateSelection(promptData, promptIndex) {
    selectedRows.clear();
    const start = Math.min(firstSelectedIndex, lastSelectedIndex);
    const end = Math.max(firstSelectedIndex, lastSelectedIndex);
    for (let i = start; i <= end; i++) selectedRows.add(i);

    const panel = document.getElementById(`tab-prompt-${promptIndex}`);
    if (!panel) return;
    panel.querySelectorAll('.timeline-row').forEach((row, i) => {
        row.classList.toggle('selected', selectedRows.has(i));
    });

    const passCount = [...selectedRows].filter(i => promptData.results[i]?.passed).length;
    const rate = (passCount / selectedRows.size * 100).toFixed(1);
    const resultEl = document.getElementById(`selectionResult-${promptIndex}`);
    if (resultEl) {
        resultEl.textContent = `Selected: ${selectedRows.size} runs · Passed: ${passCount} · Pass Rate: ${rate}%`;
    }
}

function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true
    });
}

function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
