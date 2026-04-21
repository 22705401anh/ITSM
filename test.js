
let allUsers = [];

async function loadADUsers() {
    const tbody = document.getElementById('adUsersList');
    const refreshBtn = document.getElementById('refreshBtn');

    // UI Loading state
    refreshBtn.disabled = true;
    refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Refreshing...';
    tbody.innerHTML = `
        <tr>
            <td colspan="7" class="text-center py-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading Active Directory...</span>
                </div>
                <p class="mt-3 text-muted">Querying LDAP server (ma.kostal.int)...</p>
            </td>
        </tr>
    `;

    try {
        const response = await fetch('/api/admin/ad-users');
        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || `Server error: ${response.status}`);
        }

        const rawData = await response.json();

        // Remove empty records, machines ($), and ones without a real name
        allUsers = rawData.filter(u => {
            if (!u || typeof u.username !== 'string' || typeof u.name !== 'string') return false;
            return u.username && 
                   u.username !== 'None' && 
                   !u.username.endsWith('$') &&
                   u.name && 
                   u.name !== 'None';
        });

        document.getElementById('userCount').textContent = allUsers.length.toLocaleString();
        renderUsers(allUsers);

    } catch (e) {
        console.error("AD fetching error:", e);
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center py-5 text-danger">
                    <i class="fas fa-exclamation-triangle fa-3x mb-3"></i>
                    <h5>Error connecting to Active Directory</h5>
                    <p class="text-muted">${e.message}</p>
                    <button class="btn btn-outline-danger mt-2" onclick="loadADUsers()">Try Again</button>
                </td>
            </tr>
        `;
    } finally {
        refreshBtn.disabled = false;
        refreshBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Refresh from AD';
    }
}

function renderUsers(users) {
    const tbody = document.getElementById('adUsersList');

    if (!users || users.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center py-5">
                    <div class="text-muted">
                        <i class="fas fa-search fa-3x mb-3 opacity-50"></i>
                        <p class="mb-0">No users found matching your search</p>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = users.map(user => {
        const uName = user.name === 'None' || !user.name ? '-' : user.name;
        const init = uName !== '-' ? uName.charAt(0).toUpperCase() : '?';
        return `
        <tr>
            <td>
                <div class="d-flex align-items-center">
                    <div class="avatar bg-primary text-white rounded-circle d-flex align-items-center justify-content-center me-3" style="width: 36px; height: 36px;">
                        ${init}
                    </div>
                    <div>
                        <div class="fw-bold">${uName}</div>
                    </div>
                </div>
            </td>
            <td><code>${user.username === 'None' ? '-' : (user.username || '-')}</code></td>
            <td>
                ${(user.email && user.email !== 'None') ? '<a href="mailto:' + user.email + '" class="text-decoration-none"><i class="fas fa-envelope text-muted me-1"></i>' + user.email + '</a>' : '<span class="text-muted">-</span>'}
            </td>
            <td>
                ${(user.department && user.department !== 'None') ? '<span class="badge bg-secondary">' + user.department + '</span>' : '<span class="text-muted">-</span>'}
            </td>
            <td>${(user.title && user.title !== 'None') ? user.title : '<span class="text-muted">-</span>'}</td>
            <td>${(user.company && user.company !== 'None') ? user.company : '<span class="text-muted">-</span>'}</td>
            <td class="text-end">
                <button class="btn btn-sm btn-outline-primary" title="Import User to ITSM" onclick="alert('Import feature coming soon!')">
                    <i class="fas fa-download"></i> Import
                </button>
            </td>
        </tr>
        `}).join('');
}

// Handle search filtering
document.getElementById('searchInput').addEventListener('input', (e) => {
    const term = e.target.value.toLowerCase();

    if (!term) {
        renderUsers(allUsers);
        document.getElementById('userCount').textContent = allUsers.length.toLocaleString();
        return;
    }

    const filtered = allUsers.filter(u => {
        const hasT = (val) => val && typeof val === 'string' && val !== 'None' && val.toLowerCase().includes(term);
        return hasT(u.name) || hasT(u.email) || hasT(u.username) || hasT(u.department);
    });

    renderUsers(filtered);
    document.getElementById('userCount').textContent = filtered.length.toLocaleString();
});

// Load on mount
document.addEventListener('DOMContentLoaded', loadADUsers);
