// DOM references
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const fileName = document.getElementById('fileName');
const fileError = document.getElementById('fileError');
const analyzeBtn = document.getElementById('analyzeBtn');
const pageSelection = document.getElementById('pageSelection');
const confidenceSlider = document.getElementById('confidence');
const confidenceValue = document.getElementById('confidenceValue');
const selectAllBtn = document.getElementById('selectAllBtn');
const deselectAllBtn = document.getElementById('deselectAllBtn');
const progressSection = document.getElementById('progressSection');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const resultsSection = document.getElementById('resultsSection');
const resultsSummary = document.getElementById('resultsSummary');
const devicesGrid = document.getElementById('devicesGrid');
const previewSection = document.getElementById('previewSection');
const previewGrid = document.getElementById('previewGrid');
const exportBtn = document.getElementById('exportBtn');
const startGeminiBtn = document.getElementById('startGeminiBtn');
const downloadGeminiReportBtn = document.getElementById('downloadGeminiReportBtn');
const geminiProgress = document.getElementById('geminiProgress');
const geminiProgressText = document.getElementById('geminiProgressText');
const geminiResultsSection = document.getElementById('geminiResultsSection');

let selectedFile = null;
let currentJobId = null;
let geminiConfigured = false;
let currentGeminiJobId = null;

// Initialisation
DocumentReady(() => {
    setupUploadInteractions();
    setupControls();
    resetGeminiUI();
    checkStatus();
    setInterval(checkStatus, 30000);
});

function DocumentReady(callback) {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', callback);
    } else {
        callback();
    }
}

// Upload + controls
function setupUploadInteractions() {
    if (dropZone && fileInput) {
        dropZone.addEventListener('click', () => fileInput.click());
        dropZone.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                fileInput.click();
            }
        });
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('drag-over');
        });
        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('drag-over');
        });
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            handleFiles(e.dataTransfer.files);
        });
    }

    if (fileInput) {
        fileInput.addEventListener('change', (e) => handleFiles(e.target.files));
    }

    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', () => startAnalysis('local'));
    }

    if (startGeminiBtn) {
        startGeminiBtn.addEventListener('click', () => startAnalysis('gemini'));
    }

    if (downloadGeminiReportBtn) {
        downloadGeminiReportBtn.addEventListener('click', () => {
            if (!currentGeminiJobId) {
                return;
            }
            window.location.href = `/api/gemini_report/${currentGeminiJobId}`;
        });
    }

    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', selectAllPages);
    }

    if (deselectAllBtn) {
        deselectAllBtn.addEventListener('click', deselectAllPages);
    }
}

function setupControls() {
    if (confidenceSlider && confidenceValue) {
        confidenceValue.textContent = parseFloat(confidenceSlider.value).toFixed(2);
        confidenceSlider.addEventListener('input', (e) => {
            confidenceValue.textContent = parseFloat(e.target.value).toFixed(2);
        });
    }
}

function handleFiles(files) {
    if (!files || files.length === 0) return;

    const file = files[0];
    const fileNameLower = (file.name || '').toLowerCase();
    const isPdf = (file.type && file.type.toLowerCase().includes('pdf')) || fileNameLower.endsWith('.pdf');

    if (!isPdf) {
        showError('Please select a PDF file');
        return;
    }

    if (file.size > 500 * 1024 * 1024) {
        showError('File size must be less than 500MB');
        return;
    }

    selectedFile = file;
    currentJobId = null;

    if (fileInput && fileInput.files && fileInput.files[0] !== file) {
        try {
            if (window.DataTransfer) {
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(file);
                fileInput.files = dataTransfer.files;
            }
        } catch (err) {
            fileInput.value = '';
        }
    }

    if (fileName) {
        fileName.textContent = file.name;
    }
    if (fileError) {
        fileError.style.display = 'none';
    }
    if (analyzeBtn) {
        analyzeBtn.disabled = false;
    }
    updateGeminiButtonAvailability();

    resetGeminiUI();
    hideDetectionResults();

    generatePagePreviews(file);
}

function showError(message) {
    if (fileError) {
        fileError.textContent = message;
        fileError.style.display = 'block';
    }
    if (fileName) {
        fileName.textContent = '';
    }
    selectedFile = null;
    currentJobId = null;
    if (fileInput) {
        fileInput.value = '';
    }
    if (analyzeBtn) {
        analyzeBtn.disabled = true;
    }
    updateGeminiButtonAvailability();
    resetGeminiUI();
    hideDetectionResults();
    if (pageSelection) {
        pageSelection.style.display = 'none';
    }
}

function resetGeminiUI() {
    if (geminiProgress) {
        geminiProgress.classList.add('hidden');
        geminiProgressText.textContent = '';
    }
    if (geminiResultsSection) {
        geminiResultsSection.classList.add('hidden');
        geminiResultsSection.innerHTML = '';
    }
    currentGeminiJobId = null;
    updateGeminiReportButtonState();
}

function updateGeminiButtonAvailability() {
    if (!startGeminiBtn) {
        return;
    }
    const shouldEnable = geminiConfigured && !!selectedFile;
    startGeminiBtn.disabled = !shouldEnable;
    if (!shouldEnable) {
        const reasons = [];
        if (!geminiConfigured) {
            reasons.push('Gemini API is not configured');
        }
        if (!selectedFile) {
            reasons.push('Upload a PDF to enable Gemini');
        }
        if (reasons.length > 0) {
            startGeminiBtn.title = reasons.join(' • ');
        }
    } else {
        startGeminiBtn.removeAttribute('title');
    }
}

function updateGeminiReportButtonState() {
    if (!downloadGeminiReportBtn) {
        return;
    }

    if (currentGeminiJobId) {
        downloadGeminiReportBtn.disabled = false;
        downloadGeminiReportBtn.removeAttribute('title');
    } else {
        downloadGeminiReportBtn.disabled = true;
        downloadGeminiReportBtn.title = 'Run Gemini analysis to generate the detailed report';
    }
}

function hideDetectionResults() {
    if (resultsSection) {
        resultsSection.style.display = 'none';
    }
    if (previewSection) {
        previewSection.style.display = 'none';
    }
    if (resultsSummary) {
        resultsSummary.innerHTML = '';
    }
    if (devicesGrid) {
        devicesGrid.innerHTML = '';
    }
    if (previewGrid) {
        previewGrid.innerHTML = '';
    }
    if (progressSection) {
        progressSection.style.display = 'none';
    }
    currentJobId = null;
}

function checkStatus() {
    fetch('/api/check_status')
        .then((response) => response.json())
        .then((data) => {
            const detectorDot = document.getElementById('local-model-status');
            const detectorText = document.getElementById('local-model-text');
            if (detectorDot && detectorText) {
                if (data.local_model_configured) {
                    detectorDot.className = 'status-dot online';
                    detectorText.textContent = 'Ready';
                } else {
                    detectorDot.className = 'status-dot offline';
                    detectorText.textContent = 'Model Missing';
                }
            }

            const geminiDot = document.getElementById('gemini-status');
            const geminiText = document.getElementById('gemini-text');
            geminiConfigured = !!data.gemini_configured;
            if (geminiConfigured) {
                geminiDot.className = 'status-dot online';
                geminiText.textContent = 'Connected';
            } else {
                geminiDot.className = 'status-dot offline';
                geminiText.textContent = 'Not Configured';
            }

            updateGeminiButtonAvailability();

            const modelInfo = document.getElementById('model-info');
            if (modelInfo) {
                if (data.local_model_filename) {
                    modelInfo.textContent = data.local_model_filename;
                } else if (data.local_model_name) {
                    modelInfo.textContent = data.local_model_name;
                } else if (data.model_path) {
                    const pathParts = data.model_path.split(/[/\\]/);
                    const modelFilename = pathParts[pathParts.length - 1];
                    modelInfo.textContent = modelFilename || 'No model configured';
                } else {
                    modelInfo.textContent = 'No model configured';
                }
            }
        })
        .catch((error) => console.error('Error checking status:', error));
}

function generatePagePreviews(file) {
    const formData = new FormData();
    formData.append('pdf', file);

    if (pageSelection) {
        pageSelection.style.display = 'none';
    }

    fetch('/api/preview_pages', {
        method: 'POST',
        body: formData,
    })
        .then((response) => response.json())
        .then((data) => {
            if (!data.success) {
                showError('Error generating page previews');
                return;
            }

            const pageGrid = document.getElementById('pageGrid');
            if (!pageGrid) {
                return;
            }
            pageGrid.innerHTML = '';

            data.pages.forEach((page) => {
                const pageThumb = document.createElement('div');
                pageThumb.className = 'page-thumb';
                pageThumb.innerHTML = `
                    <img src="${page.thumbnail}" alt="Page ${page.page_number}">
                    <div class="page-number">Page ${page.page_number}</div>
                `;
                pageThumb.onclick = () => {
                    pageThumb.classList.toggle('selected');
                    updateSelectedCount();
                };
                pageGrid.appendChild(pageThumb);
            });

            if (pageSelection) {
                pageSelection.style.display = 'block';
            }
            updateSelectedCount();
        })
        .catch((error) => {
            console.error('Error:', error);
            showError('Error generating page previews');
        });
}

function updateSelectedCount() {
    const selectedPages = document.querySelectorAll('.page-thumb.selected').length;
    const selectedCount = document.getElementById('selectedCount');
    if (selectedCount) {
        selectedCount.textContent = selectedPages;
    }
}

function selectAllPages() {
    document.querySelectorAll('.page-thumb').forEach((thumb) => {
        thumb.classList.add('selected');
    });
    updateSelectedCount();
}

function deselectAllPages() {
    document.querySelectorAll('.page-thumb').forEach((thumb) => {
        thumb.classList.remove('selected');
    });
    updateSelectedCount();
}

function startAnalysis(type) {
    const file = selectedFile || (fileInput ? fileInput.files[0] : null);
    if (!file) {
        alert('Please select a PDF file first');
        return;
    }

    const formData = new FormData();
    formData.append('pdf', file);

    let endpoint = '';

    if (type === 'local') {
        const selectedPages = Array.from(document.querySelectorAll('.page-thumb.selected')).map((thumb) =>
            parseInt(thumb.querySelector('.page-number').textContent.replace('Page ', ''), 10)
        );

        if (selectedPages.length === 0) {
            alert('Please select at least one page to analyze');
            return;
        }

        formData.append('selected_pages', selectedPages.join(','));

        const skipBlank = document.getElementById('skipBlank');
        const skipEdges = document.getElementById('skipEdges');
        const useParallel = document.getElementById('useParallel');
        const useCache = document.getElementById('useCache');

        formData.append('skip_blank', skipBlank ? skipBlank.checked : false);
        formData.append('skip_edges', skipEdges ? skipEdges.checked : false);
        formData.append('use_parallel', useParallel ? useParallel.checked : false);
        formData.append('use_cache', useCache ? useCache.checked : false);
        formData.append('confidence', confidenceSlider ? confidenceSlider.value : 0.5);

        if (progressSection && progressFill && progressText) {
            progressSection.style.display = 'block';
            progressFill.style.width = '0%';
            progressFill.style.background = 'linear-gradient(90deg, #4ECDC4 0%, #45B7D1 100%)';
            progressText.textContent = 'Starting local analysis...';
        }

        if (analyzeBtn) {
            analyzeBtn.disabled = true;
        }

        endpoint = '/api/analyze';
    } else {
        if (startGeminiBtn) {
            startGeminiBtn.disabled = true;
        }
        if (geminiProgress && geminiProgressText) {
            geminiProgress.classList.remove('hidden');
            geminiProgressText.textContent = 'Analyzing fire alarm scope with Gemini...';
        }
        if (geminiResultsSection) {
            geminiResultsSection.classList.add('hidden');
            geminiResultsSection.innerHTML = '';
        }
        currentGeminiJobId = null;
        updateGeminiReportButtonState();
        endpoint = '/api/analyze_gemini';
    }

    fetch(endpoint, {
        method: 'POST',
        body: formData,
    })
        .then((response) => response.json())
        .then((data) => {
            if (!data.success) {
                throw new Error(data.error || 'Analysis failed');
            }

            if (type === 'local') {
                displayDetectionResults(data);
            } else {
                displayGeminiResults(data);
            }
        })
        .catch((error) => {
            if (type === 'local') {
                if (progressText && progressFill) {
                    progressText.textContent = `Error: ${error.message}`;
                    progressFill.style.width = '100%';
                    progressFill.style.background = '#ff6b6b';
                }
            } else {
                displayGeminiError(error.message);
            }
        })
        .finally(() => {
            if (type === 'local') {
                if (analyzeBtn) {
                    analyzeBtn.disabled = false;
                }
            } else {
                updateGeminiButtonAvailability();
            }
        });
}

function displayDetectionResults(data) {
    currentJobId = data.job_id || null;

    if (progressFill && progressText) {
        progressFill.style.width = '100%';
        progressText.textContent = 'Analysis complete!';
    }

    if (!resultsSection) {
        return;
    }

    resultsSection.style.display = 'block';

    const totalDevices = data.total_devices || 0;
    const pagesWithDevices = data.pages_with_devices || 0;
    const totalPages = data.total_pages || 0;

    if (resultsSummary) {
        resultsSummary.innerHTML = `
            <div class="summary-card">
                <h3>${totalDevices}</h3>
                <p>Total Devices</p>
            </div>
            <div class="summary-card">
                <h3>${pagesWithDevices}</h3>
                <p>Pages with Devices</p>
            </div>
            <div class="summary-card">
                <h3>${totalPages}</h3>
                <p>Total Pages</p>
            </div>
        `;
    }

    if (devicesGrid) {
        devicesGrid.innerHTML = '';
        const aggregatedDevices = aggregateDevicesByType(data.page_analyses);

        if (aggregatedDevices.length === 0) {
            const emptyState = document.createElement('div');
            emptyState.className = 'empty-state';
            emptyState.textContent = 'No fire alarm devices detected.';
            devicesGrid.appendChild(emptyState);
        } else {
            const table = buildDevicesTable(aggregatedDevices);
            devicesGrid.appendChild(table);
        }
    }

    if (previewSection && previewGrid) {
        previewSection.style.display = 'block';
        previewGrid.innerHTML = '';

        if (Array.isArray(data.page_analyses)) {
            data.page_analyses.forEach((page) => {
                if (!page || !Array.isArray(page.devices) || page.devices.length === 0) {
                    return;
                }
                const previewCard = document.createElement('div');
                previewCard.className = 'preview-card';
                previewCard.innerHTML = `
                    <div class="preview-card-title">Page ${page.page_number || 'Unknown'}</div>
                    <div class="preview-card-info">${page.devices.length} devices detected</div>
                    <div class="preview-actions">
                        <button class="preview-btn view" onclick="viewPage('${data.job_id}', ${page.page_number})">View</button>
                        <button class="preview-btn download" onclick="downloadPage('${data.job_id}', ${page.page_number}, this)">Download PDF</button>
                    </div>
                `;
                previewGrid.appendChild(previewCard);
            });
        }
    }

    if (exportBtn && data.job_id) {
        exportBtn.onclick = () => {
            window.location.href = `/api/export/${data.job_id}`;
        };
    }
}

function aggregateDevicesByType(pageAnalyses = []) {
    const map = new Map();

    if (!Array.isArray(pageAnalyses)) {
        return [];
    }

    pageAnalyses.forEach((page) => {
        if (!page || !Array.isArray(page.devices)) {
            return;
        }

        page.devices.forEach((device) => {
            if (!device) {
                return;
            }

            const deviceType = device.device_type || 'Unknown Device';
            if (!map.has(deviceType)) {
                map.set(deviceType, []);
            }

            map.get(deviceType).push({
                page: page.page_number ?? device.page_number ?? null,
                location: device.location || null,
                confidence: typeof device.confidence === 'number' ? device.confidence : null,
            });
        });
    });

    return Array.from(map.entries())
        .map(([deviceType, entries]) => {
            const pageSet = new Set();
            const locationSet = new Set();
            const confidenceValues = [];

            entries.forEach((entry) => {
                if (entry.page !== null && entry.page !== undefined) {
                    pageSet.add(entry.page);
                }
                if (entry.location) {
                    locationSet.add(entry.location);
                }
                if (typeof entry.confidence === 'number') {
                    confidenceValues.push(entry.confidence);
                }
            });

            const sortedPages = Array.from(pageSet).sort((a, b) => a - b);
            const locations = Array.from(locationSet);
            const count = entries.length;
            const avgConfidence =
                confidenceValues.length > 0
                    ? confidenceValues.reduce((sum, value) => sum + value, 0) / confidenceValues.length
                    : null;
            const minConfidence = confidenceValues.length > 0 ? Math.min(...confidenceValues) : null;
            const maxConfidence = confidenceValues.length > 0 ? Math.max(...confidenceValues) : null;

            return {
                deviceType,
                count,
                pages: sortedPages,
                locations,
                avgConfidence,
                minConfidence,
                maxConfidence,
            };
        })
        .sort((a, b) => {
            if (b.count !== a.count) {
                return b.count - a.count;
            }
            return a.deviceType.localeCompare(b.deviceType);
        });
}

function buildDevicesTable(groups) {
    const wrapper = document.createElement('div');
    wrapper.className = 'devices-table-wrapper';

    const table = document.createElement('table');
    table.className = 'devices-table';

    const thead = document.createElement('thead');
    thead.innerHTML = `
        <tr>
            <th scope="col">Device Type</th>
            <th scope="col">Count</th>
            <th scope="col">Pages</th>
            <th scope="col">Locations</th>
            <th scope="col">Confidence</th>
        </tr>
    `;
    table.appendChild(thead);

    const tbody = document.createElement('tbody');

    groups.forEach((group) => {
        const row = document.createElement('tr');

        const typeCell = document.createElement('td');
        typeCell.className = 'device-type-cell';
        typeCell.textContent = group.deviceType;
        row.appendChild(typeCell);

        const countCell = document.createElement('td');
        countCell.textContent = group.count;
        row.appendChild(countCell);

        const pagesCell = document.createElement('td');
        if (group.pages.length > 0) {
            group.pages.forEach((pageNumber) => {
                pagesCell.appendChild(createChip(`Pg ${pageNumber}`));
            });
        } else {
            pagesCell.textContent = '—';
        }
        row.appendChild(pagesCell);

        const locationsCell = document.createElement('td');
        if (group.locations.length > 0) {
            const maxVisible = 5;
            group.locations.slice(0, maxVisible).forEach((location) => {
                locationsCell.appendChild(createChip(location));
            });

            if (group.locations.length > maxVisible) {
                const remainder = group.locations.length - maxVisible;
                locationsCell.appendChild(createChip(`+${remainder} more`, true));
            }
        } else {
            locationsCell.textContent = '—';
        }
        row.appendChild(locationsCell);

        const confidenceCell = document.createElement('td');
        confidenceCell.textContent = formatConfidenceSummary(group);
        row.appendChild(confidenceCell);

        tbody.appendChild(row);
    });

    table.appendChild(tbody);
    wrapper.appendChild(table);
    return wrapper;
}

function createChip(text, isMore = false) {
    const chip = document.createElement('span');
    chip.className = 'table-chip';
    if (isMore) {
        chip.classList.add('more-chip');
    }
    chip.textContent = text;
    return chip;
}

function formatConfidenceSummary(group) {
    const { avgConfidence, minConfidence, maxConfidence } = group;

    const toPercent = (value) => {
        const percentage = (value * 100).toFixed(1);
        return `${percentage.endsWith('.0') ? percentage.slice(0, -2) : percentage}%`;
    };

    if (typeof avgConfidence !== 'number') {
        return 'N/A';
    }

    if (typeof minConfidence === 'number' && typeof maxConfidence === 'number') {
        const sameValue = Math.abs(maxConfidence - minConfidence) < 0.005;
        if (sameValue) {
            return toPercent(avgConfidence);
        }
        return `${toPercent(minConfidence)} - ${toPercent(maxConfidence)} (avg ${toPercent(avgConfidence)})`;
    }

    return toPercent(avgConfidence);
}

function displayGeminiResults(data) {
    if (!geminiResultsSection || !geminiProgress) {
        return;
    }

    geminiProgress.classList.add('hidden');
    geminiResultsSection.classList.remove('hidden');
    geminiResultsSection.innerHTML = '';

    if (!data || !data.success) {
        displayGeminiError(data && data.error ? data.error : 'Gemini analysis failed');
        return;
    }

    currentGeminiJobId = data.job_id || null;
    updateGeminiReportButtonState();

    const {
        project_info: projectInfo = {},
        code_requirements: codeRequirements = {},
        fire_alarm_pages: fireAlarmPages = [],
        fire_alarm_notes: fireAlarmNotes = [],
        mechanical_devices: mechanicalDevices = {},
        specifications = {},
        structured_summary: structuredSummary = {},
        total_pages: totalPages,
        analysis_timestamp: analysisTimestamp,
    } = data;

    geminiResultsSection.appendChild(buildProjectInfoCard(projectInfo));

    const structuredSummaryCard = buildStructuredSummaryCard(structuredSummary);
    if (structuredSummaryCard) {
        geminiResultsSection.appendChild(structuredSummaryCard);
    }

    const pitfallsCard = buildPitfallsCard(structuredSummary, data.possible_pitfalls || data.pitfalls);
    if (pitfallsCard) {
        geminiResultsSection.appendChild(pitfallsCard);
    }

    const highLevelCard = buildHighLevelDetailsCard(specifications);
    if (highLevelCard) {
        geminiResultsSection.appendChild(highLevelCard);
    }

    geminiResultsSection.appendChild(buildCodeCard(codeRequirements));
    geminiResultsSection.appendChild(buildFireAlarmPagesCard(fireAlarmPages));
    geminiResultsSection.appendChild(buildFireAlarmNotesCard(fireAlarmNotes));
    geminiResultsSection.appendChild(buildMechanicalCard(mechanicalDevices));
    geminiResultsSection.appendChild(buildSpecificationsCard(specifications));
    geminiResultsSection.appendChild(buildSummaryCard(totalPages, analysisTimestamp));
}

function displayGeminiError(message) {
    if (!geminiResultsSection) return;

    if (geminiProgress) {
        geminiProgress.classList.add('hidden');
    }
    geminiResultsSection.classList.remove('hidden');
    geminiResultsSection.innerHTML = '';

    currentGeminiJobId = null;
    updateGeminiReportButtonState();

    const { card, content } = createGeminiCard('Gemini Analysis Error', 'full-width');

    const paragraph = document.createElement('p');
    paragraph.textContent = message || 'An unexpected error occurred while running Gemini analysis.';
    content.appendChild(paragraph);

    geminiResultsSection.appendChild(card);
}

function buildProjectInfoCard(projectInfo) {
    const { card, content } = createGeminiCard('Project Overview', 'full-width');
    const details = [
        ['Project Name', projectInfo.project_name],
        ['Location', projectInfo.location],
        ['Project Type', projectInfo.project_type],
        ['Owner / Client', projectInfo.owner],
        ['Architect', projectInfo.architect],
        ['Engineer', projectInfo.engineer],
        ['Project Number', projectInfo.project_number],
    ];

    const actions = document.createElement('div');
    actions.className = 'card-actions';
    const copyButton = document.createElement('button');
    copyButton.type = 'button';
    copyButton.className = 'copy-btn';
    copyButton.textContent = 'Copy Overview';
    copyButton.dataset.defaultText = 'Copy Overview';
    copyButton.setAttribute('aria-label', 'Copy Project Overview');
    copyButton.addEventListener('click', () => {
        const rows = [];
        details.forEach(([label, value]) => {
            if (value !== undefined && value !== null && value !== '') {
                rows.push(`${label}: ${formatValue(value)}`);
            }
        });
        if (projectInfo.scope_summary) {
            rows.push(`Scope Summary: ${projectInfo.scope_summary}`);
        }
        const textToCopy = rows.join('\n');
        copyTextToClipboard(copyButton, textToCopy);
    });
    actions.appendChild(copyButton);
    content.appendChild(actions);

    details.forEach(([label, value]) => content.appendChild(createInfoRow(label, value)));

    if (projectInfo.scope_summary) {
        const scopeHeading = document.createElement('h4');
        scopeHeading.textContent = 'Scope Summary';
        content.appendChild(scopeHeading);

        const scopeParagraph = document.createElement('p');
        scopeParagraph.textContent = projectInfo.scope_summary;
        content.appendChild(scopeParagraph);
    }

    return card;
}

function buildStructuredSummaryCard(structuredSummary = {}) {
    if (!structuredSummary || typeof structuredSummary !== 'object') {
        return null;
    }

    const summaryText =
        structuredSummary.project_summary ||
        structuredSummary.summary ||
        structuredSummary.overview ||
        structuredSummary.scope_summary;
    const sections = getSectionsArray(structuredSummary);

    if (!summaryText && sections.length === 0) {
        return null;
    }

    const { card, content } = createGeminiCard('AI Structured Summary', 'full-width');
    card.classList.add('structured-summary-card');

    const actions = document.createElement('div');
    actions.className = 'card-actions';
    const copyButton = document.createElement('button');
    copyButton.type = 'button';
    copyButton.className = 'copy-btn';
    copyButton.textContent = 'Copy Structured Summary';
    copyButton.dataset.defaultText = 'Copy Structured Summary';
    copyButton.addEventListener('click', () => {
        const textToCopy = serializeStructuredSummary(structuredSummary);
        copyTextToClipboard(copyButton, textToCopy || 'Structured summary not available.');
    });
    actions.appendChild(copyButton);
    content.appendChild(actions);

    if (summaryText) {
        const summaryParagraph = document.createElement('p');
        summaryParagraph.textContent = summaryText;
        content.appendChild(summaryParagraph);
    }

    const sectionList = buildSectionList(sections);
    if (sectionList) {
        content.appendChild(sectionList);
    }

    const helper = document.createElement('p');
    helper.className = 'card-helper';
    helper.textContent = 'Structured in the same order as the AI response so estimators can copy/paste directly into bid notes.';
    content.appendChild(helper);

    return card;
}

function getSectionsArray(structuredSummary = {}) {
    if (!structuredSummary || typeof structuredSummary !== 'object') {
        return [];
    }

    const candidates = [
        structuredSummary.sections,
        structuredSummary.section_list,
        structuredSummary.numbered_sections,
        structuredSummary.summary_sections,
    ];

    for (const candidate of candidates) {
        if (Array.isArray(candidate) && candidate.length > 0) {
            return candidate;
        }
    }

    return [];
}

function buildSectionList(sections = [], level = 1, parentNumber = '') {
    if (!Array.isArray(sections) || sections.length === 0) {
        return null;
    }

    const list = document.createElement('ol');
    list.className = 'structured-section-list';
    if (level > 1) {
        list.classList.add('nested');
    }

    sections.forEach((section, index) => {
        if (!section) {
            return;
        }

        const li = document.createElement('li');
        const sectionNumber =
            section.number ||
            section.section_number ||
            section.index ||
            (parentNumber ? `${parentNumber}.${index + 1}` : `${index + 1}`);
        const titleText = section.title || section.heading || section.name || `Section ${sectionNumber}`;

        const header = document.createElement('div');
        header.className = 'structured-section-header';

        const numberSpan = document.createElement('span');
        numberSpan.className = 'section-number';
        numberSpan.textContent = `${sectionNumber}.`;
        header.appendChild(numberSpan);

        const titleSpan = document.createElement('span');
        titleSpan.className = 'section-title';
        titleSpan.textContent = titleText;
        header.appendChild(titleSpan);

        li.appendChild(header);

        const sectionSummary = section.summary || section.description || section.text || section.detail;
        if (sectionSummary) {
            const summaryParagraph = document.createElement('p');
            summaryParagraph.className = 'section-summary';
            summaryParagraph.textContent = sectionSummary;
            li.appendChild(summaryParagraph);
        }

        const bulletSource = getSectionBulletSource(section);
        const bulletList = buildBulletListFromItems(bulletSource);
        if (bulletList) {
            li.appendChild(bulletList);
        }

        const subsectionCandidates = section.subsections || section.sections || section.children;
        const nestedList = buildSectionList(subsectionCandidates, level + 1, sectionNumber);
        if (nestedList) {
            li.appendChild(nestedList);
        }

        list.appendChild(li);
    });

    if (list.children.length === 0) {
        return null;
    }

    return list;
}

function getSectionBulletSource(section) {
    if (!section || typeof section !== 'object') {
        return [];
    }

    const keys = ['bullets', 'bullet_points', 'items', 'points', 'key_points', 'highlights', 'summary_items'];
    for (const key of keys) {
        if (Array.isArray(section[key]) && section[key].length > 0) {
            return section[key];
        }
    }
    return [];
}

function buildBulletListFromItems(items) {
    if (!Array.isArray(items) || items.length === 0) {
        return null;
    }

    const list = document.createElement('ul');
    list.className = 'structured-bullet-list';

    items.forEach((item) => {
        if (item === undefined || item === null) {
            return;
        }

        const li = document.createElement('li');

        if (typeof item === 'string' || typeof item === 'number') {
            li.textContent = String(item);
        } else if (Array.isArray(item)) {
            const nested = buildBulletListFromItems(item);
            if (nested) {
                li.appendChild(nested);
            }
        } else if (typeof item === 'object') {
            const label = item.label || item.title || item.heading;
            const value = item.value || item.text || item.description || item.detail || item.summary;
            const primary = label && value && label !== value ? `${label}: ${value}` : label || value;
            if (primary) {
                const span = document.createElement('span');
                span.textContent = primary;
                li.appendChild(span);
            }

            if (item.notes || item.action || item.context) {
                const note = document.createElement('div');
                note.className = 'bullet-note';
                note.textContent = item.notes || item.action || item.context;
                li.appendChild(note);
            }

            const nested = buildBulletListFromItems(
                item.items || item.subpoints || item.sub_bullets || item.children || item.bullets || item.details
            );
            if (nested) {
                li.appendChild(nested);
            }
        } else {
            li.textContent = String(item);
        }

        if (li.textContent.trim() || li.querySelector('ul')) {
            list.appendChild(li);
        }
    });

    if (list.children.length === 0) {
        return null;
    }

    return list;
}

function buildPitfallsCard(structuredSummary = {}, fallbackPitfalls = []) {
    const pitfalls = extractPitfallItems(structuredSummary, fallbackPitfalls);
    if (pitfalls.length === 0) {
        return null;
    }

    const { card, content } = createGeminiCard('Possible Pitfalls / Things to Consider', 'full-width');
    card.classList.add('pitfalls-card');

    const list = document.createElement('ul');
    list.className = 'pitfalls-list';
    pitfalls.forEach((pitfall) => {
        const li = document.createElement('li');
        li.textContent = pitfall;
        list.appendChild(li);
    });
    content.appendChild(list);

    const helper = document.createElement('p');
    helper.className = 'card-helper';
    helper.textContent = 'Quick coordination risks pulled from the structured summary so estimators know what to flag.';
    content.appendChild(helper);

    return card;
}

function extractPitfallItems(structuredSummary = {}, fallbackPitfalls = []) {
    const pitfalls = [];
    const candidates = [];

    if (structuredSummary && typeof structuredSummary === 'object') {
        candidates.push(
            structuredSummary.pitfalls,
            structuredSummary.possible_pitfalls,
            structuredSummary.things_to_consider,
            structuredSummary.coordination_risks
        );
    }

    candidates.push(fallbackPitfalls);

    candidates.forEach((candidate) => {
        if (!candidate) {
            return;
        }
        if (Array.isArray(candidate)) {
            candidate.forEach((item) => {
                const text = normalizeStructuredText(item);
                if (text) {
                    pitfalls.push(text);
                }
            });
        } else {
            const text = normalizeStructuredText(candidate);
            if (text) {
                pitfalls.push(text);
            }
        }
    });

    return pitfalls;
}

function serializeStructuredSummary(structuredSummary = {}) {
    if (!structuredSummary || typeof structuredSummary !== 'object') {
        return '';
    }

    const lines = [];
    const summaryText =
        structuredSummary.project_summary ||
        structuredSummary.summary ||
        structuredSummary.overview ||
        structuredSummary.scope_summary;

    if (summaryText) {
        lines.push('Project Summary:');
        lines.push(summaryText);
        lines.push('');
    }

    const sections = getSectionsArray(structuredSummary);
    appendSectionsToLines(sections, lines);

    const pitfalls = extractPitfallItems(structuredSummary);
    if (pitfalls.length > 0) {
        lines.push('', 'Possible Pitfalls / Things to Consider:');
        pitfalls.forEach((pitfall, index) => {
            lines.push(`${index + 1}. ${pitfall}`);
        });
    }

    return lines.filter((line, index, arr) => line !== '' || (index > 0 && arr[index - 1] !== '')).join('\n');
}

function appendSectionsToLines(sections = [], lines = [], parentNumber = '') {
    if (!Array.isArray(sections) || sections.length === 0) {
        return;
    }

    sections.forEach((section, index) => {
        if (!section) {
            return;
        }

        const sectionNumber =
            section.number ||
            section.section_number ||
            section.index ||
            (parentNumber ? `${parentNumber}.${index + 1}` : `${index + 1}`);
        const titleText = section.title || section.heading || section.name || `Section ${sectionNumber}`;
        const sectionSummary = section.summary || section.description || section.text || section.detail || '';
        const headerLine = sectionSummary
            ? `${sectionNumber}. ${titleText} - ${sectionSummary}`
            : `${sectionNumber}. ${titleText}`;
        lines.push(headerLine.trim());

        const bulletSource = getSectionBulletSource(section);
        flattenStructuredItems(bulletSource).forEach((item) => {
            lines.push(`  • ${item}`);
        });

        const subsectionCandidates = section.subsections || section.sections || section.children;
        appendSectionsToLines(subsectionCandidates, lines, sectionNumber);
    });
}

function flattenStructuredItems(items) {
    if (!Array.isArray(items) || items.length === 0) {
        return [];
    }

    const flattened = [];
    items.forEach((item) => {
        if (item === undefined || item === null) {
            return;
        }
        if (Array.isArray(item)) {
            flattened.push(...flattenStructuredItems(item));
            return;
        }
        const text = normalizeStructuredText(item);
        if (text) {
            flattened.push(text);
        }
        if (typeof item === 'object') {
            const nested = item.items || item.subpoints || item.sub_bullets || item.children || item.bullets || item.details;
            flattened.push(...flattenStructuredItems(nested));
        }
    });
    return flattened;
}

function normalizeStructuredText(value) {
    if (value === undefined || value === null) {
        return '';
    }
    if (typeof value === 'string' || typeof value === 'number') {
        return String(value).trim();
    }
    if (typeof value === 'object') {
        const label = value.label || value.title || value.heading || value.name;
        const primary = value.value || value.text || value.description || value.detail || value.summary;
        const supplemental = value.notes || value.action || value.context || value.reason;
        const parts = [];
        if (label && primary && label !== primary) {
            parts.push(`${label}: ${primary}`);
        } else if (label) {
            parts.push(label);
        } else if (primary) {
            parts.push(primary);
        }
        if (supplemental) {
            parts.push(supplemental);
        }
        return parts.join(' — ').trim();
    }
    return String(value).trim();
}

function buildCodeCard(codeRequirements = {}) {
    const { card, content } = createGeminiCard('Fire Alarm Codes & Standards', 'full-width');
    const codes = codeRequirements.fire_alarm_codes || codeRequirements.fire_alarm_standards || [];

    const list = document.createElement('ul');
    if (Array.isArray(codes) && codes.length > 0) {
        codes.forEach((code) => {
            const li = document.createElement('li');
            li.textContent = code;
            list.appendChild(li);
        });
    } else {
        const li = document.createElement('li');
        li.textContent = 'No fire alarm-specific codes were identified in the provided text.';
        list.appendChild(li);
    }

    content.appendChild(list);
    return card;
}

function buildHighLevelDetailsCard(specifications = {}) {
    const sprinklerSystem = getSpecValue(specifications, 'SPRINKLER_SYSTEM');
    const approvedManufacturers = getSpecValue(specifications, 'APPROVED_MANUFACTURERS');
    const audioSystem = getSpecValue(specifications, 'AUDIO_SYSTEM');

    const { card, content } = createGeminiCard('High-Level Fire Alarm Details', 'full-width');

    const rows = [
        ['Sprinkler System Monitoring', sprinklerSystem],
        ['Approved Manufacturers', approvedManufacturers],
        ['Audio / Voice Requirement', audioSystem],
    ];

    rows.forEach(([label, value]) => content.appendChild(createInfoRow(label, value)));

    const helper = document.createElement('p');
    helper.className = 'card-helper';
    helper.textContent = 'Summarizes sprinkler tie-ins, approved vendors, and audio requirements pulled from the fire alarm specs.';
    content.appendChild(helper);

    return card;
}

function buildFireAlarmPagesCard(fireAlarmPages) {
    const { card, content } = createGeminiCard('Fire Alarm Focus Pages');

    if (Array.isArray(fireAlarmPages) && fireAlarmPages.length > 0) {
        const chipContainer = document.createElement('div');
        fireAlarmPages.forEach((page) => {
            const chip = document.createElement('span');
            chip.className = 'gemini-chip';
            chip.textContent = `Page ${page}`;
            chipContainer.appendChild(chip);
        });
        content.appendChild(chipContainer);
    } else {
        content.appendChild(createInfoRow('Pages', null));
    }

    const helper = document.createElement('p');
    helper.textContent = 'These sheets typically include electrical power/special systems plans and general notes containing fire alarm symbols and requirements.';
    content.appendChild(helper);

    return card;
}

function buildFireAlarmNotesCard(fireAlarmNotes) {
    const { card, content } = createGeminiCard('Fire Alarm System Notes', 'full-width');

    if (Array.isArray(fireAlarmNotes) && fireAlarmNotes.length > 0) {
        const list = document.createElement('ul');
        fireAlarmNotes.forEach((note) => {
            if (!note) return;
            const item = document.createElement('li');
            const pageTag = document.createElement('span');
            pageTag.className = 'note-page';
            pageTag.textContent = `Pg ${note.page ?? '?'}`;

            const noteContent = document.createElement('div');
            const noteLabel = document.createElement('strong');
            noteLabel.textContent = `${note.note_type || 'Note'}: `;
            const noteText = document.createElement('span');
            noteText.textContent = note.content || 'Not provided';
            noteContent.appendChild(noteLabel);
            noteContent.appendChild(noteText);

            item.appendChild(pageTag);
            item.appendChild(noteContent);
            list.appendChild(item);
        });
        content.appendChild(list);
    } else {
        const paragraph = document.createElement('p');
        paragraph.textContent = 'No project-specific fire alarm notes were identified.';
        content.appendChild(paragraph);
    }

    return card;
}

function buildMechanicalCard(mechanicalDevices = {}) {
    const { card, content } = createGeminiCard('Mechanical Coordination', 'full-width');
    const { duct_detectors: ductDetectors = [], dampers = [] } = mechanicalDevices;

    const createDeviceList = (title, devices) => {
        const sectionTitle = document.createElement('h4');
        sectionTitle.textContent = title;
        content.appendChild(sectionTitle);

        const list = document.createElement('ul');
        if (Array.isArray(devices) && devices.length > 0) {
            devices.forEach((device) => {
                if (!device) return;
                const li = document.createElement('li');
                const details = [
                    ['Page', device.page],
                    ['Device', device.device_type],
                    ['Location', device.location],
                    ['Quantity', device.quantity],
                    ['Specifications', device.specifications],
                ];
                details.forEach(([label, value]) => {
                    if (!value) return;
                    const detail = document.createElement('div');
                    const strong = document.createElement('strong');
                    strong.textContent = `${label}: `;
                    const span = document.createElement('span');
                    span.textContent = value;
                    detail.appendChild(strong);
                    detail.appendChild(span);
                    li.appendChild(detail);
                });
                list.appendChild(li);
            });
        } else {
            const li = document.createElement('li');
            li.textContent = 'No devices noted.';
            list.appendChild(li);
        }
        content.appendChild(list);
    };

    createDeviceList('Duct Detectors', ductDetectors);
    createDeviceList('Fire/Smoke Dampers', dampers);

    return card;
}

function buildSpecificationsCard(specifications = {}) {
    const { card, content } = createGeminiCard('Fire Alarm System Specifications', 'full-width');

    if (specifications && Object.keys(specifications).length > 0) {
        const reservedKeys = ['SPRINKLER_SYSTEM', 'APPROVED_MANUFACTURERS', 'AUDIO_SYSTEM'];
        const entries = Object.entries(specifications).filter(([key]) => {
            if (!key) return false;
            if (key === 'error') return false;
            const normalized = key.toString().toUpperCase();
            return !reservedKeys.includes(normalized);
        });

        if (entries.length === 0) {
            const paragraph = document.createElement('p');
            paragraph.textContent = 'No additional system specifications were captured.';
            content.appendChild(paragraph);
        } else {
            entries.forEach(([key, value]) => {
                content.appendChild(createInfoRow(formatSpecLabel(key), value));
            });
        }
    } else {
        const paragraph = document.createElement('p');
        paragraph.textContent = 'No additional system specifications were captured.';
        content.appendChild(paragraph);
    }

    return card;
}

function buildSummaryCard(totalPages, analysisTimestamp) {
    const { card, content } = createGeminiCard('Analysis Summary');
    content.appendChild(createInfoRow('Total Pages Reviewed', totalPages));

    if (analysisTimestamp) {
        const summaryDate = new Date(analysisTimestamp);
        const formatted = summaryDate.toLocaleString(undefined, {
            dateStyle: 'medium',
            timeStyle: 'short',
        });
        content.appendChild(createInfoRow('Generated', formatted));
    }

    const helper = document.createElement('p');
    helper.textContent = 'Only cover pages, fire alarm-related electrical sheets, and mechanical notes impacting the fire alarm system were considered. Plumbing and unrelated trades were ignored.';
    content.appendChild(helper);

    return card;
}

function getSpecValue(specifications, key) {
    if (!specifications || !key) {
        return undefined;
    }

    if (Object.prototype.hasOwnProperty.call(specifications, key)) {
        return specifications[key];
    }

    const lower = key.toLowerCase();
    if (Object.prototype.hasOwnProperty.call(specifications, lower)) {
        return specifications[lower];
    }

    const upper = key.toUpperCase();
    if (Object.prototype.hasOwnProperty.call(specifications, upper)) {
        return specifications[upper];
    }

    return undefined;
}

function createGeminiCard(title, extraClass) {
    const card = document.createElement('details');
    card.className = 'gemini-card';
    card.open = true;
    if (extraClass) {
        card.classList.add(extraClass);
    }

    const summary = document.createElement('summary');
    summary.className = 'card-summary';
    const titleSpan = document.createElement('span');
    titleSpan.textContent = title;
    const icon = document.createElement('span');
    icon.className = 'toggle-icon';
    icon.textContent = '−';
    summary.appendChild(titleSpan);
    summary.appendChild(icon);
    card.appendChild(summary);

    const content = document.createElement('div');
    content.className = 'card-content';
    card.appendChild(content);

    card.addEventListener('toggle', () => {
        icon.textContent = card.open ? '−' : '+';
    });

    return { card, content };
}

function createInfoRow(label, value) {
    const row = document.createElement('div');
    row.className = 'info-row';

    const labelEl = document.createElement('span');
    labelEl.className = 'label';
    labelEl.textContent = label;

    const valueEl = document.createElement('span');
    const hasValue = value !== undefined && value !== null && value !== '';
    valueEl.className = `value${hasValue ? '' : ' placeholder'}`;
    valueEl.textContent = hasValue ? formatValue(value) : 'Not provided';

    row.appendChild(labelEl);
    row.appendChild(valueEl);
    return row;
}

function formatSpecLabel(key) {
    if (!key) return 'Specification';
    return key
        .toString()
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatValue(value) {
    if (Array.isArray(value)) {
        return value.join('; ');
    }
    if (typeof value === 'object' && value !== null) {
        return Object.entries(value)
            .map(([k, v]) => `${formatSpecLabel(k)}: ${v}`)
            .join('; ');
    }
    return typeof value === 'string' ? value.trim() : value;
}

async function copyTextToClipboard(button, text) {
    if (!text) {
        return;
    }

    const original = button.dataset.defaultText || button.textContent;
    try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(text);
        } else {
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.focus();
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
        }
        button.textContent = 'Copied!';
        setTimeout(() => {
            button.textContent = original;
        }, 2000);
    } catch (err) {
        console.error('Failed to copy overview', err);
        button.textContent = 'Copy failed';
        setTimeout(() => {
            button.textContent = original;
        }, 2000);
    }
}

// Preview modal helpers
async function viewPage(jobId, pageNum) {
    try {
        const response = await fetch(`/api/visualize/${jobId}/${pageNum}`);
        if (!response.ok) throw new Error(`Failed to fetch page ${pageNum}`);
        const blob = await response.blob();

        const modal = document.getElementById('imageModal');
        const modalImage = document.getElementById('modalImage');
        const modalInfo = document.getElementById('modalInfo');
        const modalDownload = document.getElementById('modalDownload');

        if (!(modal && modalImage && modalInfo && modalDownload)) {
            throw new Error('Preview modal elements missing');
        }

        modalImage.src = URL.createObjectURL(blob);
        modalInfo.textContent = `Page ${pageNum}`;
        modalDownload.onclick = (event) => downloadPage(jobId, pageNum, event.currentTarget);
        modal.classList.add('active');
        modal.setAttribute('aria-hidden', 'false');
    } catch (error) {
        console.error('Error viewing page:', error);
        alert('Error viewing page. Please try again.');
    }
}

function setButtonLoadingState(button, isLoading, loadingText = 'Preparing PDF...') {
    if (!(button instanceof HTMLElement)) {
        return;
    }

    if (isLoading) {
        if (!button.dataset.originalContent) {
            button.dataset.originalContent = button.innerHTML;
        }
        button.disabled = true;
        button.classList.add('btn-loading');
        button.innerHTML = `<span class="button-spinner" aria-hidden="true"></span><span>${loadingText}</span>`;
    } else {
        if (button.dataset.originalContent) {
            button.innerHTML = button.dataset.originalContent;
            delete button.dataset.originalContent;
        }
        button.disabled = false;
        button.classList.remove('btn-loading');
    }
}

async function downloadPage(jobId, pageNum, trigger) {
    const button = trigger instanceof HTMLElement ? trigger : null;
    setButtonLoadingState(button, true);
    try {
        const response = await fetch(`/api/download_annotated_pdf/${jobId}/${pageNum}`);
        const contentType = response.headers.get('content-type') || '';

        if (!response.ok) {
            let errorText = `Download failed (${response.status})`;
            try {
                const text = await response.text();
                const json = JSON.parse(text);
                if (json.error) errorText = json.error;
            } catch (_) {}
            throw new Error(errorText);
        }

        if (contentType.includes('application/pdf')) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `annotated_page_${pageNum}.pdf`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } else {
            const text = await response.text();
            try {
                const data = JSON.parse(text);
                alert(data.error || 'Error downloading PDF');
            } catch {
                alert('Unexpected response while downloading PDF.');
            }
        }
    } catch (error) {
        console.error('Error downloading page:', error);
        alert(error.message || 'Error downloading page. Please try again.');
    } finally {
        setButtonLoadingState(button, false);
    }
}

// Modal handling
const modal = document.getElementById('imageModal');
const modalClose = document.getElementById('modalClose');

if (modalClose && modal) {
    modalClose.onclick = () => {
        modal.classList.remove('active');
        modal.setAttribute('aria-hidden', 'true');
    };
}
if (modal) {
    modal.onclick = (e) => {
        if (e.target === modal) {
            modal.classList.remove('active');
            modal.setAttribute('aria-hidden', 'true');
        }
    };
}

// Expose functions globally for inline handlers
window.viewPage = viewPage;
window.downloadPage = downloadPage;
