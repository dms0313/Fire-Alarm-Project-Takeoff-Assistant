const openSearch = document.getElementById('openSalesSearch');
const closeSearch = document.getElementById('closeSalesSearch');
const dialog = document.getElementById('salesSearchDialog');
const form = document.getElementById('salesSearchForm');
const loader = document.getElementById('salesLoader');
const databaseViewBtn = document.getElementById('databaseViewBtn');
const dashboardTables = document.getElementById('dashboardTables');
const summary = document.getElementById('geminiSalesSummary');

const tableTitles = {
    small: 'Small businesses',
    medium: 'Medium businesses',
    large: 'Large businesses',
};

function setDialog(open) {
    if (open) {
        dialog.classList.remove('hidden');
        requestAnimationFrame(() => dialog.classList.add('active'));
    } else {
        dialog.classList.remove('active');
        setTimeout(() => dialog.classList.add('hidden'), 200);
    }
    dialog.setAttribute('aria-hidden', String(!open));
}

function renderMetrics(tables) {
    const small = tables.small?.length || 0;
    const medium = tables.medium?.length || 0;
    const large = tables.large?.length || 0;
    document.getElementById('smallCount').textContent = small;
    document.getElementById('mediumCount').textContent = medium;
    document.getElementById('largeCount').textContent = large;
    document.getElementById('totalProspects').textContent = small + medium + large;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('\"', '&quot;')
        .replaceAll("'", '&#039;');
}

function renderTable(title, rows) {
    const body = rows.map((row) => `
        <tr>
            <td>${escapeHtml(row.business_name)}</td>
            <td>${escapeHtml(row.point_of_contact)}</td>
            <td>${escapeHtml(row.phone)}</td>
            <td>${escapeHtml(row.email)}</td>
            <td>${escapeHtml(row.estimated_size_reach_footprint)}</td>
        </tr>`).join('');
    return `
        <article class="data-card">
            <div class="section-heading"><h3>${title}</h3><span>${rows.length} rows</span></div>
            <div class="table-scroll">
                <table class="sales-data-table">
                    <thead><tr><th>Business</th><th>Point of contact</th><th>Phone</th><th>Email</th><th>Estimated size / reach / footprint</th></tr></thead>
                    <tbody>${body}</tbody>
                </table>
            </div>
            <details class="json-details"><summary>JSON for shadcn data table</summary><pre>${escapeHtml(JSON.stringify(rows, null, 2))}</pre></details>
        </article>`;
}

function renderDashboard(payload) {
    renderMetrics(payload.tables);
    summary.textContent = payload.summary;
    dashboardTables.innerHTML = Object.entries(tableTitles)
        .map(([key, title]) => renderTable(title, payload.tables[key] || []))
        .join('');
}

async function runSearch(event) {
    event.preventDefault();
    loader.classList.remove('hidden');
    const submit = document.getElementById('runSalesSearch');
    submit.disabled = true;
    try {
        const response = await fetch('/api/sales/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                industry: document.getElementById('salesIndustry').value,
                area: document.getElementById('salesArea').value,
                radius: document.getElementById('salesRadius').value,
            }),
        });
        const payload = await response.json();
        if (!response.ok || !payload.success) throw new Error(payload.error || 'Search failed');
        renderDashboard(payload);
        setDialog(false);
    } catch (error) {
        summary.textContent = error.message;
    } finally {
        loader.classList.add('hidden');
        submit.disabled = false;
    }
}

async function loadDatabase() {
    const response = await fetch('/api/sales/database');
    const payload = await response.json();
    const grouped = { small: [], medium: [], large: [] };
    for (const row of payload.results || []) {
        const key = row.business_size?.toLowerCase().startsWith('small') ? 'small' : row.business_size?.toLowerCase().startsWith('medium') ? 'medium' : 'large';
        grouped[key].push(row);
    }
    renderDashboard({ tables: grouped, summary: `Complete database loaded with ${(payload.results || []).length} prospect rows across ${(payload.searches || []).length} searches.` });
}

openSearch?.addEventListener('click', () => setDialog(true));
closeSearch?.addEventListener('click', () => setDialog(false));
form?.addEventListener('submit', runSearch);
databaseViewBtn?.addEventListener('click', loadDatabase);
