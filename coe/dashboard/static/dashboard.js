let firstSelectedIndex = null;
let lastSelectedIndex = null;
const selectedRows = new Set();

function initializeTimeline(evalData) {
    updateHeaderStats(evalData);
    renderTimeline(evalData);
}

function updateHeaderStats(evalData) {
    document.getElementById('totalRuns').textContent = evalData.total_runs;
    document.getElementById('passedCount').textContent = evalData.passed;
    document.getElementById('failedCount').textContent = evalData.failed;
    document.getElementById('overallPassRate').textContent = evalData.pass_rate;
}

function renderTimeline(evalData) {
    const timelineEl = document.getElementById('timeline');
    timelineEl.innerHTML = '';

    if (evalData.results.length === 0) {
        timelineEl.innerHTML = '<div class="empty-state">No evaluation results yet.</div>';
        return;
    }

    evalData.results.forEach((result, index) => {
        const rowEl = createTimelineRow(result, index, evalData);
        timelineEl.appendChild(rowEl);
    });
}

function createTimelineRow(result, index, evalData) {
    const row = document.createElement('div');
    row.className = 'timeline-row';
    row.dataset.index = index;
    row.dataset.pass = result.overall_pass ? 'pass' : 'fail';

    if (result.overall_pass) {
        row.classList.add('pass');
    } else {
        row.classList.add('fail');
    }

    if (result.change_marker) {
        row.classList.add('has-change');
    }

    const header = document.createElement('div');
    header.className = 'row-header';

    const timestamp = document.createElement('span');
    timestamp.className = 'row-timestamp';
    timestamp.textContent = formatTimestamp(result.timestamp);

    const status = document.createElement('span');
    status.className = `row-status ${result.overall_pass ? 'pass' : 'fail'}`;
    status.textContent = result.overall_pass ? 'PASS' : 'FAIL';

    const timing = document.createElement('span');
    timing.className = 'row-timing';
    timing.textContent = `${result.timing_ms}ms`;

    header.appendChild(timestamp);
    header.appendChild(status);
    header.appendChild(timing);

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

    const testInputSection = document.createElement('div');
    testInputSection.className = 'detail-section';
    const testInputTitle = document.createElement('div');
    testInputTitle.className = 'detail-title';
    testInputTitle.textContent = 'Test Input';
    const testInputContent = document.createElement('div');
    testInputContent.className = 'detail-content';
    testInputContent.textContent = truncateText(result.test_input, 500);
    testInputSection.appendChild(testInputTitle);
    testInputSection.appendChild(testInputContent);
    details.appendChild(testInputSection);

    const outputSection = document.createElement('div');
    outputSection.className = 'detail-section';
    const outputTitle = document.createElement('div');
    outputTitle.className = 'detail-title';
    outputTitle.textContent = 'Generated Output';
    const outputContent = document.createElement('div');
    outputContent.className = 'detail-content';
    outputContent.textContent = truncateText(result.generated_output, 500);
    outputSection.appendChild(outputTitle);
    outputSection.appendChild(outputContent);
    details.appendChild(outputSection);

    if (result.deterministic_checks && Object.keys(result.deterministic_checks).length > 0) {
        const checksSection = document.createElement('div');
        checksSection.className = 'detail-section';
        const checksTitle = document.createElement('div');
        checksTitle.className = 'detail-title';
        checksTitle.textContent = 'Deterministic Checks';
        checksSection.appendChild(checksTitle);

        Object.entries(result.deterministic_checks).forEach(([checkName, checkData]) => {
            const checkItem = document.createElement('div');
            checkItem.className = 'check-item';

            const statusEl = document.createElement('span');
            statusEl.className = `check-status ${checkData.overall_pass ? 'pass' : 'fail'}`;

            const checkNameEl = document.createElement('span');
            checkNameEl.textContent = checkName;

            checkItem.appendChild(statusEl);
            checkItem.appendChild(checkNameEl);
            checksSection.appendChild(checkItem);
        });

        details.appendChild(checksSection);
    }

    if (result.model_evaluation && result.model_evaluation.enabled) {
        const modelSection = document.createElement('div');
        modelSection.className = 'detail-section';
        const modelTitle = document.createElement('div');
        modelTitle.className = 'detail-title';
        modelTitle.textContent = `Model Evaluation (${result.model_evaluation.model})`;
        modelSection.appendChild(modelTitle);

        const scoreText = document.createElement('div');
        scoreText.className = 'detail-content';
        scoreText.textContent = `Score: ${result.model_evaluation.score}/5\n\n${result.model_evaluation.reasoning}`;
        modelSection.appendChild(scoreText);

        details.appendChild(modelSection);
    }

    content.appendChild(details);
    row.appendChild(content);

    row.addEventListener('click', (e) => {
        if (e.shiftKey) {
            handleShiftClick(index, evalData);
        } else {
            toggleRowExpanded(row);
        }
    });

    return row;
}

function handleShiftClick(index, evalData) {
    if (firstSelectedIndex === null) {
        firstSelectedIndex = index;
        lastSelectedIndex = index;
        updateSelection(evalData);
    } else {
        lastSelectedIndex = index;
        updateSelection(evalData);
    }
}

function updateSelection(evalData) {
    selectedRows.clear();

    const start = Math.min(firstSelectedIndex, lastSelectedIndex);
    const end = Math.max(firstSelectedIndex, lastSelectedIndex);

    for (let i = start; i <= end; i++) {
        selectedRows.add(i);
    }

    document.querySelectorAll('.timeline-row').forEach((row, index) => {
        if (selectedRows.has(index)) {
            row.classList.add('selected');
        } else {
            row.classList.remove('selected');
        }
    });

    calculateAndDisplayPassRate(evalData);
}

function calculateAndDisplayPassRate(evalData) {
    if (selectedRows.size === 0) {
        document.getElementById('selectionResult').textContent = '';
        return;
    }

    let passCount = 0;
    selectedRows.forEach(index => {
        if (evalData.results[index].overall_pass) {
            passCount++;
        }
    });

    const passRate = (passCount / selectedRows.size * 100).toFixed(1);
    const resultText = `Selected: ${selectedRows.size} runs | Passed: ${passCount} | Pass Rate: ${passRate}%`;

    document.getElementById('selectionResult').textContent = resultText;
}

function toggleRowExpanded(row) {
    row.classList.toggle('expanded');
}

function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
    });
}

function truncateText(text, maxLength) {
    if (text.length > maxLength) {
        return text.substring(0, maxLength) + `\n... (${text.length - maxLength} more characters)`;
    }
    return text;
}
