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
const tabButtons = document.querySelectorAll('.tab-button');
const tabPanels = document.querySelectorAll('.tab-panel');
const geminiTabBtn = document.getElementById('tabButtonGemini');
const startGeminiBtn = document.getElementById('startGeminiBtn');
const geminiProgress = document.getElementById('geminiProgress');
const geminiProgressText = document.getElementById('geminiProgressText');
const geminiResultsSection = document.getElementById('geminiResultsSection');

let selectedFile = null;
let currentJobId = null;
let geminiConfigured = false;

// Initialisation
DocumentReady(() => {
    setupTabs();
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

// Tab handling
function setupTabs() {
    tabButtons.forEach((button) => {
        button.addEventListener('click', () => {
            if (button.disabled) return;
            switchTab(button.dataset.tab);
        });
    });
}

function switchTab(tabName) {
    tabButtons.forEach((button) => {
        const isActive = button.dataset.tab === tabName;
        button.classList.toggle('active', isActive);
        button.setAttribute('aria-selected', isActive);
    });

    tabPanels.forEach((panel) => {
        const isActive = panel.id === `tab-${tabName}`;
        panel.classList.toggle('active', isActive);
    });
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

    if (file.size > 50 * 1024 * 1024) {
        showError('File size must be less than 50MB');
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
    if (geminiTabBtn) {
        geminiTabBtn.disabled = false;
        geminiTabBtn.removeAttribute('title');
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
    if (geminiTabBtn) {
        geminiTabBtn.disabled = true;
        geminiTabBtn.title = 'Upload a PDF to enable Gemini';
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
                if (data.model_path) {
                    const pathParts = data.model_path.split(/[/\\]/);
                    const modelFilename = pathParts[pathParts.length - 1];
                    modelInfo.textContent = modelFilename || 'No model configured';
                } else if (data.local_model_name) {
                    modelInfo.textContent = data.local_model_name;
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

    const {
        project_info: projectInfo = {},
        code_requirements: codeRequirements = {},
        fire_alarm_pages: fireAlarmPages = [],
        fire_alarm_notes: fireAlarmNotes = [],
        mechanical_devices: mechanicalDevices = {},
        specifications = {},
        total_pages: totalPages,
        analysis_timestamp: analysisTimestamp,
    } = data;

    geminiResultsSection.appendChild(buildProjectInfoCard(projectInfo));
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

    const card = document.createElement('div');
    card.className = 'gemini-card full-width';

    const heading = document.createElement('h3');
    heading.textContent = 'Gemini Analysis Error';
    card.appendChild(heading);

    const paragraph = document.createElement('p');
    paragraph.textContent = message || 'An unexpected error occurred while running Gemini analysis.';
    card.appendChild(paragraph);

    geminiResultsSection.appendChild(card);
}

function buildProjectInfoCard(projectInfo) {
    const card = createGeminiCard('Project Overview', 'full-width');
    const details = [
        ['Project Name', projectInfo.project_name],
        ['Location', projectInfo.location],
        ['Project Type', projectInfo.project_type],
        ['Owner / Client', projectInfo.owner],
        ['Architect', projectInfo.architect],
        ['Engineer', projectInfo.engineer],
        ['Project Number', projectInfo.project_number],
    ];

    details.forEach(([label, value]) => card.appendChild(createInfoRow(label, value)));

    if (projectInfo.scope_summary) {
        const scopeHeading = document.createElement('h4');
        scopeHeading.textContent = 'Scope Summary';
        card.appendChild(scopeHeading);

        const scopeParagraph = document.createElement('p');
        scopeParagraph.textContent = projectInfo.scope_summary;
        card.appendChild(scopeParagraph);
    }

    return card;
}

function buildCodeCard(codeRequirements) {
    const card = createGeminiCard('Applicable Codes & Standards', 'full-width');
    const categories = {
        'Building Codes': codeRequirements.building_codes,
        'Fire Codes': codeRequirements.fire_codes,
        'Electrical Codes': codeRequirements.electrical_codes,
        'Fire Alarm Standards': codeRequirements.fire_alarm_standards,
        'Local Codes': codeRequirements.local_codes,
    };

    Object.entries(categories).forEach(([title, values]) => {
        const sectionTitle = document.createElement('h4');
        sectionTitle.textContent = title;
        card.appendChild(sectionTitle);

        const list = document.createElement('ul');
        if (Array.isArray(values) && values.length > 0) {
            values.forEach((item) => {
                const li = document.createElement('li');
                li.textContent = item;
                list.appendChild(li);
            });
        } else {
            const li = document.createElement('li');
            li.textContent = 'Not specified in the provided pages.';
            list.appendChild(li);
        }
        card.appendChild(list);
    });

    return card;
}

function buildFireAlarmPagesCard(fireAlarmPages) {
    const card = createGeminiCard('Fire Alarm Focus Pages');

    if (Array.isArray(fireAlarmPages) && fireAlarmPages.length > 0) {
        const chipContainer = document.createElement('div');
        fireAlarmPages.forEach((page) => {
            const chip = document.createElement('span');
            chip.className = 'gemini-chip';
            chip.textContent = `Page ${page}`;
            chipContainer.appendChild(chip);
        });
        card.appendChild(chipContainer);
    } else {
        card.appendChild(createInfoRow('Pages', null));
    }

    const helper = document.createElement('p');
    helper.textContent = 'These sheets typically include electrical power/special systems plans and general notes containing fire alarm symbols and requirements.';
    card.appendChild(helper);

    return card;
}

function buildFireAlarmNotesCard(fireAlarmNotes) {
    const card = createGeminiCard('Fire Alarm System Notes', 'full-width');

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
        card.appendChild(list);
    } else {
        const paragraph = document.createElement('p');
        paragraph.textContent = 'No project-specific fire alarm notes were identified.';
        card.appendChild(paragraph);
    }

    return card;
}

function buildMechanicalCard(mechanicalDevices = {}) {
    const card = createGeminiCard('Mechanical Coordination', 'full-width');
    const { duct_detectors: ductDetectors = [], dampers = [] } = mechanicalDevices;

    const createDeviceList = (title, devices) => {
        const sectionTitle = document.createElement('h4');
        sectionTitle.textContent = title;
        card.appendChild(sectionTitle);

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
        card.appendChild(list);
    };

    createDeviceList('Duct Detectors', ductDetectors);
    createDeviceList('Fire/Smoke Dampers', dampers);

    return card;
}

function buildSpecificationsCard(specifications = {}) {
    const card = createGeminiCard('Fire Alarm System Specifications', 'full-width');

    if (specifications && Object.keys(specifications).length > 0) {
        Object.entries(specifications).forEach(([key, value]) => {
            card.appendChild(createInfoRow(formatSpecLabel(key), value));
        });
    } else {
        const paragraph = document.createElement('p');
        paragraph.textContent = 'No additional system specifications were captured.';
        card.appendChild(paragraph);
    }

    return card;
}

function buildSummaryCard(totalPages, analysisTimestamp) {
    const card = createGeminiCard('Analysis Summary');
    card.appendChild(createInfoRow('Total Pages Reviewed', totalPages));

    if (analysisTimestamp) {
        const summaryDate = new Date(analysisTimestamp);
        const formatted = summaryDate.toLocaleString(undefined, {
            dateStyle: 'medium',
            timeStyle: 'short',
        });
        card.appendChild(createInfoRow('Generated', formatted));
    }

    const helper = document.createElement('p');
    helper.textContent = 'Only cover pages, fire alarm-related electrical sheets, and mechanical notes impacting the fire alarm system were considered. Plumbing and unrelated trades were ignored.';
    card.appendChild(helper);

    return card;
}

function createGeminiCard(title, extraClass) {
    const card = document.createElement('div');
    card.className = 'gemini-card';
    if (extraClass) {
        card.classList.add(extraClass);
    }
    const heading = document.createElement('h3');
    heading.textContent = title;
    card.appendChild(heading);
    return card;
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
