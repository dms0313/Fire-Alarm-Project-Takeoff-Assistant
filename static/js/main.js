// File upload and handling
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const fileName = document.getElementById('fileName');
const fileError = document.getElementById('fileError');
const analyzeBtn = document.getElementById('analyzeBtn');
const analyzeGeminiBtn = document.getElementById('analyzeGeminiBtn');
const pageSelection = document.getElementById('pageSelection');

// Event Listeners
dropZone.addEventListener('click', () => fileInput.click());
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

fileInput.addEventListener('change', (e) => {
    handleFiles(e.target.files);
});

// Confidence slider
document.getElementById('confidence').addEventListener('input', (e) => {
    document.getElementById('confidenceValue').textContent = parseFloat(e.target.value).toFixed(2);
});

function handleFiles(files) {
    if (files.length === 0) return;
    
    const file = files[0];
    if (!file.type.includes('pdf')) {
        showError('Please select a PDF file');
        return;
    }
    
    if (file.size > 50 * 1024 * 1024) {
        showError('File size must be less than 50MB');
        return;
    }
    
    fileName.textContent = file.name;
    fileError.style.display = 'none';
    analyzeBtn.disabled = false;
    analyzeGeminiBtn.disabled = false;
    
    generatePagePreviews(file);
}

function showError(message) {
    fileError.textContent = message;
    fileError.style.display = 'block';
    fileName.textContent = '';
    analyzeBtn.disabled = true;
    analyzeGeminiBtn.disabled = true;
}

function checkStatus() {
    fetch('/api/check_status')
        .then(response => response.json())
        .then(data => {
            const roboflowDot = document.getElementById('roboflow-status');
            const roboflowText = document.getElementById('roboflow-text');
            if (data.roboflow_configured) {
                roboflowDot.className = 'status-dot online';
                roboflowText.textContent = 'Connected';
            } else {
                roboflowDot.className = 'status-dot offline';
                roboflowText.textContent = 'Not Configured';
            }
            
            const geminiDot = document.getElementById('gemini-status');
            const geminiText = document.getElementById('gemini-text');
            if (data.gemini_configured) {
                geminiDot.className = 'status-dot online';
                geminiText.textContent = 'Connected';
            } else {
                geminiDot.className = 'status-dot offline';
                geminiText.textContent = 'Not Configured';
            }
            
            const modelInfo = document.getElementById('model-info');
            if (data.roboflow_workspace && data.roboflow_project) {
                modelInfo.textContent = `${data.roboflow_workspace}/${data.roboflow_project} v${data.roboflow_version}`;
            } else {
                modelInfo.textContent = 'Not Connected';
            }
        })
        .catch(error => console.error('Error checking status:', error));
}

function generatePagePreviews(file) {
    const formData = new FormData();
    formData.append('pdf', file);
    
    pageSelection.style.display = 'none';
    
    fetch('/api/preview_pages', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const pageGrid = document.getElementById('pageGrid');
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
            
            pageSelection.style.display = 'block';
            updateSelectedCount();
        } else {
            showError('Error generating page previews');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showError('Error generating page previews');
    });
}

function updateSelectedCount() {
    const selectedPages = document.querySelectorAll('.page-thumb.selected').length;
    document.getElementById('selectedCount').textContent = selectedPages;
}

function selectAllPages() {
    document.querySelectorAll('.page-thumb').forEach(thumb => {
        thumb.classList.add('selected');
    });
    updateSelectedCount();
}

function deselectAllPages() {
    document.querySelectorAll('.page-thumb').forEach(thumb => {
        thumb.classList.remove('selected');
    });
    updateSelectedCount();
}

// Analysis functions
analyzeBtn.addEventListener('click', () => startAnalysis('roboflow'));
analyzeGeminiBtn.addEventListener('click', () => startAnalysis('gemini'));

function startAnalysis(type) {
    const file = fileInput.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('pdf', file);
    
    const selectedPages = Array.from(document.querySelectorAll('.page-thumb.selected'))
        .map(thumb => parseInt(thumb.querySelector('.page-number').textContent.replace('Page ', '')));
    
    formData.append('selected_pages', selectedPages.join(','));
    
    if (selectedPages.length === 0) {
        alert('Please select at least one page to analyze');
        return;
    }
    
    formData.append('skip_blank', document.getElementById('skipBlank').checked);
    formData.append('skip_edges', document.getElementById('skipEdges').checked);
    formData.append('use_parallel', document.getElementById('useParallel').checked);
    formData.append('use_cache', document.getElementById('useCache').checked);
    formData.append('confidence', document.getElementById('confidence').value);
    
    const progressSection = document.getElementById('progressSection');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    progressSection.style.display = 'block';
    progressFill.style.width = '0%';
    progressText.textContent = 'Starting analysis...';
    
    analyzeBtn.disabled = true;
    analyzeGeminiBtn.disabled = true;
    
    const endpoint = type === 'gemini' ? '/api/analyze_gemini' : '/api/analyze';
    fetch(endpoint, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            progressFill.style.width = '100%';
            progressText.textContent = 'Analysis complete!';
            displayResults(data, type);
        } else {
            throw new Error(data.error || 'Analysis failed');
        }
    })
    .catch(error => {
        progressText.textContent = `Error: ${error.message}`;
        progressFill.style.backgroundColor = '#ff6b6b';
    })
    .finally(() => {
        analyzeBtn.disabled = false;
        analyzeGeminiBtn.disabled = false;
    });
}

function displayResults(data, type) {
    const resultsSection = document.getElementById('resultsSection');
    const resultsSummary = document.getElementById('resultsSummary');
    const devicesGrid = document.getElementById('devicesGrid');
    const previewSection = document.getElementById('previewSection');
    const previewGrid = document.getElementById('previewGrid');
    
    resultsSection.style.display = 'block';
    
    if (type === 'roboflow') {
        const totalDevices = data.total_devices || 0;
        const pagesWithDevices = data.pages_with_devices || 0;
        const totalPages = data.total_pages || 0;
        
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
        
        devicesGrid.innerHTML = '';
        if (data.page_analyses && Array.isArray(data.page_analyses)) {
            data.page_analyses.forEach(page => {
                if (page && Array.isArray(page.devices)) {
                    page.devices.forEach(device => {
                        if (device) {
                            devicesGrid.innerHTML += `
                                <div class="device-card">
                                    <h4>${device.device_type || 'Unknown Device'}</h4>
                                    <div class="device-info">
                                        <span class="label">Location:</span>
                                        <span class="value">${device.location || 'Unknown'}</span>
                                        <span class="label">Confidence:</span>
                                        <span class="value">${device.confidence ? (device.confidence * 100).toFixed(1) + '%' : 'N/A'}</span>
                                    </div>
                                </div>
                            `;
                        }
                    });
                }
            });
        }
        
        previewSection.style.display = 'block';
        previewGrid.innerHTML = '';
        
        if (data.page_analyses && Array.isArray(data.page_analyses)) {
            data.page_analyses.forEach(page => {
                if (page && Array.isArray(page.devices) && page.devices.length > 0) {
                    const previewCard = document.createElement('div');
                    previewCard.className = 'preview-card';
                    previewCard.innerHTML = `
                        <div class="preview-card-title">Page ${page.page_number || 'Unknown'}</div>
                        <div class="preview-card-info">${page.devices.length} devices detected</div>
                        <div class="preview-actions">
                            <button class="preview-btn view" onclick="viewPage('${data.job_id}', ${page.page_number})">View</button>
                            <button class="preview-btn download" onclick="downloadPage('${data.job_id}', ${page.page_number})">Download</button>
                        </div>
                    `;
                    previewGrid.appendChild(previewCard);
                }
            });
        }
        
        // Setup export button
        document.getElementById('exportBtn').onclick = () => {
            window.location.href = `/api/export/${data.job_id}`;
        };
    } else if (data.results) {
        resultsSummary.innerHTML = `
            <div class="summary-card">
                <h3>${data.results.project_info?.project_name || 'N/A'}</h3>
                <p>Project Name</p>
            </div>
            <div class="summary-card">
                <h3>${data.results.fire_alarm_pages?.length || 0}</h3>
                <p>Fire Alarm Pages</p>
            </div>
            <div class="summary-card">
                <h3>${Object.keys(data.results.specifications || {}).length}</h3>
                <p>Specifications Found</p>
            </div>
        `;
    }
}

async function viewPage(jobId, pageNum) {
    try {
        const response = await fetch(`/api/visualize/${jobId}/${pageNum}`);
        if (!response.ok) throw new Error(`Failed to fetch page ${pageNum}`);
        const blob = await response.blob();
        
        const modal = document.getElementById('imageModal');
        const modalImage = document.getElementById('modalImage');
        const modalInfo = document.getElementById('modalInfo');
        const modalDownload = document.getElementById('modalDownload');
        
        modalImage.src = URL.createObjectURL(blob);
        modalInfo.textContent = `Page ${pageNum}`;
        modalDownload.onclick = () => downloadPage(jobId, pageNum);
        modal.classList.add('active');
    } catch (error) {
        console.error('Error viewing page:', error);
        alert('Error viewing page. Please try again.');
    }
}

async function downloadPage(jobId, pageNum) {
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
    }
}

// Modal handling
const modal = document.getElementById('imageModal');
const modalClose = document.getElementById('modalClose');

modalClose.onclick = () => modal.classList.remove('active');
modal.onclick = (e) => {
    if (e.target === modal) modal.classList.remove('active');
};

// Check status on page load
document.addEventListener('DOMContentLoaded', () => {
    checkStatus();
    setInterval(checkStatus, 30000);
});
