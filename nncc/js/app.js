/**
 * 🌀 NeXuS Network Command Center v2.0
 * Unified control plane for anonymity networks
 */

// ── Config ────────────────────────────────────────────────────────────────
const API_BASE    = '/nncc/api';    // proxied through bifrost-bridge → Python FastAPI :8801
const GATEWAY_IP  = '127.0.0.1';   // local services — no hardcoded gateway subnet

// ── Tab switching ─────────────────────────────────────────────────────────
function showTab(name) {
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    const panel = document.getElementById('tab-' + name);
    const tab   = document.querySelector(`.nav-tab[data-tab="${name}"]`);
    if (panel) panel.classList.add('active');
    if (tab)   tab.classList.add('active');
}

// ── Node info auto-fill ───────────────────────────────────────────────────
function populateNodeInfo() {
    const el = document.getElementById('node-hostname');
    if (el) el.textContent = window.location.hostname;
    const gip = document.getElementById('gateway-ip');
    if (gip) gip.textContent = GATEWAY_IP;
    const dip = document.getElementById('device-ip');
    // best-effort local IP from RTCPeerConnection (optional, no server needed)
    try {
        const pc = new RTCPeerConnection({iceServers:[]});
        pc.createDataChannel('');
        pc.createOffer().then(o => pc.setLocalDescription(o));
        pc.onicecandidate = e => {
            if (!e || !e.candidate) return;
            const m = e.candidate.candidate.match(/(\d+\.\d+\.\d+\.\d+)/);
            if (m && dip && !m[1].startsWith('127.')) { dip.textContent = m[1]; pc.close(); }
        };
    } catch(_) { if (dip) dip.textContent = '—'; }
}

// ── Quick Actions ─────────────────────────────────────────────────────────
async function startAll()     { try { await apiCall('/services/start-all', {method:'POST'}); showNotification('Services','Starting all…','info'); setTimeout(loadServices,2000); } catch(e){} }
async function stopAll()      { try { await apiCall('/services/stop-all',  {method:'POST'}); showNotification('Services','Stopping all…','info'); setTimeout(loadServices,2000); } catch(e){} }
async function restartAll()   { try { await apiCall('/services/restart-all',{method:'POST'}); showNotification('Services','Restarting all…','info'); setTimeout(loadServices,3000); } catch(e){} }
async function startGateway() { try { await apiCall('/gateway/start',      {method:'POST'}); showNotification('Gateway','Starting Whonix Gateway…','info'); } catch(e){} }
async function runBackup()    { try { await apiCall('/backup',              {method:'POST'}); showNotification('Backup','Config backup started','success'); } catch(e){} }

// ── Live activity log ─────────────────────────────────────────────────────
function logActivity(msg, type='info') {
    const el = document.getElementById('live-activity');
    if (!el) return;
    const ts  = new Date().toLocaleTimeString('en',{hour12:false});
    const div = document.createElement('div');
    div.className = 'act-line';
    div.innerHTML = `<span class="act-time">${ts}</span><span class="act-${type}">${msg}</span>`;
    el.prepend(div);
    while (el.children.length > 50) el.removeChild(el.lastChild);
}

// Global state
const state = {
    networks: [],
    bypassRules: [],
    trafficStats: null,
    ws: null,
    connected: false,
    lastUpdate: null
};

// ============================================
// INITIALIZATION
// ============================================

document.addEventListener('DOMContentLoaded', async () => {
    console.log('🌀 NeXuS NCC v2.0 initializing...');
    populateNodeInfo();
    logActivity('NeXuS NCC initialized', 'success');

    // Initial data load
    await Promise.all([
        loadNetworks(),
        loadBypassRules(),
        loadTrafficStats(),
        updateTorPanel(),
        loadServices(),
        loadHosting(),
        runDoctor(),
        updateLogs(),
        runNetworkMapChecks(),
        updateOpenSnitch()
    ]);

    // Setup WebSocket for live updates
    setupWebSocket();

    // Setup event listeners
    setupEventListeners();

    // Start periodic refresh
    setInterval(refreshData, 10000);
    setInterval(updateTorPanel, 5000);
    setInterval(updateLogs, 2000);
    setInterval(runNetworkMapChecks, 30000);
    setInterval(updateOpenSnitch, 5000);

    console.log('🚀 NeXuS Command Center ready!');
});

// ============================================
// API FUNCTIONS
// ============================================

async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error(`API call failed: ${endpoint}`, error);
        showNotification('API Error', error.message, 'error');
        throw error;
    }
}

// ============================================
// NETWORK FUNCTIONS
// ============================================

async function loadNetworks() {
    try {
        state.networks = await apiCall('/networks');
        renderNetworkTable();
    } catch (error) {
        document.getElementById('network-table-body').innerHTML = `
            <tr><td colspan="5" class="loading">Failed to load networks</td></tr>
        `;
    }
}

function renderNetworkTable() {
    const tbody = document.getElementById('network-table-body');
    if (!tbody) return;

    tbody.innerHTML = state.networks.map(network => `
        <tr data-network-id="${network.id}">
            <td>
                <span class="network-name">
                    <span class="network-icon">${network.icon}</span>
                    <span>${network.name}</span>
                    ${network.containers.length > 0 ?
                        `<small>(${network.containers.filter(c => c.running).length}/${network.containers.length})</small>` :
                        ''}
                </span>
            </td>
            <td>
                <span class="status-badge status-${network.status.toLowerCase()}">
                    ${getStatusIcon(network.status)} ${network.status.toUpperCase()}
                </span>
            </td>
            <td>
                <span class="latency ${getLatencyClass(network.latency_ms)}">
                    ${network.latency_ms ? `${Math.round(network.latency_ms)}ms` : '—'}
                </span>
            </td>
            <td>
                <span class="traffic">
                    ${formatBytes(network.traffic_bytes_in + network.traffic_bytes_out)}/s
                </span>
            </td>
            <td>
                <div class="action-buttons">
                    ${network.containers.length > 0 ? `
                        <button class="btn-icon" data-tooltip="Stop" onclick="networkAction('${network.id}', 'stop')">
                            ⏸️
                        </button>
                        <button class="btn-icon" data-tooltip="Restart" onclick="networkAction('${network.id}', 'restart')">
                            🔄
                        </button>
                    ` : ''}
                    <button class="btn-icon" data-tooltip="Configure" onclick="showNetworkConfig('${network.id}')">
                        ⚙️
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

async function networkAction(networkId, action) {
    const btn = event.target.closest('.btn-icon');
    if (btn) btn.disabled = true;

    try {
        const result = await apiCall(`/networks/${networkId}/${action}`, {
            method: 'POST'
        });

        showNotification(
            `${action.charAt(0).toUpperCase() + action.slice(1)} Network`,
            result.message,
            result.success ? 'success' : 'error'
        );

        // Refresh network data
        await loadNetworks();
    } catch (error) {
        showNotification('Action Failed', error.message, 'error');
    } finally {
        if (btn) btn.disabled = false;
    }
}

function showNetworkConfig(networkId) {
    const network = state.networks.find(n => n.id === networkId);
    if (!network) return;

    // Simple config modal (could be expanded)
    alert(`Configure ${network.name}\n\nNetwork ID: ${networkId}\nStatus: ${network.status}\nContainers: ${network.containers.length}`);
}

// ============================================
// BYPASS RULES FUNCTIONS
// ============================================

async function loadBypassRules() {
    try {
        state.bypassRules = await apiCall('/routing/bypass');
        renderBypassRules();
    } catch (error) {
        document.getElementById('bypass-rules-list').innerHTML = `
            <li class="loading">Failed to load rules</li>
        `;
    }
}

function renderBypassRules() {
    const list = document.getElementById('bypass-rules-list');
    if (!list) return;

    list.innerHTML = state.bypassRules.map(rule => `
        <li class="bypass-rule" data-rule-id="${rule.id}">
            <div class="rule-pattern">
                <span class="rule-type">${rule.type}</span>
                <span>${rule.pattern}</span>
            </div>
            <div class="rule-actions">
                <input type="checkbox"
                       class="rule-toggle"
                       ${rule.enabled ? 'checked' : ''}
                       onchange="toggleRule(${rule.id})">
                <button class="btn-icon btn-danger"
                        data-tooltip="Delete"
                        onclick="deleteRule(${rule.id})">
                    🗑️
                </button>
            </div>
        </li>
    `).join('');
}

async function toggleRule(ruleId) {
    try {
        await apiCall(`/routing/bypass/${ruleId}/toggle`, {
            method: 'PATCH'
        });
        await loadBypassRules();
    } catch (error) {
        await loadBypassRules(); // Revert on error
    }
}

async function deleteRule(ruleId) {
    if (!confirm('Delete this bypass rule?')) return;

    try {
        await apiCall(`/routing/bypass/${ruleId}`, {
            method: 'DELETE'
        });
        showNotification('Rule Deleted', 'Bypass rule removed', 'success');
        await loadBypassRules();
    } catch (error) {
        showNotification('Delete Failed', error.message, 'error');
    }
}

async function addBypassRule() {
    const patternInput = document.getElementById('new-rule-pattern');
    const typeSelect = document.getElementById('new-rule-type');

    const pattern = patternInput.value.trim();
    const type = typeSelect.value;

    if (!pattern) {
        showNotification('Invalid Input', 'Please enter a pattern', 'error');
        return;
    }

    try {
        await apiCall('/routing/bypass', {
            method: 'POST',
            body: JSON.stringify({
                pattern,
                type,
                enabled: true
            })
        });

        patternInput.value = '';
        showNotification('Rule Added', `Bypass rule for ${pattern} created`, 'success');
        await loadBypassRules();
    } catch (error) {
        showNotification('Add Failed', error.message, 'error');
    }
}

// ============================================
// TRAFFIC FUNCTIONS
// ============================================

async function loadTrafficStats() {
    try {
        state.trafficStats = await apiCall('/traffic/stats');
        renderTrafficStats();
    } catch (error) {
        console.error('Failed to load traffic stats', error);
    }
}

function renderTrafficStats() {
    if (!state.trafficStats) return;

    // Update stat cards
    const stats = state.trafficStats;

    const bytesIn = document.getElementById('stat-bytes-in');
    const bytesOut = document.getElementById('stat-bytes-out');
    const connections = document.getElementById('stat-connections');
    const uptime = document.getElementById('stat-uptime');

    if (bytesIn) bytesIn.textContent = formatBytes(stats.total_bytes_in);
    if (bytesOut) bytesOut.textContent = formatBytes(stats.total_bytes_out);
    if (connections) connections.textContent = stats.total_connections;
    if (uptime) uptime.textContent = formatUptime(stats.uptime_seconds);
}

// ============================================
// WEBSOCKET
// ============================================

function setupWebSocket() {
    const wsUrl = `wss://${window.location.host}/nncc/api/traffic/ws`;
    try {
        state.ws = new WebSocket(wsUrl);

        state.ws.onopen = () => {
            console.log('WebSocket connected');
            state.connected = true;
            updateConnectionStatus(true);
        };

        state.ws.onclose = () => {
            console.log('WebSocket disconnected');
            state.connected = false;
            updateConnectionStatus(false);

            // Reconnect after 5 seconds
            setTimeout(setupWebSocket, 5000);
        };

        state.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        state.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleWebSocketMessage(data);
            } catch (e) {
                console.error('Failed to parse WebSocket message', e);
            }
        };
    } catch (error) {
        console.error('Failed to setup WebSocket', error);
        setTimeout(setupWebSocket, 5000);
    }
}

function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'initial':
        case 'traffic_update':
            state.trafficStats = data.stats;
            renderTrafficStats();
            state.lastUpdate = new Date();
            break;

        case 'heartbeat':
            // Keep alive
            break;

        default:
            console.log('Unknown WebSocket message:', data);
    }
}

function updateConnectionStatus(connected) {
    const indicator = document.getElementById('connection-status');
    if (indicator) {
        indicator.className = connected ? 'status-indicator connected' : 'status-indicator disconnected';
        indicator.title = connected ? 'Connected' : 'Disconnected';
    }
}

// ============================================
// EVENT LISTENERS
// ============================================

function setupEventListeners() {
    // Add rule button
    const addRuleBtn = document.getElementById('add-rule-btn');
    if (addRuleBtn) {
        addRuleBtn.addEventListener('click', addBypassRule);
    }

    // Enter key on rule input
    const ruleInput = document.getElementById('new-rule-pattern');
    if (ruleInput) {
        ruleInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') addBypassRule();
        });
    }

    // Refresh button
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', refreshData);
    }

    // Health check button
    const healthBtn = document.getElementById('health-check-btn');
    if (healthBtn) {
        healthBtn.addEventListener('click', triggerHealthCheck);
    }
}

async function refreshData() {
    console.log('Refreshing data...');
    await Promise.all([
        loadNetworks(),
        loadBypassRules(),
        loadTrafficStats()
    ]);
}

async function triggerHealthCheck() {
    try {
        const result = await apiCall('/health/check', { method: 'POST' });
        showNotification('Health Check', 'All networks checked', 'success');
        await loadNetworks();
    } catch (error) {
        showNotification('Health Check Failed', error.message, 'error');
    }
}

// ============================================
// UTILITY FUNCTIONS
// ============================================

function getStatusIcon(status) {
    switch (status.toLowerCase()) {
        case 'up': return '✅';
        case 'down': return '❌';
        case 'degraded': return '⚠️';
        default: return '❓';
    }
}

function getLatencyClass(latency) {
    if (!latency) return '';
    if (latency < 200) return 'latency-good';
    if (latency < 500) return 'latency-medium';
    return 'latency-bad';
}

function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

function formatUptime(seconds) {
    if (!seconds) return '—';
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const mins = Math.floor((seconds % 3600) / 60);

    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${mins}m`;
    return `${mins}m`;
}

function showNotification(title, message, type = 'info') {
    // Simple notification - could use a toast library
    console.log(`[${type.toUpperCase()}] ${title}: ${message}`);

    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <strong>${title}</strong>
        <p>${message}</p>
    `;

    // Add styles
    Object.assign(toast.style, {
        position: 'fixed',
        bottom: '20px',
        right: '20px',
        padding: '12px 20px',
        background: type === 'error' ? '#f85149' : type === 'success' ? '#3fb950' : '#58a6ff',
        color: 'white',
        borderRadius: '8px',
        boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
        zIndex: '1000',
        animation: 'slideIn 0.3s ease'
    });

    document.body.appendChild(toast);

    // Remove after 3 seconds
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Add animation styles
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);

// ============================================
// DARKNET & FREEDOM NODE FUNCTIONS
// ============================================

async function applyJurisdiction() {
const policy = document.getElementById('jurisdiction-select').value;
try {
    await apiCall('/jurisdiction', {
        method: 'POST',
        body: JSON.stringify({ policy })
    });
    document.getElementById('policy-status').innerText = `Policy Applied: ${policy}`;
    showNotification('Jurisdiction', `Policy ${policy} applied`, 'success');
} catch (e) {
    document.getElementById('policy-status').innerText = 'Failed to apply policy';
}
}

async function updateTorPanel() {
try {
    const d = await apiCall('/tor/info');
    const errEl = document.getElementById('tor-error');
    if (!errEl) return;
    if (d.Error) {
        errEl.style.display = 'block';
        errEl.textContent = '⚠ ' + d.Error;
        document.getElementById('tor-exit-ip').textContent = '—';
        document.getElementById('circuits-list').innerHTML =
            '<tr><td colspan="4" style="text-align:center;color:var(--text-muted);">control port unavailable</td></tr>';
        return;
    }
    errEl.style.display = 'none';
    document.getElementById('tor-exit-ip').textContent = d.ExitIP || 'unknown';
    const circuits = d.Circuits || [];
    if (circuits.length === 0) {
        document.getElementById('circuits-list').innerHTML =
            '<tr><td colspan="4" style="text-align:center;color:var(--text-muted);">no circuits yet</td></tr>';
        return;
    }
    document.getElementById('circuits-list').innerHTML = circuits.map(c => `
        <tr>
            <td style="color:var(--text-muted);">${c.ID}</td>
            <td><span style="color:${getCircuitColor(c.Status)};font-weight:bold;">${c.Status}</span></td>
            <td style="font-size:0.8rem;">${(c.Path && c.Path.length) ? c.Path.join(' → ') : '—'}</td>
            <td style="color:var(--text-secondary);font-size:0.8rem;">${(c.Purpose || '').replace('PURPOSE=','').toLowerCase()}</td>
        </tr>
    `).join('');
} catch (e) { console.error('Tor info failed', e); }
}

function getCircuitColor(status) {
switch(status) {
    case 'BUILT': return 'var(--accent-success)';
    case 'LAUNCHED': return 'var(--accent-warning)';
    case 'FAILED': return 'var(--accent-danger)';
    default: return 'var(--text-muted)';
}
}

async function requestNewIdentity() {
const btn = document.getElementById('newnym-btn');
btn.disabled = true;
try {
    await apiCall('/tor/newnym', {method:'POST'});
    showNotification('Tor', 'New identity requested', 'success');
    setTimeout(updateTorPanel, 1500);
} catch (e) {
    showNotification('Tor', 'Failed to request new identity', 'error');
} finally {
    btn.disabled = false;
}
}

async function loadServices() {
try {
    const svcs = await apiCall('/services');
    const list = document.getElementById('services-list');
    if (!list) return;
    list.innerHTML = svcs.map(s => `
        <tr>
            <td><strong>${s.name}</strong></td>
            <td><span class="status-badge status-${s.status.toLowerCase()}">${s.status}</span></td>
            <td>${s.port || '-'}</td>
            <td>${s.network}</td>
            <td><button class="btn btn-secondary btn-sm" onclick="toggleService('${s.id}')">${s.status === 'RUNNING' ? 'STOP' : 'START'}</button></td>
        </tr>
    `).join('');
} catch (e) { console.error('Services load failed', e); }
}

async function toggleService(id) {
try {
    await apiCall('/services/toggle', {
        method: 'POST',
        body: JSON.stringify({ id })
    });
    loadServices();
} catch (e) { showNotification('Error', 'Toggle failed', 'error'); }
}

async function loadHosting() {
try {
    const hosting = await apiCall('/hosting');
    const list = document.getElementById('hosting-list');
    if (!list) return;
    list.innerHTML = hosting.map(h => `
        <tr>
            <td><strong>${h.name}</strong></td>
            <td>${h.network.toUpperCase()}</td>
            <td>${h.local_port}</td>
            <td style="font-family:monospace; font-size:0.8rem; color:var(--accent-primary)">${h.dark_address || 'pending...'}</td>
            <td><button class="btn btn-danger btn-sm" onclick="hideService('${h.name}', '${h.network}')">HIDE</button></td>
        </tr>
    `).join('');
} catch (e) { console.error('Hosting load failed', e); }
}

async function exposeService() {
const name = document.getElementById('host-name').value;
const network = document.getElementById('host-net').value;
const port = parseInt(document.getElementById('host-port').value);
if (!name || !port) return;
try {
    await apiCall('/hosting/expose', {
        method: 'POST',
        body: JSON.stringify({ name, network, port })
    });
    document.getElementById('host-name').value = '';
    loadHosting();
} catch (e) { showNotification('Error', 'Expose failed', 'error'); }
}

async function hideService(name, network) {
try {
    await apiCall('/hosting/hide', {
        method: 'POST',
        body: JSON.stringify({ name, network })
    });
    loadHosting();
} catch (e) { showNotification('Error', 'Hide failed', 'error'); }
}

async function runDoctor() {
try {
    const results = await apiCall('/doctor');
    const resEl = document.getElementById('doctor-results');
    if (!resEl) return;
    resEl.innerHTML = results.map(r => `
        <div style="margin-bottom: 5px;">
            <span style="color: ${r.Pass ? 'var(--accent-success)' : 'var(--accent-danger)'}">${r.Pass ? '●' : '○'}</span>
            ${r.Name}: <small style="color: var(--text-secondary)">${r.Detail}</small>
        </div>
    `).join('');
} catch (e) { console.error('Doctor scan failed', e); }
}

async function updateLogs() {
try {
    const logs = await apiCall('/logs');
    const logDiv = document.getElementById('logs');
    const follow = document.getElementById('log-follow').checked;
    const filter = (document.getElementById('log-filter').value || '').toLowerCase();
    const visible = filter ? logs.filter(l =>
        l.Service.toLowerCase().includes(filter) ||
        l.Message.toLowerCase().includes(filter)) : logs;
    document.getElementById('log-count').textContent = `(${visible.length}/${logs.length})`;
    logDiv.innerHTML = visible.slice(-100).map(l => {
        const ts = new Date(l.Timestamp).toLocaleTimeString('en', {hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit'});
        return `<div class="log-entry"><span class="log-ts">${ts}</span><span class="log-svc log-svc-${l.Service.toUpperCase()}">${l.Service}</span><span class="log-msg">${l.Message}</span></div>`;
    }).join('');
    if (follow) logDiv.scrollTop = logDiv.scrollHeight;
} catch (e) { console.error('Logs failed', e); }
}

function clearLogView() {
document.getElementById('logs').innerHTML = '';
}

function copy(text) {
navigator.clipboard.writeText(text);
showNotification('Copied', text, 'success');
}

async function checkServiceStatus(url, dotId, statusId) {
const dot = document.getElementById(dotId);
const st = document.getElementById(statusId);
if (!dot || !st) return;
try {
    await fetch(url, {mode:'no-cors', signal: AbortSignal.timeout(3000)});
    dot.className = 'status-dot dot-green';
    st.textContent = 'online';
} catch(e) {
    dot.className = 'status-dot dot-red';
    st.textContent = 'offline';
}
}

async function runNetworkMapChecks() {
    checkServiceStatus(`http://${GATEWAY_IP}:9050`,          'dot-tor',     'status-tor');
    checkServiceStatus(`http://${GATEWAY_IP}:4444`,          'dot-i2p',     'status-i2p');
    checkServiceStatus(`http://${GATEWAY_IP}:8118`,          'dot-privoxy', 'status-privoxy');
    checkServiceStatus(`http://${GATEWAY_IP}:5001/api/v0/id`,'dot-ipfs',    'status-ipfs');
    checkServiceStatus(`http://${GATEWAY_IP}:9002`,          'dot-ygg',     'status-ygg');
    checkServiceStatus(`http://${GATEWAY_IP}:8404/stats`,    'dot-haproxy', 'status-haproxy');
}

async function updateOpenSnitch() {
    try {
        const rules = await fetch('http://127.0.0.1:8081/api/rules', {signal: AbortSignal.timeout(2000)});
        if (rules.ok) {
            const data = await rules.json();
            document.getElementById('opensnitch-status-badge').className = 'status-badge status-up';
            document.getElementById('opensnitch-status-badge').textContent = 'RUNNING';
            document.getElementById('opensnitch-toggle-btn').textContent = 'Stop';
            document.getElementById('opensnitch-controls').style.display = 'block';
            document.getElementById('opensnitch-placeholder').style.display = 'none';
            document.getElementById('opensnitch-rules-count').textContent = data.length;
            loadOpenSnitchHits();
        } else {
            throw new Error('API down');
        }
    } catch (e) {
        document.getElementById('opensnitch-status-badge').className = 'status-badge status-down';
        document.getElementById('opensnitch-status-badge').textContent = 'STOPPED';
        document.getElementById('opensnitch-toggle-btn').textContent = 'Start';
        document.getElementById('opensnitch-controls').style.display = 'none';
        document.getElementById('opensnitch-placeholder').style.display = 'block';
    }
}

async function loadOpenSnitchHits() {
    try {
        const hits = await apiCall('/opensnitch/hits');
        const list = document.getElementById('opensnitch-hits-list');
        if (!list) return;
        list.innerHTML = hits.map(h => `
            <tr>
                <td>${h.app}</td>
                <td>${h.dest}</td>
                <td><span class="status-badge status-${h.action.toLowerCase()}">${h.action}</span></td>
                <td style="font-size:0.75rem; color:var(--text-muted)">${new Date(h.time).toLocaleTimeString()}</td>
            </tr>
        `).join('');
    } catch (e) { console.error('OpenSnitch hits failed', e); }
}

async function toggleOpenSnitch() {
    const action = document.getElementById('opensnitch-toggle-btn').textContent === 'Start' ? 'start' : 'stop';
    try {
        await apiCall(`/opensnitch/${action}`, { method: 'POST' });
        showNotification('OpenSnitch', `Service ${action}ed`, 'success');
        setTimeout(updateOpenSnitch, 2000);
    } catch (e) { showNotification('Error', `Failed to ${action} OpenSnitch`, 'error'); }
}
