
    async function loadPrinters() {
        const token = localStorage.getItem('access_token');
        const res = await fetch('/api/print/printers/list', { headers: { 'Authorization': `Bearer ${token}` }});
        const printers = await res.json();
        const tbody = document.getElementById('printerBody');

        if (!printers.length) {
            tbody.innerHTML = '<tr><td colspan="10" class="text-center py-5 text-muted"><i class="fas fa-print d-block mb-2" style="font-size:2rem"></i>No printers registered yet.<br><small>Printers will appear once an agent discovers them.</small></td></tr>';
            return;
        }

        tbody.innerHTML = printers.map(p => {
            const tonerBars = renderToner(p);
            return `<tr>
                <td class="fw-medium">${p.name}</td>
                <td>${p.model || '—'}</td>
                <td><code class="small">${p.ip_address || '—'}</code></td>
                <td>${p.location || '—'}</td>
                <td>${p.department || '—'}</td>
                <td><span class="pp-status pp-status-${p.status||'unknown'}">${p.status||'unknown'}</span></td>
                <td class="text-end fw-semibold">${p.total_page_counter != null ? p.total_page_counter.toLocaleString() : '—'}</td>
                <td>${tonerBars}</td>
                <td class="text-nowrap small">${p.last_seen ? new Date(p.last_seen).toLocaleDateString() : '—'}</td>
                <td><button class="btn btn-sm btn-outline-primary py-0 px-2" onclick="openEdit(${p.id},'${esc(p.name)}','${esc(p.location)}','${esc(p.department)}','${esc(p.model)}','${esc(p.ip_address)}')"><i class="fas fa-edit"></i></button></td>
            </tr>`;
        }).join('');
    }

    function esc(s) { return (s||'').replace(/'/g, "\\'").replace(/"/g, '&quot;'); }

    function renderToner(p) {
        if (p.toner_black == null) return '<span class="text-muted small">N/A</span>';
        const bars = [
            { label: 'K', val: p.toner_black, color: '#1e293b' },
            { label: 'C', val: p.toner_cyan, color: '#06b6d4' },
            { label: 'M', val: p.toner_magenta, color: '#ec4899' },
            { label: 'Y', val: p.toner_yellow, color: '#eab308' },
        ];
        return bars.filter(b => b.val != null).map(b =>
            `<div class="d-flex align-items-center gap-1 mb-1"><span class="pp-toner-label">${b.label}</span><div class="pp-toner-bar flex-grow-1"><div class="pp-toner-fill" style="width:${b.val}%;background:${b.color}"></div></div><span class="pp-toner-label">${b.val}%</span></div>`
        ).join('');
    }

    function openEdit(id, name, loc, dept, model, ip) {
        document.getElementById('editId').value = id;
        document.getElementById('editName').value = name;
        document.getElementById('editLocation').value = loc;
        document.getElementById('editDept').value = dept;
        document.getElementById('editModel').value = model;
        document.getElementById('editIP').value = ip;
        new bootstrap.Modal(document.getElementById('editModal')).show();
    }

    document.getElementById('btnSaveEdit').addEventListener('click', async () => {
        const token = localStorage.getItem('access_token');
        const id = document.getElementById('editId').value;
        const body = {
            name: document.getElementById('editName').value,
            location: document.getElementById('editLocation').value,
            department: document.getElementById('editDept').value,
            model: document.getElementById('editModel').value,
            ip_address: document.getElementById('editIP').value,
        };
        await fetch(`/api/print/printers/${id}`, {
            method: 'PATCH', headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        bootstrap.Modal.getInstance(document.getElementById('editModal')).hide();
        loadPrinters();
    });

    loadPrinters();
