// ── Device 360 — Catalyst Center Dynamic Sections ──

let deviceId;
const sectionCache = {};
let currentSection = 'summary';
let globalDeviceData = null;

// Section title mapping
const SECTION_TITLES = {
    'summary': 'Summary', 'hw-sw': 'Hardware & Software', 'power': 'Power',
    'fans': 'Fans', 'sfp': 'SFP Modules', 'vlans': 'VLANs',
    'stp': 'Spanning Tree', 'stack': 'StackWise Virtual', 'environment': 'Environment',
    'configuration': 'Running Configuration', 'config-drift': 'Config Drift',
    'udf': 'User Defined Fields', 'stackwise': 'StackWise Virtual',
    'wireless': 'Wireless Info', 'l2-vlan': 'VLAN', 'l2-discovery': 'Discovery Protocols',
    'l2-stp': 'Spanning Tree', 'l2-vtp': 'VTP', 'l2-dhcp': 'DHCP Snooping',
    'l2-igmp': 'IGMP Snooping', 'l2-mld': 'MLD Snooping', 'l2-udld': 'UDLD',
    'l2-auth': 'Authentication', 'l2-logical': 'Logical Ports', 'l2-portcfg': 'Port Configuration',
    'sec-trustsec': 'Cisco TrustSec', 'sec-portcfg': 'Port Configuration',
    'advisories': 'Security Advisories', 'field-notices': 'Field Notices',
    'potential-field-notices': 'Potential Field Notices', 'rep-rings': 'REP Rings',
    'compliance-summary': 'Compliance Summary'
};

// Sections that have SNMP backend
const SNMP_SECTIONS = ['summary','hw-sw','power','fans','sfp','vlans','stp','stack','environment'];

// Alias mappings (sidebar section -> API section)
const SECTION_ALIAS = { 'l2-stp': 'stp', 'l2-vlan': 'vlans', 'stackwise': 'stack' };

// Whether the port grid is in VLAN-color mode
let vlanModeActive = false;

// ── VLAN Color Map ──
const VLAN_MAP = {
    1:   { label: 'Default',           color: '#9ca3af' },  // Neutral Grey
    2:   { label: 'Servers',           color: '#1f2937' },  // Dark Blue-Grey
    5:   { label: 'iSCSI',             color: '#06b6d4' },  // Bright Cyan
    6:   { label: 'iSCSI',             color: '#06b6d4' },
    10:  { label: 'Switches',          color: '#8b5cf6' },  // Bright Violet
    11:  { label: 'Office',            color: '#22c55e' },  // Bright Green
    12:  { label: 'Office',            color: '#22c55e' },
    21:  { label: 'Production',        color: '#f59e0b' },  // Strong Amber
    22:  { label: 'Production',        color: '#f59e0b' },
    23:  { label: 'Production',        color: '#f59e0b' },
    32:  { label: 'Cominfo',           color: '#ec4899' },  // Pink (unique marker)
    41:  { label: 'Printers',          color: '#a855f7' },  // Light Purple
    50:  { label: 'APs',               color: '#3b82f6' },  // Clear Blue
    52:  { label: 'WLAN-Scanners',     color: '#84cc16' },  // Lime Green
    61:  { label: 'CCTV',              color: '#ef4444' },  // Bright Red
    71:  { label: 'Voice',             color: '#f97316' },  // Orange
    72:  { label: 'Voice',             color: '#f97316' },
    73:  { label: 'Voice',             color: '#f97316' },
    200: { label: 'FW-Transfer',       color: '#7f1d1d' },  // Dark Red (critical)
    201: { label: 'PAN-WAN1-Transfer', color: '#000000' },  // Black (external/WAN)
};


function getVlanInfo(vlanId) {
    if (!vlanId) return null;
    return VLAN_MAP[parseInt(vlanId)] || { label: `VLAN ${vlanId}`, color: '#94a3b8' };
}

function toggleVlanLegend() {
    vlanModeActive = !vlanModeActive;

    // Update button appearance
    const btn = document.getElementById('btnVlanLegend');
    if (btn) {
        if (vlanModeActive) {
            btn.style.background = 'var(--primary, #6366f1)';
            btn.style.color = '#fff';
            btn.style.borderColor = 'var(--primary, #6366f1)';
        } else {
            btn.style.background = '';
            btn.style.color = '';
            btn.style.borderColor = '';
        }
    }

    // Show/hide VLAN legend panel
    const panel = document.getElementById('vlanLegendPanel');
    if (panel) {
        if (vlanModeActive) {
            // Build legend items — deduplicated by label
            const seen = new Set();
            let html = '';
            Object.entries(VLAN_MAP).forEach(([id, info]) => {
                if (!seen.has(info.label)) {
                    seen.add(info.label);
                    const ids = Object.entries(VLAN_MAP)
                        .filter(([k, v]) => v.label === info.label)
                        .map(([k]) => k).join(', ');
                    html += `<div style="display:inline-flex;align-items:center;gap:.3rem;padding:.2rem .55rem .2rem .35rem;border-radius:4px;border:1px solid #e5e7eb;background:#fff;margin:.15rem">`
                          + `<span style="width:3px;height:14px;border-radius:2px;background:${info.color};flex-shrink:0;display:inline-block"></span>`
                          + `<span style="font-size:.7rem;font-weight:700;color:#374151;letter-spacing:.01em">${info.label}</span>`
                          + `<span style="font-size:.65rem;color:#9ca3af;font-weight:500">${ids}</span>`
                          + `</div>`;
                }
            });
            panel.innerHTML = html;
            panel.style.display = 'flex';
        } else {
            panel.style.display = 'none';
        }
    }

    // Re-render port grid with current mode
    renderPortGrid();
}

function init360(id) {
    deviceId = id;
    document.addEventListener('DOMContentLoaded', () => {
        // Wire VLAN legend toggle button
        const btnVlan = document.getElementById('btnVlanLegend');
        if (btnVlan) btnVlan.addEventListener('click', toggleVlanLegend);
        loadDeviceData();
    });
}

async function loadDeviceData() {
    try {
        const device = await apiRequest('GET', `/discovery/devices/${deviceId}`);
        globalDeviceData = device;
        document.getElementById('bc-hostname').textContent = device.hostname || 'Unknown';
        document.getElementById('header-hostname').textContent = device.hostname || 'Unknown';
        document.getElementById('header-vendor').textContent = device.vendor || 'Mixed';
        document.getElementById('header-managed-status').textContent = device.status === 'MATCHED' ? 'Managed' : 'Unmanaged';
        document.getElementById('meta-ip').textContent = device.ip_address || '—';
        document.getElementById('meta-model').textContent = device.device_type || 'Generic';
        document.getElementById('meta-uptime').textContent = device.uptime || '—';
        
        // Dynamically load Role and Site
        document.getElementById('meta-role').innerHTML = `${device.role || 'Unassigned'} <i class="fas fa-pencil-alt text-muted ms-1" style="font-size:0.7em"></i>`;
        document.getElementById('meta-site').innerHTML = `${device.site || 'Unassigned'} <i class="fas fa-pencil-alt text-muted ms-1" style="font-size:0.7em"></i>`;
        
        const lastPolled = device.last_polled_at || device.last_seen;
        if (lastPolled) document.getElementById('header-last-seen').textContent = new Date(lastPolled).toLocaleString();

        document.getElementById('supervisor-meta').innerHTML = `
            <div>Platform: <span>${device.device_type || '—'}</span></div>
            <div>Address: <span style="text-transform:uppercase">${device.mac_address || '—'}</span></div>
            <div>Serial: <span>${device.serial_number || '—'}</span></div>
            <div>Role: <span>ACTIVE</span></div>`;

        fetchAndRenderPorts();
        loadSection('summary');
        document.getElementById('pageLoading').style.display = 'none';
        document.getElementById('pageContent').style.display = 'block';
    } catch (error) {
        console.error(error);
        document.getElementById('pageLoading').innerHTML = '<div class="d360-error"><i class="fas fa-exclamation-triangle fs-3 mb-2"></i><p>Failed to load device.</p><a href="/network/discovery" class="btn btn-sm btn-outline-primary mt-2">Go Back</a></div>';
    }
}

let editModalInstance = null;

function editField(field) {
    const currentVal = globalDeviceData[field] || '';
    const label = field === 'role' ? 'Role' : 'Site';
    
    document.getElementById('editFieldModalTitle').textContent = `Edit ${label}`;
    document.getElementById('editFieldLabel').textContent = label;
    document.getElementById('editFieldKey').value = field;
    
    const input = document.getElementById('editFieldValue');
    input.value = currentVal;
    input.placeholder = `Enter new ${label.toLowerCase()}...`;
    
    if (!editModalInstance) {
        editModalInstance = new bootstrap.Modal(document.getElementById('editFieldModal'));
    }
    editModalInstance.show();
    
    setTimeout(() => input.focus(), 150);
}

async function saveField(e) {
    e.preventDefault();
    const field = document.getElementById('editFieldKey').value;
    const newVal = document.getElementById('editFieldValue').value.trim();
    const currentVal = globalDeviceData[field] || '';
    const label = field === 'role' ? 'Role' : 'Site';
    
    if (newVal === currentVal) {
        editModalInstance.hide();
        return;
    }
    
    const btn = document.getElementById('btnSaveField');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    btn.disabled = true;
    
    const payload = {};
    payload[field] = newVal;
    
    try {
        const res = await apiRequest('PATCH', `/discovery/devices/${deviceId}`, payload);
        if (res.status === 'success') {
            globalDeviceData[field] = newVal;
            document.getElementById(`meta-${field}`).innerHTML = `${newVal || 'Unassigned'} <i class="fas fa-pencil-alt text-muted ms-1" style="font-size:0.7em"></i>`;
            showToast(`${label} updated successfully`, "success");
            editModalInstance.hide();
        }
    } catch (err) {
        console.error(err);
        showToast(`Failed to update ${label}`, "danger");
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

async function liveRefresh() {
    const btn = document.getElementById('btnLiveRefresh');
    if (btn) btn.classList.add('fa-spin');
    try {
        await apiRequest('POST', `/discovery/devices/${deviceId}/refresh`);
        // Clear cache so sections re-fetch
        Object.keys(sectionCache).forEach(k => delete sectionCache[k]);
        showToast("Live data refreshed", "success");
        await loadDeviceData();
    } catch (e) {
        console.error(e);
        showToast("Failed to refresh device data", "danger");
    } finally {
        if (btn) btn.classList.remove('fa-spin');
    }
}

// ── Port Grid ──
async function fetchAndRenderPorts() {
    const grid = document.getElementById('portGridContainer');
    try {
        const res = await apiRequest('GET', `/discovery/devices/${deviceId}/ports`);
        const ports = res.ports || [];
        window.globalPortsData = ports;
        if (!ports.length) { grid.innerHTML = '<div style="padding:2rem;color:#6b7280;width:100%;text-align:center">No interface data available.</div>'; return; }
        let phys = ports.filter(p => {
            const n = (p.name || '').toLowerCase();
            return n && !n.startsWith('vl') && !n.startsWith('po') && !n.startsWith('nu') && !n.startsWith('lo') && !n.startsWith('tu') && !n.startsWith('un') && !n.startsWith('veth');
        });
        if (!phys.length) phys = ports;
        window.globalPhysPorts = phys;

        // Count statuses for summary bar
        let cUp = 0, cDown = 0, cAdmin = 0;
        phys.forEach(p => {
            if (p.admin_status == '2') cAdmin++;
            else if (p.admin_status == '1' && p.oper_status == '1') cUp++;
            else cDown++;
        });
        const sumBar = document.getElementById('portSummary');
        if (sumBar) {
            sumBar.style.display = 'flex';
            document.getElementById('ps-up').textContent = cUp;
            document.getElementById('ps-down').textContent = cDown;
            document.getElementById('ps-admin').textContent = cAdmin;
            document.getElementById('ps-total').textContent = phys.length;
        }

        renderCurrentView();
    } catch (e) {
        console.error(e);
        grid.innerHTML = '<div class="d360-error" style="width:100%"><i class="fas fa-times-circle me-1"></i>Failed to fetch SNMP interface data.</div>';
    }
}

let currentViewMode = 'grid';

function setViewMode(mode) {
    if (currentViewMode === mode) return;
    currentViewMode = mode;
    
    document.getElementById('btnViewGrid').classList.toggle('active', mode === 'grid');
    document.getElementById('btnViewList').classList.toggle('active', mode === 'list');
    
    renderCurrentView();
}

function renderCurrentView() {
    if (currentViewMode === 'grid') {
        renderPortGrid();
    } else {
        renderPortList();
    }
}

// Renders (or re-renders) the port grid using the current vlanModeActive state
function renderPortGrid() {
    const grid = document.getElementById('portGridContainer');
    const phys = window.globalPhysPorts;
    if (!grid || !phys) return;

    // Split into odd (top row) / even (bottom row) pairs
    let top = [], bot = [];
    phys.forEach(p => {
        const m = (p.name || '').match(/(\d+)$/);
        if (m) { parseInt(m[1]) % 2 !== 0 ? top.push(p) : bot.push(p); } else top.push(p);
    });

    // Group into modules of 6 port-columns
    const maxCols = Math.max(top.length, bot.length);
    let html = '';
    let moduleHtml = '';
    let colInModule = 0;

    for (let i = 0; i < maxCols; i++) {
        if (colInModule === 0) moduleHtml = '';
        moduleHtml += '<div class="port-col">';
        moduleHtml += i < top.length ? portHTML(top[i]) : '<div style="width:34px;height:30px"></div>';
        moduleHtml += i < bot.length ? portHTML(bot[i]) : '<div style="width:34px;height:30px"></div>';
        moduleHtml += '</div>';
        colInModule++;
        if (colInModule === 6 || i === maxCols - 1) {
            html += '<div class="port-module">' + moduleHtml + '</div>';
            colInModule = 0;
        }
    }
    grid.innerHTML = html;
}

function renderPortList() {
    const grid = document.getElementById('portGridContainer');
    const phys = window.globalPhysPorts;
    if (!grid || !phys) return;

    let html = `<table class="table table-sm table-hover align-middle mb-0" style="font-size:0.85rem">
        <thead class="table-light text-muted" style="font-size:0.75rem; text-transform:uppercase;">
            <tr>
                <th>Port</th>
                <th>Status</th>
                <th>VLAN</th>
                <th>Description</th>
                <th>Speed / MAC</th>
            </tr>
        </thead>
        <tbody>`;

    phys.forEach(p => {
        let statusBadge = '<span class="badge bg-secondary">Down</span>';
        if (p.admin_status == '2') statusBadge = '<span class="badge bg-danger">Admin Down</span>';
        else if (p.admin_status == '1' && p.oper_status == '1') statusBadge = '<span class="badge bg-success">Up</span>';
        
        let vlanBadge = p.vlan_id ? `<span class="badge" style="background:${getVlanInfo(p.vlan_id).color}">${p.vlan_id}</span>` : '<span class="text-muted">—</span>';
        let speedStr = p.speed ? (parseInt(p.speed) >= 1000000000 ? (parseInt(p.speed)/1000000000) + ' Gbps' : (parseInt(p.speed)/1000000) + ' Mbps') : '—';
        
        html += `<tr>
            <td class="fw-bold text-nowrap">${p.name || '—'}</td>
            <td>${statusBadge}</td>
            <td>${vlanBadge}</td>
            <td><div class="text-truncate" style="max-width: 280px;" title="${p.description || ''}">${p.description || '<span class="text-muted">—</span>'}</div></td>
            <td>
                <div class="fw-medium">${speedStr}</div>
                <div class="text-muted small" style="font-family:monospace">${p.mac_address || '—'}</div>
            </td>
        </tr>`;
    });

    html += `</tbody></table>`;
    grid.innerHTML = `<div class="table-responsive w-100" style="max-height:600px; overflow-y:auto;">${html}</div>`;
}

function portHTML(p) {
    let tileCls = 'p-down', statusTxt = 'Not Connected';
    if (p.admin_status == '2') { tileCls = 'p-admin'; statusTxt = 'Admin Down'; }
    else if (p.admin_status == '1' && p.oper_status == '1') { tileCls = 'p-up'; statusTxt = 'Connected'; }

    let name = (p.name||'').replace(/GigabitEthernet/i,'Gi').replace(/FastEthernet/i,'Fa').replace(/TenGigabitEthernet/i,'Te').replace(/TwentyFiveGigE/i,'Twe').replace(/FortyGigabitEthernet/i,'Fo').replace(/HundredGigE/i,'Hu').replace(/StackPort/i,'Stk').replace(/StackSub-St/i,'Sub');

    const dotStyle = tileCls === 'p-up' ? 'background:#22c55e' : tileCls === 'p-admin' ? 'background:#ef4444' : 'background:#94a3b8';
    const desc = p.alias || 'No description';
    const vlanInfo = getVlanInfo(p.vlan_id);

    // VLAN mode: add a colored top-stripe accent
    // Status color (green/grey/red) stays visible; VLAN shown as top bar + badge
    let tileStyle = '', vlanBadge = '';
    if (vlanModeActive && vlanInfo) {
        tileStyle = `style="border-top:3px solid ${vlanInfo.color};position:relative;"`;
        vlanBadge = `<span class="port-vlan-badge" style="background:${vlanInfo.color};color:#fff;font-size:5px;font-weight:800;padding:1px 2px;border-radius:2px;position:absolute;bottom:1px;left:50%;transform:translateX(-50%);white-space:nowrap;line-height:1;pointer-events:none;z-index:3">${p.vlan_id}</span>`;
    }

    // VLAN row in tooltip always visible when there's VLAN data
    const vlanTipRow = vlanInfo
        ? `<div class="port-tip-row"><span class="port-tip-lbl">VLAN</span><span class="port-tip-val" style="color:${vlanInfo.color}">${p.vlan_id} \u2013 ${vlanInfo.label}</span></div>`
        : '';

    const tip = `<div class="port-tip"><div class="port-tip-row"><span class="port-tip-lbl">Port</span><span class="port-tip-val">${p.name}</span></div><div class="port-tip-row"><span class="port-tip-lbl">Status</span><span class="port-tip-val"><span class="port-tip-status" style="${dotStyle}"></span>${statusTxt}</span></div>${vlanTipRow}<div class="port-tip-row"><span class="port-tip-lbl">Description</span><span class="port-tip-val">${desc}</span></div></div>`;

    return `<div class="port-cell" onclick="openPortDetails(${p.index})">${tip}<div class="port-tile ${tileCls}" ${tileStyle}>${vlanBadge}<span class="port-icon"><i class="fas fa-ethernet"></i></span></div><div class="port-lbl">${name}</div></div>`;
}

function openPortDetails(index) {
    const ports = window.globalPortsData || [];
    const p = ports.find(x => x.index == index);
    if (!p) return;

    // Determine status
    let statusTxt = 'Not Connected', bannerCls = 'pm-st-down', pillCls = 'pill-down';
    if (p.admin_status == '2') { statusTxt = 'Admin Down'; bannerCls = 'pm-st-admin'; pillCls = 'pill-admin'; }
    else if (p.admin_status == '1' && p.oper_status == '1') { statusTxt = 'Connected'; bannerCls = 'pm-st-up'; pillCls = 'pill-up'; }

    // Format MAC
    let mac = p.mac || '';
    if (mac.startsWith('0x')) { let raw = mac.substring(2); mac = []; for (let i=0;i<raw.length;i+=2) mac.push(raw.substring(i,i+2)); mac = mac.join(':').toLowerCase(); }
    mac = mac || 'N/A';

    // Format speed
    let speed = parseInt(p.speed) || 0, speedStr = 'N/A';
    if (speed > 0) { if (speed >= 1e9) speedStr = (speed/1e9)+' Gbps'; else if (speed >= 1e6) speedStr = (speed/1e6)+' Mbps'; else speedStr = speed+' bps'; }

    const adminStr = p.admin_status == '1' ? 'Up' : (p.admin_status == '2' ? 'Down' : 'Unknown');

    // Update banner
    const banner = document.getElementById('pm-banner');
    banner.className = 'pm-banner ' + bannerCls;
    document.getElementById('pm-title').textContent = p.name || 'Unknown Port';
    document.getElementById('pm-banner-sub').innerHTML = `
        <span class="pm-status-pill ${pillCls}"><span class="pill-dot"></span>${statusTxt}</span>
        <span>${speedStr}</span>
        <span style="font-family:monospace;text-transform:uppercase">${mac}</span>`;

    // Build body
    const desc = p.alias || '';
    const nName = p.neighbor_name || 'N/A';
    const nIp = p.neighbor_ip || 'N/A';
    const nUser = p.neighbor_user || 'N/A';
    const nMac = p.raw_macs || 'N/A';
    const nCaps = p.neighbor_caps || 'N/A';
    const dSrc = p.data_source || 'Unknown';

    function kvRow(k, v, cls) {
        return `<div class="pm-kv"><span class="pm-kv-k">${k}</span><span class="pm-kv-v ${cls||''}">${v}</span></div>`;
    }

    let dSrcHtml = dSrc;
    if (dSrc === 'Live (SNMP)') {
        dSrcHtml = `<span style="color:#10b981; font-weight:500;"><i class="fas fa-bolt"></i> Live (SNMP)</span>`;
    } else if (dSrc === 'ITSM Assets') {
        dSrcHtml = `<span style="color:#3b82f6; font-weight:500;"><i class="fas fa-database"></i> ITSM Assets</span>`;
    }

    let html = '';

    // ── System Section ──
    html += `<div class="pm-section">
        <div class="pm-section-head"><div class="pm-section-icon si-sys"><i class="fas fa-microchip"></i></div><span class="pm-section-label">Interface Details</span></div>
        <div class="pm-kv-grid">
            ${kvRow('Admin Status', adminStr, adminStr==='Up'?'val-up':'val-down')}
            ${kvRow('Oper Status', statusTxt, statusTxt==='Connected'?'val-up':'val-down')}
            ${kvRow('Speed', speedStr)}
            ${kvRow('MTU', '1500 Bytes')}
            ${kvRow('MAC Address', mac, 'mono')}
            ${kvRow('Type', 'Physical')}
            ${kvRow('Duplex', 'Auto')}
            ${kvRow('Link', 'Auto')}
        </div>
    </div>`;

    // ── VLAN Section ──
    const vlanInfo = getVlanInfo(p.vlan_id);
    if (vlanInfo) {
        html += `<div class="pm-section">
            <div class="pm-section-head"><div class="pm-section-icon" style="background:${vlanInfo.color}1a;color:${vlanInfo.color}"><i class="fas fa-layer-group"></i></div><span class="pm-section-label">VLAN Assignment</span></div>
            <div class="pm-kv-grid">
                ${kvRow('VLAN ID', p.vlan_id)}
                ${kvRow('VLAN Name', `<span style="color:${vlanInfo.color};font-weight:700">${vlanInfo.label}</span>`)}
            </div>
        </div>`;
    }

    // ── Neighbor Section ──
    const hasNeighbor = nName !== 'N/A' || nIp !== 'N/A' || nUser !== 'N/A';
    html += `<div class="pm-section">
        <div class="pm-section-head"><div class="pm-section-icon si-net"><i class="fas fa-network-wired"></i></div><span class="pm-section-label">Connected Devices</span></div>
        <div class="pm-kv-grid">
            ${kvRow('Hostname', nName)}
            ${kvRow('IP Address', nIp, 'mono')}
            ${kvRow('User', nUser)}
            ${kvRow('MAC Address', nMac, 'mono')}
            ${kvRow('Data Source', dSrcHtml)}
            ${kvRow('Capabilities', nCaps)}
        </div>
    </div>`;

    // ── Description Section ──
    if (desc) {
        html += `<div class="pm-section">
            <div class="pm-section-head"><div class="pm-section-icon si-desc"><i class="fas fa-tag"></i></div><span class="pm-section-label">Port Description</span></div>
            <div class="pm-desc-block">${desc}</div>
        </div>`;
    }

    document.getElementById('pm-body').innerHTML = html;
    document.getElementById('portModal').classList.remove('d-none');
}

function closePortDetails(e) {
    if (e && e.target.id !== 'portModal') return;
    document.getElementById('portModal').classList.add('d-none');
}

// ── Sidebar Navigation ──
function toggleSub(el) {
    const sub = el.nextElementSibling;
    if (!sub || !sub.classList.contains('side-sub')) return;
    sub.classList.toggle('open');
    el.classList.toggle('expanded');
}

function sidebarNav(el, section) {
    document.querySelectorAll('#d360Sidebar a[data-section]').forEach(a => a.classList.remove('active'));
    el.classList.add('active');
    loadSection(section);
}

// ── Dynamic Section Loading ──
async function loadSection(section) {
    currentSection = section;
    const titleEl = document.getElementById('sectionTitle');
    const contentEl = document.getElementById('sectionContent');
    titleEl.textContent = SECTION_TITLES[section] || section;

    // Resolve alias
    const apiSection = SECTION_ALIAS[section] || section;

    // Check if this is an SNMP-backed section
    if (!SNMP_SECTIONS.includes(apiSection)) {
        contentEl.innerHTML = renderComingSoon(section);
        return;
    }

    // Check cache
    if (sectionCache[apiSection]) {
        contentEl.innerHTML = renderSection(apiSection, sectionCache[apiSection]);
        return;
    }

    // Show loading
    contentEl.innerHTML = '<div class="d360-loading"><div class="d360-spinner"></div><div>Loading data&hellip;</div></div>';

    try {
        const res = await apiRequest('GET', `/discovery/devices/${deviceId}/detail/${apiSection}`);
        sectionCache[apiSection] = res.data;
        if (currentSection === section) {
            contentEl.innerHTML = renderSection(apiSection, res.data);
        }
    } catch (e) {
        console.error(e);
        if (currentSection === section) {
            contentEl.innerHTML = `<div class="d360-error"><i class="fas fa-exclamation-triangle me-2"></i>${e.message || 'Failed to load section data'}</div>`;
        }
    }
}

// ── Section Renderers ──
function renderSection(section, data) {
    switch (section) {
        case 'summary': return renderSummary(data);
        case 'hw-sw': return renderHwSw(data);
        case 'power': return renderPower(data);
        case 'fans': return renderFans(data);
        case 'sfp': return renderSfp(data);
        case 'vlans': return renderVlans(data);
        case 'stp': return renderStp(data);
        case 'stack': return renderStack(data);
        case 'environment': return renderEnvironment(data);
        default: return renderComingSoon(section);
    }
}

function renderComingSoon(section) {
    const icons = {
        'configuration':'fa-file-code','config-drift':'fa-code-compare','udf':'fa-tags',
        'wireless':'fa-wifi','l2-discovery':'fa-project-diagram','l2-vtp':'fa-network-wired',
        'l2-dhcp':'fa-server','l2-igmp':'fa-broadcast-tower','l2-mld':'fa-broadcast-tower',
        'l2-udld':'fa-link','l2-auth':'fa-shield-alt','l2-logical':'fa-layer-group',
        'l2-portcfg':'fa-cogs','sec-trustsec':'fa-lock','sec-portcfg':'fa-cogs',
        'advisories':'fa-shield-alt','field-notices':'fa-clipboard-list',
        'potential-field-notices':'fa-clipboard-check','rep-rings':'fa-ring',
        'compliance-summary':'fa-check-double'
    };
    const icon = icons[section] || 'fa-tools';
    return `<div class="d360-coming-soon"><i class="fas ${icon}"></i><h5>${SECTION_TITLES[section] || section}</h5><p>This section requires CLI/SSH integration or external API access and is not yet available via SNMP.</p></div>`;
}

function kv(key, val, cls) {
    return `<div class="d360-prop"><span class="d360-prop-k">${key}</span><span class="d360-prop-v ${cls||''}">${val || '—'}</span></div>`;
}

function renderSummary(d) {
    const dev = globalDeviceData || {};
    return `<div class="d360-props">
        ${kv('Hostname', d.sys_name)}${kv('IP Address', dev.ip_address, 'mono')}
        ${kv('Model', d.model)}${kv('MAC Address', dev.mac_address, 'mono')}
        ${kv('Serial Number', d.serial_number)}${kv('Uptime', d.sys_uptime)}
        ${kv('Contact', d.sys_contact)}${kv('Location', d.sys_location)}
        ${kv('OS / Firmware', d.sys_descr)}${kv('Vendor', dev.vendor)}
        ${kv('SNMP Status', dev.snmp_status, dev.snmp_status==='CONNECTED'?'ok':'')}${kv('Device Type', dev.device_type)}
    </div>`;
}

function renderHwSw(d) {
    let html = '<div class="d360-props">';
    const c = d.chassis || {};
    html += kv('Chassis Model', c.model) + kv('IOS Version', c.ios_version);
    html += kv('Hardware Revision', c.hw_revision) + kv('Software Revision', c.sw_revision);
    html += kv('Serial Number', c.serial_number) + kv('Description', c.description);
    html += '</div>';

    if (d.entities && d.entities.length) {
        html += '<div style="margin-top:1.25rem"><div style="font-size:.85rem;font-weight:600;color:#4b5563;margin-bottom:.75rem"><i class="fas fa-microchip me-2"></i>Physical Entities</div>';
        html += '<div class="d360-table-wrap"><table class="d360-table"><thead><tr><th>Class</th><th>Description</th><th>Model</th><th>Serial</th><th>HW Rev</th></tr></thead><tbody>';
        d.entities.forEach(e => {
            html += `<tr><td><span class="tbl-badge active">${e.class}</span></td><td>${e.description}</td><td>${e.model||'—'}</td><td>${e.serial||'—'}</td><td>${e.hw_rev||'—'}</td></tr>`;
        });
        html += '</tbody></table></div></div>';
    }
    return html;
}

function renderPower(d) {
    let html = '';
    if (!d.supplies || !d.supplies.length) {
        html = '<div style="padding:1rem;color:#6b7280;text-align:center">No power supply information available via SNMP.</div>';
    } else {
        html = '<div class="d360-status-grid">';
        d.supplies.forEach(s => {
            const cls = s.ok ? 'ok' : (s.state_code==='2'?'warn': s.state_code==='5'?'off':'crit');
            html += `<div class="d360-status-card ${cls}"><div class="d360-sc-header"><span class="d360-sc-name"><i class="fas fa-plug me-2"></i>${s.name}</span><span class="d360-sc-badge ${cls}">${s.state}</span></div><div class="d360-sc-detail">Index: ${s.index}</div></div>`;
        });
        html += '</div>';
    }
    if (d.poe) {
        const budget = parseInt(d.poe.budget_watts)||0;
        const used = parseInt(d.poe.consumption_watts)||0;
        const pct = budget > 0 ? Math.min(100, Math.round(used/budget*100)) : 0;
        const barColor = pct > 80 ? '#ef4444' : pct > 60 ? '#f59e0b' : '#22c55e';
        html += `<div class="d360-poe-meter"><div style="display:flex;justify-content:space-between;align-items:center"><span style="font-size:.85rem;font-weight:600;color:#1f2937"><i class="fas fa-bolt me-2" style="color:#f59e0b"></i>PoE Budget</span><span style="font-size:.78rem;color:#6b7280">${used}W / ${budget}W (${pct}%)</span></div><div class="d360-poe-bar"><div class="d360-poe-fill" style="width:${pct}%;background:${barColor}"></div></div></div>`;
    }
    return html;
}

function renderFans(d) {
    if (!d.fans || !d.fans.length) return '<div style="padding:1rem;color:#6b7280;text-align:center">No fan information available via SNMP.</div>';
    let html = '<div class="d360-status-grid">';
    d.fans.forEach(f => {
        const cls = f.ok ? 'ok' : (f.state_code==='2'?'warn':'crit');
        html += `<div class="d360-status-card ${cls}"><div class="d360-sc-header"><span class="d360-sc-name"><i class="fas fa-fan me-2"></i>${f.name}</span><span class="d360-sc-badge ${cls}">${f.state}</span></div><div class="d360-sc-detail">Index: ${f.index}</div></div>`;
    });
    return html + '</div>';
}

function renderSfp(d) {
    if (!d.sfp_modules || !d.sfp_modules.length) return '<div style="padding:1rem;color:#6b7280;text-align:center">No SFP/transceiver modules detected via SNMP.</div>';
    let html = '<div class="d360-table-wrap"><table class="d360-table"><thead><tr><th>#</th><th>Description</th><th>Model</th><th>Serial</th></tr></thead><tbody>';
    d.sfp_modules.forEach(s => {
        html += `<tr><td>${s.index}</td><td>${s.description}</td><td>${s.model}</td><td>${s.serial}</td></tr>`;
    });
    return html + '</tbody></table></div>';
}

function renderVlans(d) {
    if (!d.vlans || !d.vlans.length) return '<div style="padding:1rem;color:#6b7280;text-align:center">No VLAN data available via SNMP.</div>';
    let html = `<div style="font-size:.78rem;color:#6b7280;margin-bottom:.75rem">${d.vlans.length} VLANs configured</div>`;
    html += '<div class="d360-table-wrap"><table class="d360-table"><thead><tr><th>VLAN ID</th><th>Name</th><th>State</th><th>Type</th></tr></thead><tbody>';
    d.vlans.forEach(v => {
        const cls = v.state === 'Active' ? 'active' : 'suspended';
        html += `<tr><td><strong>${v.vlan_id}</strong></td><td>${v.name}</td><td><span class="tbl-badge ${cls}">${v.state}</span></td><td>${v.type}</td></tr>`;
    });
    return html + '</tbody></table></div>';
}

function renderStp(d) {
    return `<div class="d360-props d360-stp-grid">
        ${kv('Protocol', d.protocol)}${kv('Bridge Priority', d.bridge_priority)}
        ${kv('Root Priority', d.root_priority)}${kv('Root MAC', d.root_mac, 'mono')}
        ${kv('Root Cost', d.root_cost)}${kv('Root Port', d.root_port)}
        ${kv('Max Age', d.max_age ? d.max_age/100+'s' : '—')}${kv('Hello Time', d.hello_time ? d.hello_time/100+'s' : '—')}
        ${kv('Forward Delay', d.forward_delay ? d.forward_delay/100+'s' : '—')}
    </div>`;
}

function renderStack(d) {
    if (!d.members || !d.members.length) return '<div style="padding:1rem;color:#6b7280;text-align:center">No StackWise data available. Device may not be in a stack.</div>';
    let html = '<div class="d360-table-wrap"><table class="d360-table"><thead><tr><th>Switch #</th><th>Role</th><th>Priority</th><th>MAC Address</th><th>Software Image</th></tr></thead><tbody>';
    d.members.forEach(m => {
        const roleCls = m.role === 'Master' ? 'active' : '';
        html += `<tr><td><strong>${m.switch_num}</strong></td><td><span class="tbl-badge ${roleCls}">${m.role}</span></td><td>${m.priority}</td><td style="font-family:monospace;text-transform:uppercase">${m.mac_address}</td><td>${m.software_image}</td></tr>`;
    });
    return html + '</tbody></table></div>';
}

function renderEnvironment(d) {
    if (!d.sensors || !d.sensors.length) return '<div style="padding:1rem;color:#6b7280;text-align:center">No temperature sensor data available via SNMP.</div>';
    let html = '<div class="d360-status-grid">';
    d.sensors.forEach(s => {
        const val = parseInt(s.value_celsius) || 0;
        const thresh = parseInt(s.threshold_celsius) || 100;
        const pct = Math.min(100, Math.round(val / thresh * 100));
        const cls = s.ok ? 'ok' : (s.state === 'Warning' ? 'warn' : 'crit');
        const barColor = pct > 80 ? '#ef4444' : pct > 60 ? '#f59e0b' : '#22c55e';
        html += `<div class="d360-status-card ${cls}"><div class="d360-sc-header"><span class="d360-sc-name"><i class="fas fa-thermometer-half me-2"></i>${s.name}</span><span class="d360-sc-badge ${cls}">${s.state}</span></div><div class="d360-sc-detail">${s.value_celsius}°C / Threshold: ${s.threshold_celsius}°C</div><div class="d360-temp-bar"><div class="d360-temp-fill" style="width:${pct}%;background:${barColor}"></div></div></div>`;
    });
    return html + '</div>';
}
