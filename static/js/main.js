// DOM references
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const fileName = document.getElementById('fileName');
const fileError = document.getElementById('fileError');
const specDropZone = document.getElementById('specDropZone');
const specFileInput = document.getElementById('specFileInput');
const specFileName = document.getElementById('specFileName');
const analyzeBtn = document.getElementById('analyzeBtn');
const pageSelection = document.getElementById('pageSelection');
const confidenceSlider = document.getElementById('confidence');
const confidenceValue = document.getElementById('confidenceValue');
const selectAllBtn = document.getElementById('selectAllBtn');
const deselectAllBtn = document.getElementById('deselectAllBtn');
const progressSection = document.getElementById('progressSection');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const progressStatus = document.getElementById('progressStatus');
const progressEta = document.getElementById('progressEta');
const resultsSection = document.getElementById('resultsSection');
const resultsSummary = document.getElementById('resultsSummary');
const devicesGrid = document.getElementById('devicesGrid');
const previewSection = document.getElementById('previewSection');
const previewGrid = document.getElementById('previewGrid');
const pageHoverPreview = document.getElementById('pageHoverPreview');
const pageHoverImage = document.getElementById('pageHoverImage');
const pageHoverLabel = document.getElementById('pageHoverLabel');
const pageHoverLens = document.getElementById('pageHoverLens');
const pageGridWrapper = document.getElementById('pageGridWrapper');
const pageSelectionToggle = document.getElementById('pageSelectionToggle');
const exportBtn = document.getElementById('exportBtn');
const startGeminiBtn = document.getElementById('startGeminiBtn');
const downloadGeminiReportBtn = document.getElementById('downloadGeminiReportBtn');
const copyGeminiBtn = document.getElementById('copyGeminiBtn');
const copyGeminiStatus = document.getElementById('copyGeminiStatus');
const sendGeminiImagesCheckbox = document.getElementById('sendGeminiImages');
const geminiProgress = document.getElementById('geminiProgress');
const geminiProgressText = document.getElementById('geminiProgressText');
const geminiEta = document.getElementById('geminiEta');
const geminiResultsSection = document.getElementById('geminiResultsSection');
const geminiStatusMessage = document.getElementById('gemini-status-message');
const geminiModelSelect = document.getElementById('geminiModelSelect');
const geminiPanel = document.getElementById('geminiPanel');
const historyList = document.getElementById('historyList');
const historyStatus = document.getElementById('historyStatus');
const historyToggle = document.getElementById('historyToggle');

const DEVICE_NAME_MAP = {
    cm: 'Control Module',
    co: 'CO Detector',
    dd: 'Duct Detector',
    dh: 'Door Holder',
    ecap: 'Emergency Communications Access Panel',
    ecps: 'Emergency Communications Power Supply',
    ecs: 'Emergency Communication Station',
    faap: 'Remote Annunciator',
    facp: 'Fire Alarm Control Panel',
    fsd: 'Fire/Smoke Damper',
    h_w: 'Horn, Wall Mounted',
    heat: 'Heat Detector',
    hs_c: 'Horn/Strobe, Ceiling Mounted',
    hs_w: 'Horn/Strobe, Wall Mounted',
    hs_w_wp: 'Horn/Strobe, Wall Mounted, Weatherproof',
    loc: 'Local Operating Console',
    mm: 'Monitor Module',
    nac: 'NAC Panel',
    pull: 'Pull Station',
    relay: 'Relay Module',
    rts: 'Remote Test Switch',
    s_w: 'Strobe, Wall Mounted',
    s_w_wp: 'Strobe, Wall Mounted, Weatherproof',
    sc: 'Strobe, Ceiling Mounted',
    smoke: 'Smoke Detector',
    'smoke-co': 'Smoke/CO Combo',
    'smoke-sb': 'Smoke w/ Sounder Base',
    sp_c: 'Speaker, Ceiling Mounted',
    ss_c: 'Speaker/Strobe, Ceiling Mounted',
    ss_w: 'Speaker/Strobe, Wall Mounted',
    ts: 'Tamper Switch',
    wf: 'Waterflow Switch',
};

let selectedFile = null;
let selectedSpecFile = null;
let currentJobId = null;
let geminiConfigured = false;
let currentGeminiJobId = null;
let geminiStatusError = '';
let progressInterval = null;
let progressStartTime = null;
let geminiProgressInterval = null;
let geminiProgressStartTime = null;
let availableGeminiModels = [];
let latestGeminiResults = null;
let pageSelectionCollapsed = true;
let geminiCardIdCounts = {};
let historyCollapsed = true;

const ESTIMATED_LOCAL_DURATION_SECONDS = 80;
const ESTIMATED_GEMINI_DURATION_SECONDS = 90;
const GEMINI_STATUS_STEPS = [
    { threshold: 18, message: 'Extracting text from every page for Gemini...' },
    { threshold: 38, message: 'Reviewing cover sheets for project details...' },
    { threshold: 58, message: 'Scanning fire alarm and special systems pages...' },
    { threshold: 78, message: 'Pulling specs, notes, and mechanical devices...' },
    { threshold: 96, message: 'Building structured takeoff and RFIs...' },
    { threshold: 101, message: 'Finalizing Gemini deliverables...' },
];

// Initialisation
DocumentReady(() => {
    setupUploadInteractions();
    setupControls();
    setupModelSelector();
    setPageSelectionCollapsed(true);
    setHistoryCollapsed(true);
    resetGeminiUI();
    checkStatus();
    setInterval(checkStatus, 30000);
    refreshHistoryList();
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

    if (specDropZone && specFileInput) {
        specDropZone.addEventListener('click', () => specFileInput.click());
        specDropZone.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                specFileInput.click();
            }
        });
        specDropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            specDropZone.classList.add('drag-over');
        });
        specDropZone.addEventListener('dragleave', () => {
            specDropZone.classList.remove('drag-over');
        });
        specDropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            specDropZone.classList.remove('drag-over');
            handleSpecFiles(e.dataTransfer.files);
        });
    }

    if (fileInput) {
        fileInput.addEventListener('change', (e) => handleFiles(e.target.files));
    }

    if (specFileInput) {
        specFileInput.addEventListener('change', (e) => handleSpecFiles(e.target.files));
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

    if (copyGeminiBtn) {
        copyGeminiBtn.addEventListener('click', copyGeminiSections);
    }

    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', selectAllPages);
    }

    if (deselectAllBtn) {
        deselectAllBtn.addEventListener('click', deselectAllPages);
    }

    if (pageSelectionToggle) {
        pageSelectionToggle.addEventListener('click', () => setPageSelectionCollapsed(!pageSelectionCollapsed));
    }

    if (historyToggle) {
        historyToggle.addEventListener('click', () => setHistoryCollapsed(!historyCollapsed));
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

function setupModelSelector() {
    if (!geminiModelSelect) {
        return;
    }

    geminiModelSelect.addEventListener('change', handleGeminiModelChange);
}

function hidePageHoverPreview() {
    if (!pageHoverPreview) {
        return;
    }

    pageHoverPreview.classList.add('hidden');
    pageHoverPreview.setAttribute('aria-hidden', 'true');

    if (pageHoverLens) {
        pageHoverLens.classList.add('hidden');
        pageHoverLens.setAttribute('aria-hidden', 'true');
    }

    if (pageHoverImage) {
        pageHoverImage.style.transform = 'scale(1.2)';
        pageHoverImage.style.transformOrigin = '50% 50%';
    }
}

function setPageSelectionCollapsed(collapsed) {
    pageSelectionCollapsed = collapsed;

    if (pageGridWrapper) {
        pageGridWrapper.classList.toggle('collapsed', collapsed);
    }

    if (pageSelectionToggle) {
        pageSelectionToggle.textContent = collapsed ? 'Expand Page Selection' : 'Collapse Page Selection';
        pageSelectionToggle.setAttribute('aria-expanded', (!collapsed).toString());
    }
}

function positionPageHoverPreview(target) {
    if (!pageHoverPreview || !target) {
        return;
    }

    const offset = 16;
    const previewWidth = pageHoverPreview.offsetWidth || 260;
    const previewHeight = pageHoverPreview.offsetHeight || 320;

    const rect = target.getBoundingClientRect();
    let left = rect.right + offset;

    if (left + previewWidth > window.innerWidth - offset) {
        left = Math.max(offset, rect.left - previewWidth - offset);
    }

    let top = rect.top + rect.height / 2 - previewHeight / 2;
    const maxTop = window.innerHeight - previewHeight - offset;
    top = Math.max(offset, Math.min(top, maxTop));

    pageHoverPreview.style.left = `${left}px`;
    pageHoverPreview.style.top = `${top}px`;
}

function updatePageHoverMagnifier(event) {
    if (!pageHoverImage || !event || !event.currentTarget) {
        return;
    }

    const rect = event.currentTarget.getBoundingClientRect();
    const relativeX = ((event.clientX - rect.left) / rect.width) * 100;
    const relativeY = ((event.clientY - rect.top) / rect.height) * 100;

    pageHoverImage.style.transformOrigin = `${relativeX}% ${relativeY}%`;
    pageHoverImage.style.transform = 'scale(1.35)';

    if (pageHoverLens && pageHoverPreview) {
        const lensSize = pageHoverLens.offsetWidth || 180;
        const halfLens = lensSize / 2;
        const previewRect = pageHoverPreview.getBoundingClientRect();
        let lensLeft = (previewRect.width * (relativeX / 100)) - halfLens;
        let lensTop = (previewRect.height * (relativeY / 100)) - halfLens;

        lensLeft = Math.min(Math.max(8, lensLeft), previewRect.width - lensSize - 8);
        lensTop = Math.min(Math.max(8, lensTop), previewRect.height - lensSize - 8);

        pageHoverLens.style.left = `${lensLeft}px`;
        pageHoverLens.style.top = `${lensTop}px`;
        pageHoverLens.style.backgroundImage = `url(${pageHoverImage.src})`;
        pageHoverLens.style.backgroundSize = '220%';
        pageHoverLens.style.backgroundPosition = `${relativeX}% ${relativeY}%`;
        pageHoverLens.classList.remove('hidden');
        pageHoverLens.setAttribute('aria-hidden', 'false');
    }
}

function showPageHoverPreview(page, event) {
    if (!pageHoverPreview || !pageHoverImage || !pageHoverLabel) {
        return;
    }

    pageHoverImage.src = page.thumbnail;
    pageHoverImage.alt = `Zoomed preview of page ${page.page_number}`;
    pageHoverLabel.textContent = `Page ${page.page_number}`;
    pageHoverPreview.classList.remove('hidden');
    pageHoverPreview.setAttribute('aria-hidden', 'false');
    positionPageHoverPreview(event?.currentTarget);
    updatePageHoverMagnifier(event);
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

function handleSpecFiles(files) {
    if (!files || files.length === 0) return;

    const file = files[0];
    const fileNameLower = (file.name || '').toLowerCase();
    const isPdf = (file.type && file.type.toLowerCase().includes('pdf')) || fileNameLower.endsWith('.pdf');

    if (!isPdf) {
        setCopyStatus('Spec book must be a PDF file.', 'error');
        return;
    }

    if (file.size > 500 * 1024 * 1024) {
        setCopyStatus('Spec book must be less than 500MB.', 'error');
        return;
    }

    selectedSpecFile = file;

    if (specFileInput && specFileInput.files && specFileInput.files[0] !== file) {
        try {
            if (window.DataTransfer) {
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(file);
                specFileInput.files = dataTransfer.files;
            }
        } catch (err) {
            specFileInput.value = '';
        }
    }

    if (specFileName) {
        specFileName.textContent = `Spec book attached: ${file.name}`;
    }
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
    hidePageHoverPreview();
}

function resetGeminiUI() {
    stopGeminiProgress();
    if (geminiProgress) {
        geminiProgress.classList.add('hidden');
        geminiProgressText.textContent = '';
    }
    if (geminiResultsSection) {
        geminiResultsSection.classList.add('hidden');
        geminiResultsSection.innerHTML = '';
    }
    currentGeminiJobId = null;
    latestGeminiResults = null;
    if (copyGeminiBtn) {
        copyGeminiBtn.disabled = true;
    }
    setCopyStatus('');
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
            reasons.push(geminiStatusError ? `Gemini unavailable: ${geminiStatusError}` : 'Gemini API is not configured');
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

function setCopyStatus(message, tone = 'info') {
    if (!copyGeminiStatus) {
        return;
    }

    copyGeminiStatus.textContent = message || '';
    copyGeminiStatus.classList.toggle('hidden', !message);
    copyGeminiStatus.style.color = tone === 'error' ? '#ffb3b3' : '#d0e8ff';
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
    hidePageHoverPreview();
    stopProgressAnimation();
    if (progressSection) {
        progressSection.style.display = 'none';
    }
    currentJobId = null;
}

function stopProgressAnimation() {
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
    progressStartTime = null;
}

function startProgressAnimation(initialStatus = 'Working on your PDF...') {
    if (!progressSection || !progressFill || !progressText) {
        return;
    }

    stopProgressAnimation();

    progressSection.style.display = 'block';
    progressFill.style.width = '5%';
    progressFill.style.background = 'linear-gradient(90deg, #4ECDC4 0%, #45B7D1 100%)';
    progressText.textContent = 'Initializing analysis...';

    if (progressStatus) {
        progressStatus.textContent = initialStatus;
    }
    if (progressEta) {
        progressEta.textContent = 'Estimating time remaining...';
    }

    progressStartTime = Date.now();
    updateProgressAnimation();
    progressInterval = setInterval(() => updateProgressAnimation(), 1000);
}

function updateProgressAnimation(statusOverride) {
    if (!progressFill || !progressText || !progressStartTime) {
        return;
    }

    const elapsedSeconds = (Date.now() - progressStartTime) / 1000;
    const estimatedSeconds = ESTIMATED_LOCAL_DURATION_SECONDS || 60;
    const percent = Math.min(95, Math.max(5, Math.floor((elapsedSeconds / estimatedSeconds) * 95)));

    const statusSteps = [
        { threshold: 25, message: 'Uploading PDF and preparing page previews...' },
        { threshold: 55, message: 'Detecting fire alarm symbols on selected pages...' },
        { threshold: 85, message: 'Building annotated previews and summaries...' },
        { threshold: 96, message: 'Finalizing results...' },
    ];

    const autoStatus = statusSteps.find((step) => percent < step.threshold) || statusSteps[statusSteps.length - 1];

    progressFill.style.width = `${percent}%`;
    progressText.textContent = `Working... ${percent}%`;

    if (progressStatus) {
        progressStatus.textContent = statusOverride || autoStatus.message;
    }

    if (progressEta) {
        const remainingSeconds = Math.max(0, Math.ceil(estimatedSeconds - elapsedSeconds));
        progressEta.textContent = `${remainingSeconds}s remaining (estimated)`;
    }
}

function finishProgressAnimation(message = 'Analysis complete!') {
    stopProgressAnimation();

    if (progressFill) {
        progressFill.style.width = '100%';
    }
    if (progressText) {
        progressText.textContent = message;
    }
    if (progressStatus) {
        progressStatus.textContent = 'Detection finished';
    }
    if (progressEta) {
        progressEta.textContent = 'Done';
    }
}

function failProgressAnimation(errorMessage) {
    stopProgressAnimation();

    if (progressFill) {
        progressFill.style.width = '100%';
        progressFill.style.background = '#ff6b6b';
    }
    if (progressText) {
        progressText.textContent = `Error: ${errorMessage}`;
    }
    if (progressStatus) {
        progressStatus.textContent = 'Analysis stopped';
    }
    if (progressEta) {
        progressEta.textContent = 'No active process';
    }
}

function startGeminiProgress(statusText = 'Analyzing fire alarm scope with Gemini...') {
    if (!geminiProgress || !geminiProgressText) {
        return;
    }

    stopGeminiProgress();
    geminiProgress.classList.remove('hidden');
    geminiProgressText.textContent = statusText;
    if (geminiEta) {
        geminiEta.textContent = 'Estimating time remaining...';
    }

    geminiProgressStartTime = Date.now();
    updateGeminiProgress(statusText);
    geminiProgressInterval = setInterval(() => updateGeminiProgress(), 1000);
}

function updateGeminiProgress(statusText) {
    if (!geminiProgressText || !geminiProgressStartTime) {
        return;
    }

    const elapsedSeconds = (Date.now() - geminiProgressStartTime) / 1000;
    const estimatedSeconds = ESTIMATED_GEMINI_DURATION_SECONDS || 90;
    const percent = Math.min(98, Math.max(5, Math.floor((elapsedSeconds / estimatedSeconds) * 98)));

    const autoStatus = GEMINI_STATUS_STEPS.find((step) => percent < step.threshold)
        || GEMINI_STATUS_STEPS[GEMINI_STATUS_STEPS.length - 1];
    const activeStatus = statusText || autoStatus.message;

    geminiProgressText.textContent = `${percent}% • ${activeStatus}`;

    if (geminiEta) {
        const remainingSeconds = Math.max(0, Math.ceil(estimatedSeconds - elapsedSeconds));
        geminiEta.textContent = `${remainingSeconds}s remaining (estimated)`;
    }
}

function stopGeminiProgress(message) {
    if (geminiProgressInterval) {
        clearInterval(geminiProgressInterval);
        geminiProgressInterval = null;
    }
    geminiProgressStartTime = null;

    if (message && geminiProgressText) {
        geminiProgressText.textContent = message;
    }
    if (message && geminiEta) {
        geminiEta.textContent = 'Done';
    }
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
            geminiStatusError = data.gemini_error || '';
            if (geminiConfigured) {
                geminiDot.className = 'status-dot online';
                geminiText.textContent = 'Connected';
            } else {
                geminiDot.className = 'status-dot offline';
                geminiText.textContent = 'Not Configured';
            }

            if (geminiStatusMessage) {
                if (!geminiConfigured && geminiStatusError) {
                    geminiStatusMessage.textContent = `Gemini unavailable: ${geminiStatusError}`;
                    geminiStatusMessage.classList.remove('hidden');
                } else {
                    geminiStatusMessage.textContent = '';
                    geminiStatusMessage.classList.add('hidden');
                }
            }

            updateGeminiButtonAvailability();

            const modelInfo = document.getElementById('model-info');
            if (modelInfo) {
                availableGeminiModels = Array.isArray(data.available_gemini_models)
                    ? data.available_gemini_models
                    : [];
                populateGeminiModelOptions(availableGeminiModels, data.gemini_model);

                const modelLabel = data.gemini_model ? `Gemini: ${data.gemini_model}` : '';
                const localLabel = data.local_model_filename
                    ? `Local: ${data.local_model_filename}`
                    : data.local_model_name
                        ? `Local: ${data.local_model_name}`
                        : '';

                const resolvedModelInfo = modelLabel || localLabel;

                if (resolvedModelInfo) {
                    modelInfo.textContent = resolvedModelInfo;
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

function populateGeminiModelOptions(models = [], currentModel) {
    if (!geminiModelSelect) {
        return;
    }

    const uniqueModels = Array.from(new Set(models.filter(Boolean)));
    geminiModelSelect.innerHTML = '';

    if (uniqueModels.length === 0 && currentModel) {
        uniqueModels.push(currentModel);
    }

    uniqueModels.forEach((model) => {
        const option = document.createElement('option');
        option.value = model;
        option.textContent = model;
        if (currentModel && model === currentModel) {
            option.selected = true;
        }
        geminiModelSelect.appendChild(option);
    });
}

function handleGeminiModelChange(event) {
    const { value } = event.target;
    if (!value) {
        return;
    }

    geminiModelSelect.disabled = true;
    const statusEl = document.getElementById('gemini-status-message');
    if (statusEl) {
        statusEl.classList.remove('hidden');
        statusEl.textContent = `Switching Gemini model to ${value}...`;
    }

    fetch('/api/set_gemini_model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: value }),
    })
        .then((response) => response.json().then((data) => ({ ok: response.ok, data })))
        .then(({ ok, data }) => {
            if (!ok || !data.success) {
                throw new Error(data.error || 'Failed to switch Gemini model');
            }
            if (statusEl) {
                statusEl.textContent = `Gemini model set to ${data.gemini_model}`;
            }
            checkStatus();
        })
        .catch((error) => {
            console.error(error);
            if (statusEl) {
                statusEl.textContent = error.message;
            }
        })
        .finally(() => {
            geminiModelSelect.disabled = false;
        });
}

function generatePagePreviews(file) {
    const formData = new FormData();
    formData.append('pdf', file);

    if (pageSelection) {
        pageSelection.style.display = 'none';
    }
    hidePageHoverPreview();

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
                pageThumb.addEventListener('mouseenter', (event) => showPageHoverPreview(page, event));
                pageThumb.addEventListener('mousemove', (event) => {
                    positionPageHoverPreview(event.currentTarget);
                    updatePageHoverMagnifier(event);
                });
                pageThumb.addEventListener('mouseleave', hidePageHoverPreview);
                pageThumb.onclick = () => {
                    pageThumb.classList.toggle('selected');
                    updateSelectedCount();
                };
                pageGrid.appendChild(pageThumb);
            });

            if (pageSelection) {
                pageSelection.style.display = 'block';
            }
            setPageSelectionCollapsed(true);
            updateSelectedCount();
        })
        .catch((error) => {
            console.error('Error:', error);
            showError('Error generating page previews');
            hidePageHoverPreview();
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

        startProgressAnimation('Uploading PDF and preparing pages...');

        if (analyzeBtn) {
            analyzeBtn.disabled = true;
        }

        endpoint = '/api/analyze';
    } else {
        if (startGeminiBtn) {
            startGeminiBtn.disabled = true;
        }
        startGeminiProgress('Analyzing fire alarm scope with Gemini...');
        if (copyGeminiBtn) {
            copyGeminiBtn.disabled = true;
        }
        setCopyStatus('');
        latestGeminiResults = null;
        if (geminiResultsSection) {
            geminiResultsSection.classList.add('hidden');
            geminiResultsSection.innerHTML = '';
        }
        currentGeminiJobId = null;
        updateGeminiReportButtonState();
        endpoint = '/api/analyze_gemini';
        const sendGeminiImages = sendGeminiImagesCheckbox ? sendGeminiImagesCheckbox.checked : false;
        formData.append('send_images', sendGeminiImages);
        const specFile = selectedSpecFile || (specFileInput ? specFileInput.files[0] : null);
        if (specFile) {
            formData.append('spec_pdf', specFile);
        }
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
                failProgressAnimation(error.message);
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

function displayDetectionResults(data, options = {}) {
    const { fromHistory = false } = options;
    currentJobId = data.job_id || null;

    if (!fromHistory) {
        finishProgressAnimation('Analysis complete!');
    } else if (progressSection) {
        progressSection.classList.add('hidden');
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

    if (!fromHistory) {
        refreshHistoryList();
    }
}

function aggregateDevicesByType(pageAnalyses = []) {
    const map = new Map();

    const getDisplayName = (deviceType) => {
        if (!deviceType) {
            return 'Unknown Device';
        }
        const normalized = String(deviceType).toLowerCase();
        return DEVICE_NAME_MAP[normalized] || deviceType;
    };

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
            const displayName = getDisplayName(deviceType);
            if (!map.has(displayName)) {
                map.set(displayName, []);
            }

            map.get(displayName).push({
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

function displayGeminiResults(data, options = {}) {
    const { fromHistory = false } = options;
    if (!geminiResultsSection || !geminiProgress) {
        return;
    }

    if (!fromHistory) {
        stopGeminiProgress('Gemini analysis complete');
    }
    geminiProgress.classList.add('hidden');
    geminiResultsSection.classList.remove('hidden');
    geminiResultsSection.innerHTML = '';
    geminiCardIdCounts = {};

    if (!data || !data.success) {
        displayGeminiError(data && data.error ? data.error : 'Gemini analysis failed');
        return;
    }

    currentGeminiJobId = data.job_id || null;
    updateGeminiReportButtonState();
    latestGeminiResults = data;
    if (copyGeminiBtn) {
        copyGeminiBtn.disabled = false;
        copyGeminiBtn.title = 'Copy the AI sections to your clipboard';
    }
    setCopyStatus(fromHistory ? 'Loaded from history.' : 'Ready to copy the Gemini summary and sections.');

    const {
        project_info: projectInfo = {},
        high_level_overview: highLevelOverview = {},
        fire_alarm_briefing: fireAlarmBriefing = {},
        code_requirements: codeRequirements = {},
        fire_alarm_pages: fireAlarmPages = [],
        fire_alarm_notes: fireAlarmNotes = [],
        mechanical_devices: mechanicalDevices = {},
        specifications = {},
        structured_summary: structuredSummary = {},
        total_pages: totalPages,
        analysis_timestamp: analysisTimestamp,
    } = data;

    const overviewCard = buildHighLevelOverviewCard(highLevelOverview, projectInfo);
    if (overviewCard) {
        geminiResultsSection.appendChild(overviewCard);
    }

    const briefingCard = buildFireAlarmBriefingCard(
        fireAlarmBriefing,
        structuredSummary,
        fireAlarmNotes,
        fireAlarmPages
    );
    if (briefingCard) {
        geminiResultsSection.appendChild(briefingCard);
    }

    const mechanicalCard = buildMechanicalRequirementsCard(mechanicalDevices);
    if (mechanicalCard) {
        geminiResultsSection.appendChild(mechanicalCard);
    }

    const pitfallsCard = buildPitfallsCard(structuredSummary, data.possible_pitfalls || data.pitfalls);
    if (pitfallsCard) {
        geminiResultsSection.appendChild(pitfallsCard);
    }

    geminiResultsSection.appendChild(buildSummaryCard(totalPages, analysisTimestamp));

    const tableOfContents = buildGeminiTableOfContents();
    if (tableOfContents) {
        geminiResultsSection.prepend(tableOfContents);
    }

    if (!fromHistory) {
        refreshHistoryList();
    }
}

function buildGeminiTableOfContents() {
    if (!geminiResultsSection) {
        return null;
    }

    const cards = Array.from(geminiResultsSection.querySelectorAll('.gemini-card'));
    if (!cards.length) {
        return null;
    }

    const items = cards
        .map((card) => {
            const title = card.querySelector('.card-summary span')?.textContent?.trim();
            const id = card.id;
            if (!title || !id) {
                return null;
            }
            return { id, title, card };
        })
        .filter(Boolean);

    if (!items.length) {
        return null;
    }

    const container = document.createElement('div');
    container.className = 'gemini-toc';

    const heading = document.createElement('h3');
    heading.textContent = 'Table of Contents';
    container.appendChild(heading);

    const list = document.createElement('ol');
    items.forEach((item) => {
        const listItem = document.createElement('li');
        const link = document.createElement('a');
        link.href = `#${item.id}`;
        link.textContent = item.title;
        link.addEventListener('click', (event) => {
            event.preventDefault();
            const target = document.getElementById(item.id);
            if (target) {
                target.open = true;
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
        listItem.appendChild(link);
        list.appendChild(listItem);
    });

    container.appendChild(list);
    return container;
}

function displayGeminiError(message) {
    if (!geminiResultsSection) return;

    stopGeminiProgress('Gemini analysis stopped');
    if (geminiProgress) {
        geminiProgress.classList.add('hidden');
    }
    geminiResultsSection.classList.remove('hidden');
    geminiResultsSection.innerHTML = '';
    geminiCardIdCounts = {};

    currentGeminiJobId = null;
    updateGeminiReportButtonState();
    latestGeminiResults = null;
    if (copyGeminiBtn) {
        copyGeminiBtn.disabled = true;
    }
    setCopyStatus('');

    const { card, content } = createGeminiCard('Gemini Analysis Error', 'full-width');

    const paragraph = document.createElement('p');
    paragraph.textContent = message || 'An unexpected error occurred while running Gemini analysis.';
    content.appendChild(paragraph);

    geminiResultsSection.appendChild(card);
}

function buildHighLevelOverviewCard(overview = {}, fallbackProjectInfo = {}) {
    const resolved = {
        ...fallbackProjectInfo,
        ...overview,
    };

    const rows = [
        ['Project Name', resolved.project_name || resolved.name],
        ['Address / Location', resolved.project_address || resolved.project_location || resolved.location],
        ['Project Type', resolved.project_type],
        ['Fire Alarm Required', resolved.fire_alarm_required],
        ['Sprinkler Status', resolved.sprinkler_status],
    ];

    const hasContent = rows.some(([, value]) => value) || resolved.scope_summary;
    if (!hasContent) {
        return null;
    }

    const { card, content } = createGeminiCard('Project Snapshot', 'full-width');
    rows.forEach(([label, value]) => content.appendChild(createInfoRow(label, value)));

    if (resolved.scope_summary) {
        const scopeHeading = document.createElement('h4');
        scopeHeading.textContent = 'Scope Summary';
        content.appendChild(scopeHeading);

        const scopeParagraph = document.createElement('p');
        scopeParagraph.textContent = resolved.scope_summary;
        content.appendChild(scopeParagraph);
    }

    return card;
}

function buildFireAlarmBriefingCard(briefing = {}, structuredSummary = {}, fireAlarmNotes = [], fireAlarmPages = []) {
    const requirements = [];
    (briefing.requirements || []).forEach((item) => requirements.push(item));
    (briefing.equipment || []).forEach((item) => requirements.push(item));

    const { card, content } = createGeminiCard('Fire Alarm Briefing', 'full-width');
    let populated = false;

    if (requirements.length > 0) {
        const reqHeading = document.createElement('h4');
        reqHeading.textContent = 'Key Requirements & Equipment';
        content.appendChild(reqHeading);

        const list = document.createElement('ul');
        requirements.forEach((req) => {
            const li = document.createElement('li');
            li.textContent = req;
            list.appendChild(li);
        });
        content.appendChild(list);
        populated = true;
    }

    const codes = Array.isArray(briefing.codes) ? briefing.codes : [];
    if (codes.length > 0) {
        const codeHeading = document.createElement('h4');
        codeHeading.textContent = 'Referenced Fire Alarm Codes';
        content.appendChild(codeHeading);

        const chipContainer = document.createElement('div');
        codes.forEach((code) => {
            const chip = document.createElement('span');
            chip.className = 'gemini-chip';
            chip.textContent = code;
            chipContainer.appendChild(chip);
        });
        content.appendChild(chipContainer);
        populated = true;
    }

    const summarySections = structuredSummary && structuredSummary.sections ? structuredSummary.sections : {};
    const estimatingNotes = summarySections.estimating_notes || [];
    if (estimatingNotes.length > 0) {
        const notesHeading = document.createElement('h4');
        notesHeading.textContent = 'Estimating & Coordination Notes';
        content.appendChild(notesHeading);

        const list = document.createElement('ul');
        estimatingNotes.forEach((note) => {
            const li = document.createElement('li');
            li.textContent = normalizeStructuredText(note);
            list.appendChild(li);
        });
        content.appendChild(list);
        populated = true;
    }

    const pages = Array.isArray(fireAlarmPages) ? fireAlarmPages : [];
    if (pages.length > 0) {
        const pageHeading = document.createElement('h4');
        pageHeading.textContent = 'Fire Alarm Focus Pages';
        content.appendChild(pageHeading);

        const chipContainer = document.createElement('div');
        pages.forEach((page) => {
            const chip = document.createElement('span');
            chip.className = 'gemini-chip';
            chip.textContent = `Page ${page}`;
            chipContainer.appendChild(chip);
        });
        content.appendChild(chipContainer);
        populated = true;
    }

    const notes = Array.isArray(briefing.notes) && briefing.notes.length > 0 ? briefing.notes : fireAlarmNotes;
    if (Array.isArray(notes) && notes.length > 0) {
        const faNotesHeading = document.createElement('h4');
        faNotesHeading.textContent = 'Project-Specific Fire Alarm Notes';
        content.appendChild(faNotesHeading);

        const list = document.createElement('ul');
        notes.forEach((note) => {
            if (!note) return;
            const li = document.createElement('li');
            const pageTag = document.createElement('span');
            pageTag.className = 'note-page';
            pageTag.textContent = `Pg ${note.page ?? '?'}`;
            const noteText = document.createElement('span');
            noteText.textContent = note.content || note.note || note.text || '';
            li.appendChild(pageTag);
            li.appendChild(noteText);
            list.appendChild(li);
        });
        content.appendChild(list);
        populated = true;
    }

    if (!populated) {
        const paragraph = document.createElement('p');
        paragraph.textContent = 'No fire alarm-specific requirements were identified in the AI summary.';
        content.appendChild(paragraph);
    }

    const helper = document.createElement('p');
    helper.className = 'card-helper';
    helper.textContent = 'Packed summary of the fire alarm scope, codes, and keyed notes from the Gemini analysis.';
    content.appendChild(helper);

    return card;
}

function buildMechanicalRequirementsCard(mechanicalDevices = {}) {
    const { duct_detectors: ductDetectors = [], dampers = [] } = mechanicalDevices;
    const hasDevices = (Array.isArray(ductDetectors) && ductDetectors.length > 0) || (Array.isArray(dampers) && dampers.length > 0);

    if (!hasDevices) {
        const { card, content } = createGeminiCard('Mechanical Requirements (Fire Alarm)', 'full-width');
        const paragraph = document.createElement('p');
        paragraph.textContent = 'No duct detector or smoke damper requirements were detected in the provided pages.';
        content.appendChild(paragraph);
        return card;
    }

    const { card, content } = createGeminiCard('Mechanical Requirements (Fire Alarm)', 'full-width');

    const createDeviceSection = (title, devices) => {
        const heading = document.createElement('h4');
        heading.textContent = title;
        content.appendChild(heading);

        const list = document.createElement('ul');
        if (Array.isArray(devices) && devices.length > 0) {
            devices.forEach((device) => {
                const li = document.createElement('li');
                const parts = [];
                if (device.page) parts.push(`Page ${device.page}`);
                if (device.device_type) parts.push(device.device_type);
                if (device.location) parts.push(device.location);
                if (device.quantity) parts.push(`Qty ${device.quantity}`);
                if (device.specifications) parts.push(device.specifications);
                li.textContent = parts.filter(Boolean).join(' — ');
                list.appendChild(li);
            });
        } else {
            const li = document.createElement('li');
            li.textContent = 'No devices noted.';
            list.appendChild(li);
        }
        content.appendChild(list);
    };

    createDeviceSection('Duct Detectors', ductDetectors);
    createDeviceSection('Smoke / Fire Dampers', dampers);

    const helper = document.createElement('p');
    helper.className = 'card-helper';
    helper.textContent = 'Lists duct detectors and smoke dampers that must report to the fire alarm system for coordination with mechanical sheets.';
    content.appendChild(helper);

    return card;
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
    const conflicts = collectConflictSignals(structuredSummary);
    const advisories = collectAdvisoryNotes(structuredSummary);

    if (pitfalls.length === 0 && conflicts.length === 0 && advisories.length === 0) {
        return null;
    }

    const { card, content } = createGeminiCard('Conflicts, Pitfalls & Advice', 'full-width');
    card.classList.add('pitfalls-card');

    if (conflicts.length > 0) {
        const heading = document.createElement('h4');
        heading.className = 'insight-group-title';
        heading.textContent = 'Potentially Conflicting Information';
        content.appendChild(heading);

        const conflictList = document.createElement('ul');
        conflictList.className = 'insight-list';
        conflicts.forEach((conflict) => {
            const li = document.createElement('li');
            li.textContent = conflict;
            conflictList.appendChild(li);
        });
        content.appendChild(conflictList);
    }

    if (pitfalls.length > 0) {
        const heading = document.createElement('h4');
        heading.className = 'insight-group-title';
        heading.textContent = 'Pitfalls / Things to Watch';
        content.appendChild(heading);

        const list = document.createElement('ul');
        list.className = 'pitfalls-list';
        pitfalls.forEach((pitfall) => {
            const li = document.createElement('li');
            li.textContent = pitfall;
            list.appendChild(li);
        });
        content.appendChild(list);
    }

    if (advisories.length > 0) {
        const heading = document.createElement('h4');
        heading.className = 'insight-group-title';
        heading.textContent = 'Advice & Coordination Notes';
        content.appendChild(heading);

        const adviceList = document.createElement('ul');
        adviceList.className = 'insight-list';
        advisories.forEach((advice) => {
            const li = document.createElement('li');
            li.textContent = advice;
            adviceList.appendChild(li);
        });
        content.appendChild(adviceList);
    }

    const helper = document.createElement('p');
    helper.className = 'card-helper';
    helper.textContent = 'Quick conflicts, risks, and coordination notes pulled from the structured summary so estimators know what to flag.';
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

function collectConflictSignals(structuredSummary = {}) {
    return collectFlaggedItemsFromSummary(structuredSummary, [
        'conflict',
        'discrep',
        'mismatch',
        'versus',
        'inconsistent',
        'not align',
        'contradict',
    ]);
}

function collectAdvisoryNotes(structuredSummary = {}) {
    const baseNotes = [];
    if (structuredSummary && structuredSummary.sections && structuredSummary.sections.estimating_notes) {
        baseNotes.push(...structuredSummary.sections.estimating_notes);
    }

    const flagged = collectFlaggedItemsFromSummary(
        structuredSummary,
        ['verify', 'coordinate', 'confirm', 'tbd', 'unknown', 'not shown', 'by others', 'field', 'review']
    );

    const unique = new Set();
    [...baseNotes, ...flagged].forEach((note) => {
        const normalized = normalizeStructuredText(note);
        if (normalized) {
            unique.add(normalized);
        }
    });

    return Array.from(unique);
}

function collectFlaggedItemsFromSummary(structuredSummary = {}, keywords = []) {
    if (!keywords || keywords.length === 0) {
        return [];
    }

    const normalizedKeywords = keywords.map((keyword) => keyword.toLowerCase());
    const matches = new Set();

    const texts = gatherSectionTexts(structuredSummary);
    texts.forEach((text) => {
        const normalized = normalizeStructuredText(text);
        if (!normalized) {
            return;
        }
        const lower = normalized.toLowerCase();
        if (normalizedKeywords.some((keyword) => lower.includes(keyword))) {
            matches.add(normalized);
        }
    });

    return Array.from(matches);
}

function gatherSectionTexts(structuredSummary = {}) {
    const texts = [];

    const sections = getSectionsArray(structuredSummary);
    const traverse = (section) => {
        if (!section) {
            return;
        }
        const summaryText = section.summary || section.description || section.text || section.detail;
        if (summaryText) {
            texts.push(summaryText);
        }

        const bulletSource = getSectionBulletSource(section);
        flattenStructuredItems(bulletSource).forEach((item) => texts.push(item));

        const nested = section.subsections || section.sections || section.children;
        if (Array.isArray(nested)) {
            nested.forEach(traverse);
        }
    };

    sections.forEach(traverse);

    if (structuredSummary && structuredSummary.sections) {
        Object.values(structuredSummary.sections).forEach((value) => {
            if (Array.isArray(value)) {
                value.forEach((item) => texts.push(item));
            }
        });
    }

    return texts.filter(Boolean);
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

function buildGeminiCardId(title) {
    if (!title) {
        return '';
    }

    const baseId = `gemini-${title}`
        .toLowerCase()
        .replace(/[^a-z0-9\s-]/g, '')
        .trim()
        .replace(/\s+/g, '-');

    if (!geminiCardIdCounts[baseId]) {
        geminiCardIdCounts[baseId] = 0;
    }

    geminiCardIdCounts[baseId] += 1;
    const suffix = geminiCardIdCounts[baseId] > 1 ? `-${geminiCardIdCounts[baseId]}` : '';

    return `${baseId}${suffix}`;
}

function createGeminiCard(title, extraClass) {
    const card = document.createElement('details');
    card.className = 'gemini-card';
    card.open = true;
    const cardId = buildGeminiCardId(title);
    if (cardId) {
        card.id = cardId;
    }
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

function copyGeminiSections() {
    if (!latestGeminiResults || !latestGeminiResults.success) {
        setCopyStatus('Run Gemini analysis before copying sections.', 'error');
        return;
    }

    const text = buildCopyableSectionsText(latestGeminiResults);
    if (!text) {
        setCopyStatus('No Gemini content is available to copy yet.', 'error');
        return;
    }

    const onSuccess = () => setCopyStatus('Copied all Gemini sections to your clipboard.');
    const onError = () =>
        setCopyStatus('Unable to copy automatically. Select the text manually and use Ctrl/Cmd + C.', 'error');

    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(onSuccess).catch(() => {
            fallbackCopyToClipboard(text, onSuccess, onError);
        });
    } else {
        fallbackCopyToClipboard(text, onSuccess, onError);
    }
}

function fallbackCopyToClipboard(text, onSuccess, onError) {
    try {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        textarea.setAttribute('readonly', '');
        document.body.appendChild(textarea);
        textarea.select();
        const successful = document.execCommand('copy');
        document.body.removeChild(textarea);
        if (successful) {
            onSuccess();
        } else {
            onError();
        }
    } catch (err) {
        console.error('Copy failed', err);
        onError();
    }
}

function buildCopyableSectionsText(data = {}) {
    const lines = [];
    const overview = {
        ...(data.project_info || {}),
        ...(data.high_level_overview || {}),
    };

    const overviewLines = [];
    appendFormattedLine('Project', overview.project_name || overview.name, overviewLines);
    appendFormattedLine('Location', overview.project_address || overview.project_location || overview.location, overviewLines);
    appendFormattedLine('Project Type', overview.project_type, overviewLines);
    appendFormattedLine('Fire Alarm Required', overview.fire_alarm_required, overviewLines);
    appendFormattedLine('Sprinkler Status', overview.sprinkler_status, overviewLines);
    appendFormattedLine('Scope', overview.scope_summary, overviewLines);

    if (overviewLines.length > 0) {
        lines.push('Project Snapshot:');
        lines.push(...overviewLines.map((line) => `- ${line}`));
    }

    const structuredSummary = data.structured_summary || {};
    const serializedSummary = serializeStructuredSummary(structuredSummary);
    if (serializedSummary) {
        lines.push('', 'AI Structured Summary:', serializedSummary);
    }

    const conflicts = collectConflictSignals(structuredSummary);
    const pitfalls = extractPitfallItems(structuredSummary, data.possible_pitfalls || data.pitfalls);
    const advisories = collectAdvisoryNotes(structuredSummary);
    if (conflicts.length > 0 || pitfalls.length > 0 || advisories.length > 0) {
        lines.push('', 'Conflicts / Pitfalls / Advice:');
        conflicts.forEach((item, index) => lines.push(`C${index + 1}. ${item}`));
        pitfalls.forEach((item, index) => lines.push(`P${index + 1}. ${item}`));
        advisories.forEach((item, index) => lines.push(`A${index + 1}. ${item}`));
    }

    if (data.analysis_timestamp) {
        const summaryDate = new Date(data.analysis_timestamp);
        lines.push('', `Generated: ${summaryDate.toLocaleString()}`);
    }

    return lines.filter((line) => line !== undefined && line !== null).join('\n');
}

function appendFormattedLine(label, value, lines = []) {
    if (!lines || !Array.isArray(lines)) {
        return;
    }
    const normalized = normalizeStructuredText(value);
    if (normalized) {
        lines.push(`${label}: ${normalized}`);
    }
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

// History management
async function refreshHistoryList() {
    if (!historyList) {
        return;
    }

    setHistoryStatus('Loading recent projects...');
    historyList.innerHTML = '';

    try {
        const response = await fetch('/api/history');
        const payload = await response.json();
        if (!payload.success) {
            throw new Error(payload.error || 'Failed to load history');
        }

        renderHistoryEntries(payload.entries || []);
    } catch (error) {
        setHistoryStatus(error.message || 'Unable to load history', true);
    }
}

function setHistoryCollapsed(collapsed) {
    historyCollapsed = collapsed;

    if (historyList) {
        historyList.classList.toggle('collapsed', collapsed);
    }

    if (historyToggle) {
        historyToggle.textContent = collapsed ? 'Show History' : 'Hide History';
        historyToggle.setAttribute('aria-expanded', (!collapsed).toString());
    }
}

function setHistoryStatus(message, isError = false) {
    if (!historyStatus) return;
    historyStatus.textContent = message || '';
    historyStatus.classList.toggle('error', Boolean(isError));
}

function handleEditProjectTitle(entry) {
    if (!entry?.job_id) {
        return;
    }

    const currentTitle = entry.project_name || entry.original_filename || 'Untitled Project';
    const newTitle = prompt('Edit project title', currentTitle);

    if (newTitle === null) {
        return;
    }

    const trimmed = newTitle.trim();
    if (!trimmed) {
        setHistoryStatus('Project title cannot be empty.', true);
        return;
    }

    updateHistoryTitle(entry.job_id, trimmed);
}

async function updateHistoryTitle(jobId, projectName) {
    try {
        const response = await fetch(`/api/history/${jobId}/title`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ project_name: projectName }),
        });

        const payload = await response.json();
        if (!payload.success) {
            throw new Error(payload.error || 'Failed to update project title');
        }

        setHistoryStatus('Project title updated.');
        refreshHistoryList();
    } catch (error) {
        setHistoryStatus(error.message || 'Unable to update project title', true);
    }
}

function handleDeleteHistory(jobId) {
    if (!jobId) return;

    const confirmed = window.confirm('Delete this saved project? This cannot be undone.');
    if (!confirmed) return;

    deleteHistoryEntry(jobId);
}

async function deleteHistoryEntry(jobId) {
    setHistoryStatus('Removing project...');
    try {
        const response = await fetch(`/api/history/${jobId}`, { method: 'DELETE' });
        const payload = await response.json();

        if (!payload.success) {
            throw new Error(payload.error || 'Failed to delete project');
        }

        setHistoryStatus('Project removed.');
        refreshHistoryList();
    } catch (error) {
        setHistoryStatus(error.message || 'Unable to delete project', true);
    }
}

function renderHistoryEntries(entries = []) {
    if (!historyList) {
        return;
    }

    historyList.innerHTML = '';

    if (!entries.length) {
        const emptyState = document.createElement('div');
        emptyState.className = 'history-subtle';
        emptyState.textContent = 'No analyses saved yet. Run a local or Gemini scan to build your project history.';
        historyList.appendChild(emptyState);
        setHistoryStatus('');
        return;
    }

    entries.forEach((entry) => {
        const card = buildHistoryCard(entry);
        if (card) {
            historyList.appendChild(card);
        }
    });

    setHistoryStatus(`Showing ${entries.length} saved ${entries.length === 1 ? 'project' : 'projects'}.`);
}

function buildHistoryCard(entry) {
    const card = document.createElement('div');
    card.className = 'history-card';

    const preview = document.createElement('div');
    preview.className = 'history-preview';
    const previewImg = document.createElement('img');
    previewImg.loading = 'lazy';
    previewImg.src = `/api/history/${entry.job_id}/preview`;
    previewImg.alt = `Preview image for ${entry.project_name || entry.original_filename || 'project'}`;
    previewImg.onerror = () => {
        previewImg.remove();
        const fallback = document.createElement('div');
        fallback.className = 'history-preview-fallback';
        fallback.textContent = 'Preview unavailable';
        preview.appendChild(fallback);
    };
    preview.appendChild(previewImg);
    card.appendChild(preview);

    const title = document.createElement('h4');
    title.textContent = entry.project_name || entry.original_filename || 'Untitled Project';
    card.appendChild(title);

    const meta = document.createElement('div');
    meta.className = 'history-meta';
    const type = document.createElement('span');
    type.className = `history-type ${entry.analysis_type === 'local' ? 'local' : ''}`;
    type.textContent = entry.analysis_type === 'gemini' ? 'Gemini' : 'Local';
    meta.appendChild(type);

    if (entry.timestamp) {
        const time = document.createElement('span');
        time.textContent = formatTimestamp(entry.timestamp);
        meta.appendChild(time);
    }

    card.appendChild(meta);

    if (entry.original_filename) {
        const filename = document.createElement('div');
        filename.className = 'history-subtle';
        filename.textContent = entry.original_filename;
        card.appendChild(filename);
    }

    const actions = document.createElement('div');
    actions.className = 'history-actions';
    const openBtn = document.createElement('button');
    openBtn.className = entry.analysis_type === 'gemini' ? 'btn btn-gemini' : 'btn';
    openBtn.textContent = 'Open';
    openBtn.onclick = () => loadHistoryEntry(entry.job_id, entry.analysis_type);
    actions.appendChild(openBtn);

    const editBtn = document.createElement('button');
    editBtn.className = 'btn btn-secondary';
    editBtn.textContent = 'Edit Title';
    editBtn.onclick = () => handleEditProjectTitle(entry);
    actions.appendChild(editBtn);

    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'btn btn-danger';
    deleteBtn.textContent = 'Delete';
    deleteBtn.onclick = () => handleDeleteHistory(entry.job_id);
    actions.appendChild(deleteBtn);

    card.appendChild(actions);
    return card;
}

async function loadHistoryEntry(jobId, analysisType) {
    if (!jobId) return;

    setHistoryStatus('Loading saved results...');
    try {
        const response = await fetch(`/api/history/${jobId}`);
        const payload = await response.json();
        if (!payload.success) {
            throw new Error(payload.error || 'Unable to load saved results');
        }

        const resultData = payload.data || {};
        const type = payload.analysis_type || analysisType;

        if (type === 'gemini') {
            displayGeminiResults(resultData, { fromHistory: true });
            geminiPanel?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } else {
            displayDetectionResults(resultData, { fromHistory: true });
            resultsSection?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }

        setHistoryStatus(`Loaded ${payload.project_name || 'saved project'}.`);
    } catch (error) {
        console.error('History load error', error);
        setHistoryStatus(error.message || 'Unable to load saved results', true);
    }
}

function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    if (Number.isNaN(date.getTime())) {
        return timestamp;
    }
    return date.toLocaleString();
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
