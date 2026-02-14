/* Ceramic Glaze Designer — Frontend */
(function() {
  'use strict';

  let materials = [];
  let clayBodies = [];
  let references = [];
  let currentResult = null;

  // ── Init ──
  async function init() {
    materials = await api('/api/materials');
    clayBodies = await api('/api/clay-bodies');
    references = await api('/api/references');

    populateClayBodies();
    setupTabs();
    setupDesign();
    setupAnalyze();
    setupLibrary();
    addMaterialRow();
    addMaterialRow();
    addMaterialRow();
  }

  async function api(url, body) {
    const opts = body ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)} : {};
    const r = await fetch(url, opts);
    return r.json();
  }

  // ── Tabs ──
  function setupTabs() {
    document.querySelectorAll('.tab').forEach(t => {
      t.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
        document.querySelectorAll('.panel').forEach(x => x.classList.remove('active'));
        t.classList.add('active');
        document.getElementById(t.dataset.panel).classList.add('active');
      });
    });
  }

  function populateClayBodies() {
    ['clay-body', 'analyze-clay-body'].forEach(id => {
      const sel = document.getElementById(id);
      sel.innerHTML = '<option value="">— None —</option>';
      clayBodies.forEach(cb => {
        sel.innerHTML += `<option value="${cb.id}">${cb.name} (Cone ${cb.cone})</option>`;
      });
    });
  }

  // ── Design Mode ──
  function setupDesign() {
    document.getElementById('design-btn').addEventListener('click', doDesign);
    document.getElementById('scale-btn').addEventListener('click', doScale);
    document.querySelectorAll('.variation-bar .btn').forEach(b => {
      b.addEventListener('click', () => doVariation(b.dataset.dir));
    });
    document.getElementById('glaze-desc').addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); doDesign(); }
    });
  }

  async function doDesign() {
    const desc = document.getElementById('glaze-desc').value.trim();
    if (!desc) return;
    showLoading('design');
    const data = await api('/api/design', {
      description: desc,
      clay_body: document.getElementById('clay-body').value || null,
      cone: parseInt(document.getElementById('cone-select').value),
    });
    hideLoading('design');
    if (!data.success) { showError('design', data.error); return; }
    currentResult = data;
    renderResults('design', data);
  }

  async function doVariation(direction) {
    if (!currentResult) return;
    showLoading('design');
    const data = await api('/api/variation', {
      recipe: currentResult.recipe,
      direction: direction,
      description: document.getElementById('glaze-desc').value,
      clay_body: document.getElementById('clay-body').value || null,
      colorant_additions: currentResult.additions_table ?
        Object.fromEntries(currentResult.additions_table.map(a => [a.material, a.grams])) : {},
      parsed: currentResult.parsed || {},
    });
    hideLoading('design');
    if (!data.success) { showError('design', data.error); return; }
    currentResult = data;
    renderResults('design', data);
  }

  async function doScale() {
    if (!currentResult) return;
    const weight = parseFloat(document.getElementById('scale-weight').value) || 1000;
    const fullRecipe = {...currentResult.recipe};
    if (currentResult.additions_table) {
      currentResult.additions_table.forEach(a => { fullRecipe[a.material] = a.grams; });
    }
    const data = await api('/api/scale', {recipe: fullRecipe, target_weight: weight});
    if (data.success) {
      const table = document.getElementById('design-recipe-table');
      table.innerHTML = buildRecipeTableHTML(data.recipe_table, [], data.total_weight);
    }
  }

  // ── Analyze Mode ──
  function setupAnalyze() {
    document.getElementById('add-material-btn').addEventListener('click', addMaterialRow);
    document.getElementById('analyze-btn').addEventListener('click', doAnalyze);
  }

  function addMaterialRow() {
    const container = document.getElementById('analyze-rows');
    const row = document.createElement('div');
    row.className = 'material-row';
    let opts = '<option value="">Select material…</option>';
    materials.forEach(m => { opts += `<option value="${m}">${m}</option>`; });
    row.innerHTML = `
      <div class="select-wrap"><select>${opts}</select></div>
      <input type="number" placeholder="%" min="0" step="0.1">
      <button class="btn-icon" title="Remove" onclick="this.parentElement.remove()">×</button>
    `;
    container.appendChild(row);
  }

  async function doAnalyze() {
    const rows = document.querySelectorAll('#analyze-rows .material-row');
    const recipe = {};
    rows.forEach(r => {
      const mat = r.querySelector('select').value;
      const amt = parseFloat(r.querySelector('input').value);
      if (mat && amt > 0) recipe[mat] = amt;
    });
    if (Object.keys(recipe).length === 0) return;
    showLoading('analyze');
    const data = await api('/api/analyze', {
      recipe: recipe,
      clay_body: document.getElementById('analyze-clay-body').value || null,
    });
    hideLoading('analyze');
    if (!data.success) { showError('analyze', data.error); return; }
    renderResults('analyze', data);
  }

  // ── Library ──
  function setupLibrary() {
    filterLibrary();
    document.getElementById('lib-search').addEventListener('input', filterLibrary);
    const srcFilter = document.getElementById('lib-source-filter');
    const surfFilter = document.getElementById('lib-surface-filter');
    if (srcFilter) srcFilter.addEventListener('change', filterLibrary);
    if (surfFilter) surfFilter.addEventListener('change', filterLibrary);
  }

  function filterLibrary() {
    const q = (document.getElementById('lib-search').value || '').toLowerCase();
    const srcEl = document.getElementById('lib-source-filter');
    const surfEl = document.getElementById('lib-surface-filter');
    const src = srcEl ? srcEl.value : 'all';
    const surf = surfEl ? surfEl.value : 'all';
    
    let filtered = references;
    if (q) {
      filtered = filtered.filter(r =>
        (r.name || '').toLowerCase().includes(q) ||
        (r.description || '').toLowerCase().includes(q) ||
        (r.notes || '').toLowerCase().includes(q) ||
        Object.keys(r.recipe || {}).some(m => m.toLowerCase().includes(q))
      );
    }
    if (src !== 'all') {
      filtered = filtered.filter(r => r.source === src);
    }
    if (surf !== 'all') {
      filtered = filtered.filter(r => (r.surface || '').toLowerCase().includes(surf));
    }
    renderLibrary(filtered);
  }

  function renderLibrary(items) {
    const list = document.getElementById('lib-list');
    const countEl = document.getElementById('lib-count');
    list.innerHTML = '';
    if (countEl) countEl.textContent = `${items.length} recipe${items.length !== 1 ? 's' : ''}`;
    
    items.forEach(ref => {
      const mats = Object.keys(ref.recipe || {}).join(', ');
      const adds = ref.additions ? Object.keys(ref.additions).join(', ') : '';
      const sourceBadge = ref.source ? `<span class="source-badge source-${ref.source}">${ref.source}</span>` : '';
      const surfBadge = ref.surface ? `<span class="surface-badge">${ref.surface}</span>` : '';
      const ratingStr = ref.rating ? `<span class="rating">★ ${ref.rating}</span>` : '';
      
      const card = document.createElement('div');
      card.className = 'ref-card';
      card.innerHTML = `
        <div class="ref-header">
          <h4>${ref.name || 'Unnamed'}</h4>
          <div class="ref-badges">${sourceBadge}${surfBadge}${ratingStr}</div>
        </div>
        <p class="ref-desc">${ref.description || ''}</p>
        <div class="ref-materials">${mats}${adds ? ' + ' + adds : ''}</div>
      `;
      card.addEventListener('click', () => loadIntoAnalyzer(ref));
      list.appendChild(card);
    });
  }

  function loadIntoAnalyzer(ref) {
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(x => x.classList.remove('active'));
    document.querySelector('[data-panel="analyze"]').classList.add('active');
    document.getElementById('analyze').classList.add('active');

    const container = document.getElementById('analyze-rows');
    container.innerHTML = '';
    const allMats = {...ref.recipe, ...(ref.additions || {})};
    Object.entries(allMats).forEach(([mat, amt]) => {
      addMaterialRow();
      const rows = container.querySelectorAll('.material-row');
      const lastRow = rows[rows.length - 1];
      lastRow.querySelector('select').value = mat;
      lastRow.querySelector('input').value = amt;
    });
  }

  // ── Render Results ──
  function renderResults(prefix, data) {
    hideError(prefix);
    const results = document.getElementById(prefix + '-results');
    results.classList.add('visible');

    // Recipe table
    const table = document.getElementById(prefix + '-recipe-table');
    const additions = data.additions_table || [];
    const recipeRows = data.recipe_table || [];
    const total = recipeRows.reduce((s, r) => s + r.grams, 0);
    table.innerHTML = buildRecipeTableHTML(recipeRows, additions, total);

    // UMF chart
    renderUMFChart(prefix, data.umf);

    // Limits
    renderLimits(prefix, data.limits);

    // CTE
    const cte = typeof data.cte === 'object' ? data.cte : {value: data.cte};
    document.getElementById(prefix + '-cte').textContent = cte.value.toFixed(1) + ' × 10⁻⁷/°C';
    document.getElementById(prefix + '-cte-note').textContent = cte.note || '';

    // Food safety
    const fs = document.getElementById(prefix + '-food-safety');
    fs.innerHTML = '';
    (data.food_safety || []).forEach(w => {
      const d = document.createElement('div');
      d.className = 'food-safety-item';
      d.textContent = w;
      fs.appendChild(d);
    });

    // Notes/explanation (design only)
    if (prefix === 'design') {
      const notesCard = document.getElementById('design-notes-card');
      const exp = document.getElementById('design-explanation');
      const allNotes = [
        ...(data.color_notes || []).map(n => '🎨 ' + n),
        ...(data.notes || []).map(n => '📝 ' + n),
        ...(data.explanation || []).map(n => '→ ' + n),
      ];
      if (allNotes.length) {
        notesCard.style.display = '';
        exp.innerHTML = allNotes.map(n => `<p>${escHtml(n)}</p>`).join('');
      } else {
        notesCard.style.display = 'none';
      }
    }
  }

  function buildRecipeTableHTML(rows, additions, total) {
    let html = '<thead><tr><th>Material</th><th style="text-align:right">%</th><th style="text-align:right">Grams</th></tr></thead><tbody>';
    rows.forEach(r => {
      html += `<tr><td>${escHtml(r.material)}</td><td style="text-align:right">${r.percent.toFixed(1)}</td><td style="text-align:right">${r.grams.toFixed(1)}</td></tr>`;
    });
    if (additions && additions.length) {
      html += `<tr><td colspan="3"><span class="additions-label">+ Colorant Additions</span></td></tr>`;
      additions.forEach(r => {
        html += `<tr><td>${escHtml(r.material)}</td><td style="text-align:right">${r.percent.toFixed(1)}</td><td style="text-align:right">${r.grams.toFixed(1)}</td></tr>`;
      });
    }
    const grandTotal = (additions || []).reduce((s, a) => s + a.grams, total);
    html += `<tr class="total-row"><td>Total</td><td></td><td style="text-align:right">${grandTotal.toFixed(1)}</td></tr>`;
    html += '</tbody>';
    return html;
  }

  // ── UMF Chart ──
  const FLUX = ['Li2O','Na2O','K2O','CaO','MgO','ZnO','SrO','BaO'];
  const AMPHOTERIC = ['Al2O3','B2O3'];
  const GLASS = ['SiO2'];
  const COLORANT = ['Fe2O3','TiO2','MnO','P2O5','CoO','CuO','Cr2O3','NiO'];

  function renderUMFChart(prefix, umf) {
    const container = document.getElementById(prefix + '-umf-chart');
    container.innerHTML = '';
    const maxVal = Math.max(...Object.values(umf), 0.01);

    function addGroup(label, oxides, cls) {
      const lbl = document.createElement('div');
      lbl.className = 'umf-group-label';
      lbl.textContent = label;
      container.appendChild(lbl);
      oxides.forEach(ox => {
        const val = umf[ox] || 0;
        if (val < 0.0005 && cls !== 'glass') return;
        const row = document.createElement('div');
        row.className = 'umf-bar-row';
        const pct = (val / maxVal * 100).toFixed(1);
        row.innerHTML = `
          <span class="umf-bar-label">${ox}</span>
          <div class="umf-bar-track"><div class="umf-bar-fill ${cls}" style="width:${pct}%"></div></div>
          <span class="umf-bar-value">${val.toFixed(3)}</span>
        `;
        container.appendChild(row);
      });
    }

    addGroup('Fluxes (sum ≈ 1.0)', FLUX, 'flux');
    addGroup('Amphoterics', AMPHOTERIC, 'amphoteric');
    addGroup('Glass Formers', GLASS, 'glass');
    const hasColorant = COLORANT.some(ox => (umf[ox] || 0) > 0.0005);
    if (hasColorant) addGroup('Colorants', COLORANT, 'colorant');
  }

  // ── Limits ──
  function renderLimits(prefix, limits) {
    const container = document.getElementById(prefix + '-limits');
    container.innerHTML = '';
    if (!limits) return;
    const maxLimit = Math.max(...limits.map(l => Math.max(l.max, l.value)), 1);
    limits.forEach(l => {
      const row = document.createElement('div');
      row.className = 'limit-row';
      const rangeLeft = (l.min / maxLimit * 100).toFixed(1);
      const rangeWidth = ((l.max - l.min) / maxLimit * 100).toFixed(1);
      const markerPos = Math.min(Math.max(l.value / maxLimit * 100, 0), 100).toFixed(1);
      row.innerHTML = `
        <span class="limit-dot ${l.status}"></span>
        <span class="limit-oxide">${l.oxide}</span>
        <div class="limit-bar">
          <div class="limit-range" style="left:${rangeLeft}%;width:${rangeWidth}%"></div>
          <div class="limit-marker ${l.status}" style="left:calc(${markerPos}% - 1px)"></div>
        </div>
        <span class="limit-value">${l.value.toFixed(3)}</span>
      `;
      container.appendChild(row);
    });
  }

  // ── Helpers ──
  function showLoading(prefix) {
    document.getElementById(prefix + '-loading').classList.add('visible');
    document.getElementById(prefix + '-results').classList.remove('visible');
    hideError(prefix);
  }
  function hideLoading(prefix) {
    document.getElementById(prefix + '-loading').classList.remove('visible');
  }
  function showError(prefix, msg) {
    const el = document.getElementById(prefix + '-error');
    el.textContent = msg;
    el.classList.add('visible');
  }
  function hideError(prefix) {
    document.getElementById(prefix + '-error').classList.remove('visible');
  }
  function escHtml(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  init();
})();
