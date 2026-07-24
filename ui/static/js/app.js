const NetryxApp = (() => {
  let ws = null;
  let wsReconnectTimer = null;
  let currentJobId = null;
  let candidateCount = 0;

  const DOM = {
    uploadZone: () => document.getElementById('upload-zone'),
    uploadInput: () => document.getElementById('upload-input'),
    uploadStatus: () => document.getElementById('upload-status'),
    indexInfo: () => document.getElementById('index-info'),
    hubList: () => document.getElementById('hub-list'),
    searchImage: () => document.getElementById('search-image'),
    searchLat: () => document.getElementById('search-lat'),
    searchLon: () => document.getElementById('search-lon'),
    searchRadius: () => document.getElementById('search-radius'),
    searchBtn: () => document.getElementById('search-btn'),
    cancelBtn: () => document.getElementById('cancel-btn'),
    engineSelect: () => document.getElementById('engine-select'),
    progressBar: () => document.getElementById('progress-bar'),
    progressText: () => document.getElementById('progress-text'),
    progressCount: () => document.getElementById('progress-count'),
    resultsList: () => document.getElementById('results-list'),
    resultTemplate: () => document.getElementById('result-template'),
  };

  function init() {
    setupUpload();
    setupSearch();
    loadIndexInfo();
    loadHubList();
    loadCoverage();
  }

  function setupUpload() {
    const zone = DOM.uploadZone();
    const input = DOM.uploadInput();
    zone.addEventListener('click', () => input.click());
    zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('dragover'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
    zone.addEventListener('drop', (e) => { e.preventDefault(); zone.classList.remove('dragover'); if (e.dataTransfer.files[0]) handleUpload(e.dataTransfer.files[0]); });
    input.addEventListener('change', () => { if (input.files[0]) handleUpload(input.files[0]); });
  }

  async function handleUpload(file) {
    const status = DOM.uploadStatus();
    if (!file.name.endsWith('.netryx')) {
      status.textContent = 'Error: File must be .netryx bundle';
      status.className = 'upload-status error';
      return;
    }
    status.textContent = 'Uploading...';
    status.className = 'upload-status';
    const form = new FormData();
    form.append('file', file);
    try {
      const resp = await fetch('/api/v1/index/load', { method: 'POST', body: form });
      const data = await resp.json();
      if (resp.ok) {
        status.textContent = data.message || 'Index loaded';
        status.className = 'upload-status loaded';
        loadIndexInfo();
        loadCoverage();
      } else {
        status.textContent = 'Error: ' + (data.error || 'Unknown');
        status.className = 'upload-status error';
      }
    } catch (e) {
      status.textContent = 'Error: ' + e.message;
      status.className = 'upload-status error';
    }
  }

  async function loadIndexInfo() {
    const el = DOM.indexInfo();
    try {
      const resp = await fetch('/api/v1/index/info');
      const info = await resp.json();
      if (info.loaded) {
        el.innerHTML = `<span class="status-dot complete"></span>${info.entries.toLocaleString()} entries &middot; ${info.panoids.toLocaleString()} panoids`;
      } else {
        el.innerHTML = `<span class="status-dot queued"></span>No index loaded`;
      }
    } catch {
      el.innerHTML = `<span class="status-dot failed"></span>Error loading info`;
    }
  }

  async function loadHubList() {
    const el = DOM.hubList();
    try {
      const resp = await fetch('/api/v1/index/hub/list');
      const data = await resp.json();
      if (data.indexes && data.indexes.length > 0) {
        el.innerHTML = data.indexes.slice(0, 5).map(idx => `
          <div class="hub-item">
            <div>
              <div class="name">${idx.name || idx.repo_id}</div>
              <div class="meta">${idx.num_entries ? idx.num_entries.toLocaleString() + ' entries' : ''} ${idx.author ? '- ' + idx.author : ''}</div>
            </div>
            <button class="btn btn-sm btn-primary" onclick="NetryxApp.downloadHub('${idx.repo_id}')">Load</button>
          </div>
        `).join('');
      } else {
        el.innerHTML = '<div class="no-results">No community indexes found</div>';
      }
    } catch {
      el.innerHTML = '<div class="no-results">Hub unavailable</div>';
    }
  }

  async function downloadHub(repoName) {
    const form = new FormData();
    form.append('repo_name', repoName);
    try {
      const resp = await fetch('/api/v1/index/hub/download', { method: 'POST', body: form });
      const data = await resp.json();
      if (resp.ok) {
        DOM.uploadStatus().textContent = data.message;
        DOM.uploadStatus().className = 'upload-status loaded';
        loadIndexInfo();
        loadCoverage();
      } else {
        alert('Download failed: ' + (data.error || 'Unknown'));
      }
    } catch (e) {
      alert('Download error: ' + e.message);
    }
  }

  async function loadCoverage() {
    try {
      const resp = await fetch('/api/v1/index/coverage');
      const geojson = await resp.json();
      NetryxMap.loadCoverage(geojson);
    } catch {}
  }

  function setupSearch() {
    DOM.searchBtn().addEventListener('click', startSearch);
    DOM.cancelBtn().addEventListener('click', cancelSearch);
  }

  async function startSearch() {
    const file = DOM.searchImage().files[0];
    if (!file) { alert('Select a query image'); return; }
    const lat = parseFloat(DOM.searchLat().value);
    const lon = parseFloat(DOM.searchLon().value);
    const radius = parseFloat(DOM.searchRadius().value);
    if (isNaN(lat) || isNaN(lon)) { alert('Enter valid coordinates'); return; }

    DOM.searchBtn().disabled = true;
    DOM.cancelBtn().style.display = 'inline-block';
    NetryxMap.clearMarkers();
    DOM.resultsList().innerHTML = '<div class="no-results">Searching...</div>';
    setProgress(0, 'Starting...');

    const form = new FormData();
    form.append('file', file);
    form.append('lat', lat);
    form.append('lon', lon);
    form.append('radius', radius);
    form.append('engine', DOM.engineSelect().value);

    try {
      const resp = await fetch('/api/v1/search/run', { method: 'POST', body: form });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || 'Search failed');
      currentJobId = data.job_id;
      candidateCount = 0;
      connectWS(data.job_id);
    } catch (e) {
      setError(e.message);
      resetSearchUI();
    }
  }

  function connectWS(jobId) {
    if (ws) ws.close();
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${location.host}/api/v1/ws/search?job_id=${jobId}`;
    ws = new WebSocket(url);

    ws.onopen = () => {
      setProgress(0, 'Connected, waiting for stages...');
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleWSMessage(msg);
      } catch {}
    };

    ws.onclose = () => {
      ws = null;
      if (currentJobId) {
        wsReconnectTimer = setTimeout(() => connectWS(currentJobId), 1000);
      }
    };

    ws.onerror = () => {
      ws.close();
    };
  }

  function handleWSMessage(msg) {
    switch (msg.type) {
      case 'status':
        if (msg.stage === 1) {
          setProgress(0, msg.message);
        } else if (msg.stage === 2) {
          candidateCount = msg.total_candidates || 0;
          setProgress(0, msg.message);
        }
        break;

      case 'progress':
        if (candidateCount > 0) {
          const pct = Math.round((msg.current / candidateCount) * 100);
          setProgress(pct, `Matching ${msg.current + 1}/${candidateCount}`);
        }
        break;

      case 'complete':
        currentJobId = null;
        if (msg.result) showResults(msg.result);
        setProgress(100, 'Complete');
        resetSearchUI();
        break;

      case 'error':
        setError(msg.message);
        resetSearchUI();
        break;

      case 'cancelled':
        currentJobId = null;
        setProgress(0, 'Cancelled');
        resetSearchUI();
        break;
    }
  }

  function showResults(result) {
    const topClusters = result.top_clusters || [];
    const best = result.best || {};
    const allMatches = result.all_matches || [];
    const el = DOM.resultsList();
    const tmpl = DOM.resultTemplate();

    if (topClusters.length === 0 && best.inliers === 0) {
      el.innerHTML = '<div class="no-results">No matches found</div>';
      return;
    }

    let html = '';
    const items = topClusters.length > 0 ? topClusters : allMatches;
    items.forEach((m, i) => {
      const inliers = m.inliers || 0;
      const rank = i + 1;
      html += `
        <div class="result-card ${i === 0 ? 'active' : ''}" data-lat="${m.lat}" data-lon="${m.lon}" data-inliers="${inliers}" data-panoid="${m.panoid || ''}" data-rank="${rank}">
          <div class="rank">#${rank}</div>
          <div class="coords">${parseFloat(m.lat).toFixed(5)}, ${parseFloat(m.lon).toFixed(5)}</div>
          <div class="inliers">${inliers} inliers</div>
          <div class="panoid">${m.panoid || ''}</div>
        </div>
      `;

      if (topClusters.length > 0) {
        NetryxMap.addClusterMarker(m.lat, m.lon, inliers, rank);
      } else {
        NetryxMap.addCandidate(m.lat, m.lon, inliers, rank, m.panoid);
      }
    });
    el.innerHTML = html;

    el.querySelectorAll('.result-card').forEach(card => {
      card.addEventListener('click', () => {
        el.querySelectorAll('.result-card').forEach(c => c.classList.remove('active'));
        card.classList.add('active');
        const lat = parseFloat(card.dataset.lat);
        const lon = parseFloat(card.dataset.lon);
        NetryxMap.flyTo(lat, lon, 16);
      });
    });

    if (items.length > 0) {
      NetryxMap.flyTo(parseFloat(items[0].lat), parseFloat(items[0].lon), 14);
    }
  }

  function cancelSearch() {
    if (ws && currentJobId) {
      ws.send(JSON.stringify({ type: 'cancel' }));
    }
  }

  function setProgress(pct, text) {
    DOM.progressBar().style.width = pct + '%';
    DOM.progressText().textContent = text || '';
  }

  function setError(msg) {
    DOM.resultsList().innerHTML = `<div class="no-results" style="color:var(--error)">${msg}</div>`;
    setProgress(0, 'Error');
  }

  function resetSearchUI() {
    DOM.searchBtn().disabled = false;
    DOM.cancelBtn().style.display = 'none';
    currentJobId = null;
    if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null; }
  }

  return { init, downloadHub };
})();

document.addEventListener('DOMContentLoaded', () => NetryxApp.init());
