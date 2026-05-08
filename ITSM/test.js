
document.addEventListener('DOMContentLoaded', async function() {
    const assetType = "{{ asset_type }}";
    const assetId = "{{ asset_id }}";
    
    // Formatting Helpers
    const formatDate = (isoString) => {
        if (!isoString) return '-';
        const d = new Date(isoString);
        return d.toLocaleString([], { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute:'2-digit' });
    };

    const typeIcons = {
        'pc': 'fa-laptop',
        'monitor': 'fa-desktop',
        'docking_station': 'fa-plug',
        'printer': 'fa-print',
        'phone': 'fa-phone-alt',
        'phone_number': 'fa-hashtag'
    };
    const typeNames = {
        'pc': 'Computer System',
        'monitor': 'Display Unit',
        'docking_station': 'Docking Hub',
        'printer': 'Printer',
        'phone': 'VoIP Phone',
        'phone_number': 'Phone Line / SIM'
    };

    // Start BOTH fetches in parallel immediately!
    const detailPromise = fetch(`/api/hardware/detail/${assetType}/${assetId}`);
    const historyPromise = fetch(`/api/hardware/history/${assetType}/${assetId}`);

    try {
        const res = await detailPromise;
        if (!res.ok) throw new Error("Asset not found");
        const asset = await res.json();

        // Reveal dashboard
        document.getElementById('dashboardContent').style.display = 'flex';
        
        // 1. Header & Passport
        document.getElementById('assetTitle').innerHTML = asset.model || typeNames[assetType];
        document.getElementById('assetSubtitle').innerHTML = `Internal DB ID: #${asset.id}`;
        document.getElementById('assetBadge').innerHTML = `<i class="fas ${typeIcons[assetType]} me-1"></i> ${typeNames[assetType]}`;
        
        document.getElementById('mainIcon').innerHTML = `<i class="fas ${typeIcons[assetType]}"></i>`;
        document.getElementById('modelDisplay').innerText = asset.model || 'Unknown Model';
        document.getElementById('vendorDisplay').innerText = asset.vendor || 'Unknown Vendor';
        document.getElementById('snDisplay').innerText = asset.serial_number;
        
        if (asset.name) {
            document.getElementById('hostnameContainer').style.display = 'block';
            document.getElementById('hostnameDisplay').innerText = asset.name;
        }
        
        if (assetType === 'printer' && asset.ip_address) {
            const btnHtml = `<a href="http://${asset.ip_address}" target="_blank" class="btn btn-light rounded-pill px-4 fw-semibold border shadow-sm"><i class="fas fa-globe me-2"></i> Web UI</a>`;
            document.getElementById('headerActions').insertAdjacentHTML('afterbegin', btnHtml);
        }
        
        // Last Network Ping Color Logic
        const lastSeenEl = document.getElementById('lastSeenDisplay');
        lastSeenEl.innerText = formatDate(asset.last_seen_at);
        if (asset.last_seen_at) {
            const lastSeenDate = new Date(asset.last_seen_at);
            const diffDays = Math.ceil(Math.abs(new Date() - lastSeenDate) / (1000 * 60 * 60 * 24));
            
            lastSeenEl.classList.remove('secondary', 'bg-secondary', 'bg-success', 'bg-danger');
            lastSeenEl.style.backgroundColor = '';
            
            if (diffDays <= 14) {
                lastSeenEl.classList.add('success');
            } else if (diffDays < 28) {
                lastSeenEl.classList.add('warning');
            } else {
                lastSeenEl.classList.add('danger');
                lastSeenEl.innerHTML = `<i class="fas fa-exclamation-triangle me-1"></i> ${formatDate(asset.last_seen_at)}`;
            }
        }

        const isAvail = asset.status === 'Available';
        let statusColor = 'secondary';
        let statusIcon = 'fa-info-circle';
        
        if (asset.status === 'Available') {
            statusColor = 'success';
            statusIcon = 'fa-check-circle';
        } else if (asset.status === 'Assigned') {
            statusColor = 'primary';
            statusIcon = 'fa-user-lock';
        } else if (asset.status === 'Maintenance') {
            statusColor = 'warning text-dark';
            statusIcon = 'fa-tools text-dark';
        } else if (asset.status === 'Broken' || asset.status === 'Retired') {
            statusColor = 'danger';
            statusIcon = 'fa-times-circle';
        } else if (asset.status === 'Returned to Supplier') {
            statusColor = 'secondary';
            statusIcon = 'fa-truck-loading';
        }

        document.getElementById('statusIndicator').innerHTML = `
            <div class="dropdown d-inline-block">
                <div class="status-pill ${statusColor === 'warning text-dark' ? 'warning' : statusColor} cursor-pointer" 
                     data-bs-toggle="dropdown" aria-expanded="false" style="cursor: pointer; transition: opacity 0.2s;" onmouseover="this.style.opacity=0.8" onmouseout="this.style.opacity=1" title="Click to change status">
                    <i class="fas ${statusIcon} me-2"></i> ${asset.status || 'Unknown'} <i class="fas fa-chevron-down ms-2 small opacity-50"></i>
                </div>
                <ul class="dropdown-menu shadow-sm border-0" style="border-radius: 12px; font-size: 0.85rem; min-width: 180px;">
                    <li><h6 class="dropdown-header text-uppercase" style="font-size: 0.7rem; font-weight: 600; color: #94a3b8;">Change Status</h6></li>
                    <li><a class="dropdown-item py-2 d-flex align-items-center" href="#" onclick="confirmStatusChange(event, 'Available')"><i class="fas fa-check-circle text-success me-2" style="width: 16px;"></i> Available</a></li>
                    <li><a class="dropdown-item py-2 d-flex align-items-center" href="#" onclick="confirmStatusChange(event, 'Assigned')"><i class="fas fa-user-lock text-primary me-2" style="width: 16px;"></i> Assigned</a></li>
                    <li><a class="dropdown-item py-2 d-flex align-items-center" href="#" onclick="confirmStatusChange(event, 'Maintenance')"><i class="fas fa-tools text-warning me-2" style="width: 16px;"></i> Maintenance</a></li>
                    <li><a class="dropdown-item py-2 d-flex align-items-center" href="#" onclick="confirmStatusChange(event, 'Broken')"><i class="fas fa-times-circle text-danger me-2" style="width: 16px;"></i> Broken</a></li>
                    <li><a class="dropdown-item py-2 d-flex align-items-center" href="#" onclick="confirmStatusChange(event, 'Retired')"><i class="fas fa-ban text-danger me-2" style="width: 16px;"></i> Retired</a></li>
                    <li><a class="dropdown-item py-2 d-flex align-items-center" href="#" onclick="confirmStatusChange(event, 'Returned to Supplier')"><i class="fas fa-truck-loading text-secondary me-2" style="width: 16px;"></i> Returned to Supplier</a></li>
                </ul>
            </div>
        `;

        // 2. Assignee Widget
        const assigneeDiv = document.getElementById('assigneeWidget');
        if (asset.current_assignee) {
            assigneeDiv.innerHTML = `
                <div class="premium-card p-4">
                    <div class="text-label mb-3">Currently Deployed To</div>
                    <div class="d-flex align-items-center">
                        <div class="icon-soft icon-soft-primary" style="width: 48px; height: 48px; font-size: 1.2rem;">
                            <i class="fas fa-user"></i>
                        </div>
                        <div class="ms-3">
                            <h5 class="mb-0 fw-bold"><a href="/admin/users/${asset.current_assignee.id}" class="text-decoration-none text-dark">${asset.current_assignee.name}</a></h5>
                            ${asset.current_assignee.email ? `<small class="text-muted"><i class="fas fa-envelope me-1"></i>${asset.current_assignee.email}</small>` : ''}
                        </div>
                    </div>
                </div>
            `;
        } else if (isAvail) {
            assigneeDiv.innerHTML = `
                <div class="premium-card p-4">
                    <div class="d-flex align-items-center">
                        <div class="icon-soft icon-soft-success" style="width: 48px; height: 48px; font-size: 1.2rem;">
                            <i class="fas fa-box-open"></i>
                        </div>
                        <div class="ms-3">
                            <h5 class="mb-0 fw-bold text-success">In Stock</h5>
                            <p class="mb-0 text-muted small">Asset is stored and ready to be deployed.</p>
                        </div>
                    </div>
                </div>
            `;
        }

        // 2b. Connected Monitors Widget
        const monitorsDiv = document.getElementById('monitorsWidget');
        if (asset.connected_monitors && asset.connected_monitors.length > 0) {
            let monitorsHtml = `
                <div class="premium-card p-4">
                    <h6 class="fw-bold brand-font mb-3"><i class="fas fa-desktop text-success me-2"></i> Connected Monitors</h6>
                    <ul class="list-group list-group-flush bg-transparent">
            `;
            asset.connected_monitors.forEach(mon => {
                monitorsHtml += `
                    <li class="list-group-item bg-transparent px-0 border-light d-flex align-items-center">
                        <div class="icon-soft icon-soft-dark" style="width: 32px; height: 32px; font-size: 0.9rem;">
                            <i class="fas fa-desktop"></i>
                        </div>
                        <div class="ms-3">
                            <div class="fw-bold"><a href="/hardware/monitor/${mon.id}" class="text-decoration-none text-dark">${mon.model || 'Unknown Model'}</a></div>
                            <small class="text-muted">S/N: ${mon.serial_number} &bull; ${mon.vendor || 'Unknown'}</small>
                        </div>
                    </li>
                `;
            });
            monitorsHtml += `</ul></div>`;
            monitorsDiv.innerHTML = monitorsHtml;
        }

        // 2c. Connected Host PC Widget (For Monitors)
        if (assetType === 'monitor' && asset.connected_pc) {
            let pcHtml = `
                <div class="premium-card p-4 mt-4 border-start border-primary border-4">
                    <h6 class="fw-bold brand-font mb-3"><i class="fas fa-laptop-house text-primary me-2"></i> Connected Host PC</h6>
                    <ul class="list-group list-group-flush bg-transparent">
                        <li class="list-group-item bg-transparent px-0 border-0 d-flex align-items-center">
                            <div class="icon-soft icon-soft-primary" style="width: 32px; height: 32px; font-size: 0.9rem;">
                                <i class="fas fa-laptop"></i>
                            </div>
                            <div class="ms-3">
                                <div class="fw-bold"><a href="/hardware/pc/${asset.connected_pc.id}" class="text-decoration-none text-dark">${asset.connected_pc.model || 'Unknown Model'}</a></div>
                                <small class="text-muted">S/N: ${asset.connected_pc.serial_number} &bull; ${asset.connected_pc.vendor || 'Unknown'}</small>
                            </div>
                        </li>
                    </ul>
                </div>
            `;
            // Append to monitorsDiv since it's the same column location
            monitorsDiv.innerHTML += pcHtml;
        }

        // 3. Telemetry Micro-Widgets
        let telemetryHtml = '';
        const buildWidget = (icon, colorClass, label, value) => `
            <div class="col-sm-6 col-md-4">
                <div class="telemetry-item">
                    <div class="telemetry-icon icon-soft icon-soft-${colorClass}"><i class="fas ${icon}"></i></div>
                    <div class="overflow-hidden">
                        <div class="text-label">${label}</div>
                        <div class="text-value text-break" style="font-size: 0.9rem;">${value || '<span class="text-muted fw-normal">N/A</span>'}</div>
                    </div>
                </div>
            </div>
        `;

        if (assetType === 'pc') {
            telemetryHtml += buildWidget('fa-network-wired', 'info', 'IPv4', asset.ip_address);
            telemetryHtml += buildWidget('fa-wifi', 'dark', 'MAC', asset.mac_address);
            
            // OS
            const osVal = asset.windows_version ? `<i class="fab fa-windows text-primary me-1"></i>${asset.windows_version.split('(')[0].trim()}` : null;
            telemetryHtml += buildWidget('fa-desktop', 'primary', 'OS', osVal);
            
            // Intune
            const isEnrolled = asset.intune_status === 'Enrolled';
            const intuneVal = asset.intune_status ? `<span class="text-${isEnrolled ? 'success' : 'danger'}"><i class="fas fa-${isEnrolled ? 'cloud-check' : 'cloud-upload-alt'} me-1"></i>${asset.intune_status}</span>` : null;
            telemetryHtml += buildWidget('fa-cloud', isEnrolled ? 'success' : 'danger', 'MDM', intuneVal);

            // Antivirus
            const hasAV = asset.antivirus_status && !asset.antivirus_status.includes('None');
            const avVal = asset.antivirus_status ? `<span class="text-${hasAV ? 'success' : 'warning'}"><i class="fas fa-shield-alt me-1"></i>${asset.antivirus_status.split(' ')[0]}</span>` : null;
            telemetryHtml += buildWidget('fa-shield-virus', hasAV ? 'success' : 'warning', 'Antivirus', avVal);
            
            // RAM & Storage & Print
            telemetryHtml += buildWidget('fa-memory', 'secondary', 'RAM', asset.ram);
            telemetryHtml += buildWidget('fa-hdd', 'warning', 'Storage', asset.storage);
            telemetryHtml += buildWidget('fa-print', 'info', '30-Day Prints', `${asset.print_volume_30d} Pages`);
            
            // Network Location Placeholder
            if (asset.mac_address) {
                telemetryHtml += `
                <div class="col-sm-6 col-md-4">
                    <div class="telemetry-item">
                        <div class="telemetry-icon icon-soft icon-soft-info"><i class="fas fa-route"></i></div>
                        <div class="overflow-hidden">
                            <div class="text-label">Switch Port</div>
                            <div class="text-value text-break" style="font-size: 0.9rem;" id="netLocWidgetContent">
                                <i class="fas fa-circle-notch fa-spin text-info me-1"></i> Locating...
                            </div>
                        </div>
                    </div>
                </div>
                `;
            }

        } else if (assetType === 'phone' || assetType === 'phone_number') {
            if (asset.phone_number) {
                telemetryHtml += buildWidget('fa-hashtag', 'primary', 'Extension / Number', asset.phone_number);
            }
        } else if (assetType === 'printer') {
            const ipLink = asset.ip_address ? `<a href="http://${asset.ip_address}" target="_blank" class="text-decoration-none fw-bold text-info" title="Open Printer Web Interface">${asset.ip_address} <i class="fas fa-external-link-alt ms-1 small"></i></a>` : null;
            telemetryHtml += buildWidget('fa-network-wired', 'info', 'IPv4 (Web UI)', ipLink || asset.ip_address);
            telemetryHtml += buildWidget('fa-microchip', 'dark', 'MAC', asset.mac_address);
            
            if (asset.mac_address) {
                telemetryHtml += `
                <div class="col-sm-6 col-md-4">
                    <div class="telemetry-item">
                        <div class="telemetry-icon icon-soft icon-soft-info"><i class="fas fa-route"></i></div>
                        <div class="overflow-hidden">
                            <div class="text-label">Switch Port</div>
                            <div class="text-value text-break" style="font-size: 0.9rem;" id="netLocWidgetContent">
                                <i class="fas fa-circle-notch fa-spin text-info me-1"></i> Locating...
                            </div>
                        </div>
                    </div>
                </div>
                `;
            }
        }

        document.getElementById('telemetryRow').innerHTML = telemetryHtml;

        if (assetType === 'printer') {
            let printerHtml = '';
            
            // SNMP Telemetry
            if (asset.snmp) {
                const s = asset.snmp;
                
                let snmpStatusHtml = '';
                if (s.status === 'online' || s.status === 'idle' || s.status === 'printing') {
                    snmpStatusHtml = `<span class="badge bg-success bg-opacity-10 text-success border border-success border-opacity-50 px-3 py-2"><i class="fas fa-check-circle me-1"></i> SNMP Online</span>`;
                } else {
                    snmpStatusHtml = `<span class="badge bg-danger bg-opacity-10 text-danger border border-danger border-opacity-50 px-3 py-2"><i class="fas fa-exclamation-circle me-1"></i> ${s.status || 'Offline'}</span>`;
                }

                if (s.error_state) {
                    snmpStatusHtml += `<span class="badge bg-warning bg-opacity-10 text-dark border border-warning border-opacity-50 px-3 py-2 ms-2"><i class="fas fa-exclamation-triangle text-warning me-1"></i> ${s.error_state}</span>`;
                }
                
                printerHtml += `
                <div class="premium-card p-4 mb-4">
                    <div class="d-flex justify-content-between align-items-center mb-4 border-bottom border-light pb-3">
                        <div class="d-flex align-items-center">
                            <div class="icon-soft icon-soft-dark me-3" style="width: 40px; height: 40px;">
                                <i class="fas fa-tachometer-alt"></i>
                            </div>
                            <h5 class="mb-0 fw-bold brand-font text-dark">SNMP Telemetry</h5>
                        </div>
                        <div>${snmpStatusHtml}</div>
                    </div>
                    
                    <div class="row g-4">
                        <div class="col-md-6">
                            <div class="text-label mb-3">Consumables (Toner Levels)</div>
                `;
                
                const addToner = (color, level, hex) => {
                    if (level === null || level === undefined) return '';
                    return `
                        <div class="mb-3">
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <span style="font-size: 0.85rem; font-weight: 600; text-transform: capitalize;">${color}</span>
                                <span style="font-size: 0.85rem; font-weight: 600; color: ${hex};">${level}%</span>
                            </div>
                            <div class="progress" style="height: 8px; border-radius: 4px; background-color: #f1f5f9;">
                                <div class="progress-bar" role="progressbar" style="width: ${level}%; background-color: ${hex}; border-radius: 4px;" aria-valuenow="${level}" aria-valuemin="0" aria-valuemax="100"></div>
                            </div>
                        </div>
                    `;
                };

                let toners = '';
                toners += addToner('Black', s.toner_black, '#0f172a');
                toners += addToner('Cyan', s.toner_cyan, '#0ea5e9');
                toners += addToner('Magenta', s.toner_magenta, '#ec4899');
                toners += addToner('Yellow', s.toner_yellow, '#eab308');

                if (!toners) {
                    toners = `<div class="text-muted small"><i class="fas fa-info-circle me-1"></i> Toner data unavailable via SNMP.</div>`;
                }
                
                printerHtml += toners;
                
                printerHtml += `
                        </div>
                        <div class="col-md-6 border-start border-light ps-4">
                            <div class="text-label mb-3">Hardware Usage</div>
                            <div class="d-flex align-items-center mb-4">
                                <div class="icon-soft icon-soft-info" style="width: 48px; height: 48px; font-size: 1.2rem;">
                                    <i class="fas fa-copy"></i>
                                </div>
                                <div class="ms-3">
                                    <h3 class="mb-0 fw-bold text-dark">${s.total_page_counter !== null ? s.total_page_counter.toLocaleString() : '—'}</h3>
                                    <p class="mb-0 text-muted small">Total Lifetime Pages</p>
                                </div>
                            </div>
                            <div class="text-muted" style="font-size: 0.8rem;">
                                <i class="fas fa-sync-alt me-1"></i> Last Polled: ${s.last_seen ? formatDate(s.last_seen) : 'Never'}
                            </div>
                        </div>
                    </div>
                </div>
                `;
            }

            // Print Logs Table
            if (asset.print_logs && asset.print_logs.length > 0) {
                printerHtml += `
                <div class="premium-card p-4 mb-4">
                    <div class="d-flex justify-content-between align-items-center mb-4">
                        <div class="d-flex align-items-center">
                            <div class="icon-soft icon-soft-primary me-3" style="width: 40px; height: 40px;">
                                <i class="fas fa-history"></i>
                            </div>
                            <h5 class="mb-0 fw-bold brand-font text-dark">Recent Print Jobs</h5>
                        </div>
                        <span class="badge bg-primary rounded-pill px-3 py-2 shadow-sm">${asset.print_logs.length} Recent</span>
                    </div>
                    
                    <div class="elegant-table-container">
                        <table class="elegant-table">
                            <thead>
                                <tr>
                                    <th class="ps-4">Time</th>
                                    <th>User</th>
                                    <th>Document</th>
                                    <th>Pages</th>
                                    <th>Format</th>
                                    <th class="pe-4">Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${asset.print_logs.map(log => {
                                    let statusPill = '';
                                    if(log.status === 'printed') statusPill = '<span class="status-pill success">Printed</span>';
                                    else if(log.status === 'printing') statusPill = '<span class="status-pill warning">Printing</span>';
                                    else if(log.status === 'failed') statusPill = '<span class="status-pill danger">Failed</span>';
                                    else if(log.status === 'cancelled') statusPill = '<span class="status-pill danger">Cancelled</span>';
                                    else statusPill = '<span class="status-pill secondary">' + (log.status || 'Unknown') + '</span>';

                                    let fmtHtml = '';
                                    if (log.is_color === true) fmtHtml = '<span title="Color" style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#ef4444;"></span>';
                                    else if (log.is_color === false) fmtHtml = '<span title="Mono" style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#94a3b8;"></span>';

                                    return `
                                        <tr>
                                            <td class="ps-4 text-muted" style="font-size: 0.8rem;">${formatDate(log.submitted_at)}</td>
                                            <td class="fw-medium text-dark">${log.user}</td>
                                            <td><div style="max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${log.document_name || ''}">${log.document_name || 'Untitled'}</div></td>
                                            <td class="fw-semibold">${log.total_pages || '—'}</td>
                                            <td>${fmtHtml}</td>
                                            <td class="pe-4">${statusPill}</td>
                                        </tr>
                                    `;
                                }).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
                `;
            } else {
                printerHtml += `
                <div class="premium-card p-4 mb-4 text-center">
                    <i class="fas fa-inbox fa-3x text-muted opacity-25 mb-3 mt-2"></i>
                    <h6 class="text-muted">No recent print jobs found for this printer.</h6>
                </div>
                `;
            }

            document.getElementById('printerSpecificWidgets').innerHTML = printerHtml;
        }

        if ((assetType === 'pc' || assetType === 'printer') && asset.mac_address) {
            fetch(`/api/discovery/locate_mac/${encodeURIComponent(asset.mac_address)}`, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                }
            })
                .then(r => {
                    if (!r.ok) throw new Error('Network response was not ok');
                    return r.json();
                })
                .then(data => {
                    const contentDiv = document.getElementById('netLocWidgetContent');
                    if (data.found) {
                        contentDiv.innerHTML = `
                            <a href="/network/discovery" class="text-info text-decoration-none fw-bold" title="${data.switch_ip}">${data.switch_name}</a>
                            <span class="text-muted small ms-1">(${data.port_name})</span>
                        `;
                    } else {
                        contentDiv.innerHTML = `<span class="text-muted small">Not found on network</span>`;
                    }
                })
                .catch(e => {
                    document.getElementById('netLocWidgetContent').innerHTML = `<span class="text-danger small">Scan Failed</span>`;
                });
        }

        // 4. Software Table
        if (assetType === 'pc') {
            document.getElementById('softwareCard').classList.remove('d-none');
            const swBody = document.getElementById('softwareTableBody');
            
            if (asset.software && asset.software.length > 0) {
                document.getElementById('softwareCount').innerText = `${asset.software.length} Total Apps`;
                
                asset.software.sort((a, b) => {
                    if (a.is_active === b.is_active) return a.name.localeCompare(b.name);
                    return a.is_active ? -1 : 1;
                });

                swBody.innerHTML = asset.software.map(sw => `
                    <tr style="transition: all 0.2s;" class="${!sw.is_active ? 'opacity-50 bg-light' : ''}">
                        <td class="ps-4 fw-medium text-dark"><i class="fas fa-cube text-muted me-2 opacity-50"></i>${sw.name}</td>
                        <td><span class="badge bg-light text-dark border">${sw.version || 'Unknown'}</span></td>
                        <td>
                            ${sw.is_active ? 
                                '<span class="badge bg-success bg-opacity-10 text-success border border-success border-opacity-50"><i class="fas fa-check me-1"></i> Active</span>' : 
                                '<span class="badge bg-danger bg-opacity-10 text-danger border border-danger border-opacity-50"><i class="fas fa-times me-1"></i> Removed</span>'}
                        </td>
                        <td><small class="text-muted">${formatDate(sw.installed_date)}</small></td>
                        <td class="pe-4"><small class="text-danger">${sw.is_active ? '-' : formatDate(sw.removed_date)}</small></td>
                    </tr>
                `).join('');

                // Search Functionality
                document.getElementById('softwareSearch').addEventListener('input', function(e) {
                    const term = e.target.value.toLowerCase();
                    const rows = swBody.querySelectorAll('tr');
                    let visibleCount = 0;
                    rows.forEach(row => {
                        const appName = row.cells[0]?.textContent?.toLowerCase() || '';
                        if (appName.includes(term)) {
                            row.style.display = '';
                            visibleCount++;
                        } else {
                            row.style.display = 'none';
                        }
                    });
                    document.getElementById('softwareCount').innerText = `${visibleCount} Apps`;
                });
            } else {
                swBody.innerHTML = `<tr><td colspan="5" class="text-center py-5 text-muted"><i class="fas fa-ghost fa-2x mb-3 opacity-50"></i><br>No software inventory available. Pending remote discovery.</td></tr>`;
            }

            // 4b. Printers Table
            document.getElementById('printersCard').classList.remove('d-none');
            const prBody = document.getElementById('printerTableBody');
            
            if (asset.printers && asset.printers.length > 0) {
                document.getElementById('printerCount').innerText = `${asset.printers.length} Printers`;
                
                prBody.innerHTML = asset.printers.map(pr => `
                    <tr>
                        <td class="ps-4 fw-medium text-dark">
                            <i class="fas fa-print text-muted me-2 ${pr.is_default ? 'text-success' : 'opacity-50'}"></i>
                            ${pr.name}
                        </td>
                        <td><span class="text-muted small">${pr.driver_name || 'Generic'}</span></td>
                        <td><code>${pr.port_name || '-'}</code></td>
                        <td>${pr.is_network ? '<span class="badge bg-info">Network</span>' : '<span class="badge bg-secondary">Local</span>'}</td>
                        <td class="pe-4">
                            ${pr.is_default ? '<span class="badge bg-success bg-opacity-10 text-success border border-success"><i class="fas fa-star me-1"></i> Default</span>' : ''}
                        </td>
                    </tr>
                `).join('');
            } else {
                prBody.innerHTML = `<tr><td colspan="5" class="text-center py-5 text-muted"><i class="fas fa-print fa-2x mb-3 opacity-50"></i><br>No printers found on this device.</td></tr>`;
            }
        }

    } catch(e) {
        document.getElementById('assetTitle').innerHTML = `<span class="text-danger">Critical Failure</span>`;
        document.getElementById('dashboardContent').innerHTML = `
            <div class="col-12 animate-fade-in">
                <div class="alert alert-danger shadow-sm border-0 rounded-4 p-4 d-flex align-items-center">
                    <i class="fas fa-exclamation-triangle fa-3x me-4"></i>
                    <div>
                        <h4 class="fw-bold">Unable to load asset profile</h4>
                        <p class="mb-0">The system encountered an error: ${e.message}</p>
                    </div>
                </div>
            </div>`;
    }

    // 5. Timeline History
    try {
        const res = await historyPromise;
        const data = await res.json();
        const timeline = document.getElementById('historyTimeline');

        if (data.length === 0) {
            timeline.innerHTML = `<div class="text-muted text-center py-4"><i class="fas fa-info-circle me-2"></i> No chronological data recorded.</div>`;
            return;
        }

        timeline.innerHTML = data.map((entry, index) => {
            const isCurrent = index === 0 && !entry.returned_date;
            return `
                <div class="timeline-node ${isCurrent ? 'current' : ''}">
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <h6 class="fw-bold mb-0 text-dark" style="font-size: 0.95rem;">
                            Assigned to ${entry.new_user_name || 'Unknown'}
                            ${isCurrent ? '<span class="status-pill success ms-2" style="font-size:0.65rem; padding:4px 10px;">Current</span>' : ''}
                        </h6>
                        <span class="text-muted small fw-semibold"><i class="fas fa-calendar-alt me-1"></i> ${formatDate(entry.assigned_date)}</span>
                    </div>
                    <div class="text-muted mb-2" style="font-size: 0.85rem;">
                        <i class="fas fa-exchange-alt me-1"></i> Transferred from <strong>${entry.previous_user_name || 'Inventory Stock'}</strong>
                    </div>
                    ${entry.notes ? `<div class="bg-light p-2 rounded text-muted border border-light mt-2" style="font-size: 0.85rem;"><i class="fas fa-comment text-warning me-1"></i> ${entry.notes}</div>` : ''}
                    ${entry.returned_date ? `<div class="text-danger mt-2 fw-medium" style="font-size: 0.85rem;"><i class="fas fa-undo-alt me-1"></i> Returned to stock on ${formatDate(entry.returned_date)}</div>` : ''}
                </div>
            `;
        }).join('');
    } catch(e) {
        document.getElementById('historyTimeline').innerHTML = `<div class="text-danger">Failed to load history.</div>`;
    }
});

// Status Update Logic
let pendingStatusChange = null;
let statusModalInstance = null;

function confirmStatusChange(event, newStatus) {
    event.preventDefault();
    pendingStatusChange = newStatus;
    document.getElementById('modalTargetStatus').innerText = newStatus;
    
    if (!statusModalInstance) {
        statusModalInstance = new bootstrap.Modal(document.getElementById('statusConfirmModal'));
    }
    statusModalInstance.show();
}

document.getElementById('confirmStatusBtn').addEventListener('click', async function() {
    if (!pendingStatusChange) return;
    
    const pathParts = window.location.pathname.split('/');
    const assetType = pathParts[2];
    const assetId = pathParts[3];
    
    const btn = this;
    const originalText = btn.innerHTML;
    btn.innerHTML = `<i class="fas fa-circle-notch fa-spin me-2"></i> Updating...`;
    btn.disabled = true;
    
    try {
        const res = await fetch(`/api/hardware/stock/${assetType}/${assetId}/status`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: pendingStatusChange })
        });
        
        if (!res.ok) {
            const err = await res.json();
            alert('Error updating status: ' + (err.detail || 'Unknown error'));
            btn.innerHTML = originalText;
            btn.disabled = false;
            return;
        }
        
        location.reload();
    } catch (err) {
        alert('Network error updating status.');
        console.error(err);
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
});
