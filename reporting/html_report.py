import json
from typing import Any, Dict


def embedded_json(payload: Dict[str, Any]) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return (
        serialized.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_html(payload: Dict[str, Any]) -> str:
    return _HTML.replace("__REPORT_DATA__", embedded_json(payload))


_HTML = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:">
  <title>Protocol Check Report</title>
  <style>
    :root {
      --ink:#172033; --muted:#687287; --line:#dfe4ec; --soft:#f5f7fa;
      --paper:#fff; --nav:#111827; --nav-soft:#202a3a; --accent:#3457d5;
      --pass:#177245; --pass-bg:#e7f5ed; --fail:#a72b35; --fail-bg:#fdebed;
      --review:#8a5a00; --review-bg:#fff4d6; --error:#8e2344; --error-bg:#f7e4ed;
      --blocked:#5f3b91; --blocked-bg:#efe8f7; --na:#5f6878; --na-bg:#eef1f4;
      --e1:#dcecff; --e2:#ece4ff; --e3:#fff0cf; --e4:#dff3ef; --e5:#f9e3ea;
      --shadow:0 12px 34px rgba(20,30,50,.09);
    }
    *{box-sizing:border-box} html,body{margin:0;min-height:100%;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--ink);background:#eef1f5}
    button,input,select{font:inherit} button{cursor:pointer}
    .topbar{height:72px;background:var(--paper);border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 26px;position:sticky;top:0;z-index:30}
    .brand{display:flex;align-items:center;gap:13px}.brand-mark{width:36px;height:36px;border-radius:10px;background:linear-gradient(145deg,#2846b8,#6882e8);display:grid;place-items:center;color:white;font-weight:800}.brand h1{font-size:18px;margin:0}.brand small{display:block;color:var(--muted);margin-top:2px}
    .tabs{display:flex;gap:6px;background:var(--soft);padding:4px;border-radius:10px}.tab{border:0;background:transparent;color:var(--muted);padding:8px 14px;border-radius:7px;font-weight:700}.tab.active{background:white;color:var(--ink);box-shadow:0 1px 4px rgba(0,0,0,.08)}
    .layout{display:grid;grid-template-columns:300px minmax(0,1fr);min-height:calc(100vh - 72px)}
    .sidebar{background:var(--nav);color:#e9edf5;padding:22px 18px;overflow:auto;height:calc(100vh - 72px);position:sticky;top:72px}.side-title{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#9ca8bb;font-weight:800;margin:0 0 11px}
    .coverage-card{background:var(--nav-soft);border:1px solid #303b4d;border-radius:12px;padding:15px;margin-bottom:18px}.coverage-big{font-size:26px;font-weight:800}.coverage-sub{font-size:12px;color:#aeb8c9}.coverage-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:13px}.coverage-stat{font-size:12px;color:#aeb8c9}.coverage-stat b{display:block;color:white;font-size:17px}.coverage-bar{height:6px;background:#374154;border-radius:6px;overflow:hidden;margin:12px 0 8px}.coverage-fill{height:100%;background:#8299ee}
    .category{border-top:1px solid #2c3647;padding-top:10px;margin-top:10px}.category-toggle{width:100%;border:0;color:#f5f7fb;background:transparent;text-align:left;font-weight:800;padding:8px 5px}.item-button{width:100%;border:0;background:transparent;color:#bbc4d3;text-align:left;padding:7px 10px;border-radius:7px;display:flex;justify-content:space-between}.item-button:hover,.item-button.active{background:#2b374b;color:white}.item-button small{color:#7f8ba0}.concept-list{padding:0 7px 5px 20px;color:#8f9bad;font-size:11px;line-height:1.45}.category.collapsed .category-body{display:none}
    .main{padding:24px;min-width:0}.panel{background:var(--paper);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow)}
    .summary{display:grid;grid-template-columns:repeat(4,minmax(120px,1fr));gap:12px;margin-bottom:18px}.metric{background:white;border:1px solid var(--line);border-radius:12px;padding:14px}.metric b{display:block;font-size:22px}.metric span{font-size:12px;color:var(--muted)}
    .notice{border:1px solid #ead9a6;background:#fff9e9;border-radius:10px;padding:11px 14px;margin-bottom:14px;color:#655125;font-size:13px}.issues{border-color:#e5c8d2;background:#fff5f8;color:#6e2b41}.issues ul{margin:7px 0 0;padding-left:18px}
    .matrix-head{padding:18px 20px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:15px;align-items:flex-end}.matrix-head h2{margin:0;font-size:20px}.matrix-head p{margin:5px 0 0;color:var(--muted);font-size:13px}.filters{display:flex;gap:8px;flex-wrap:wrap}.filters input,.filters select{border:1px solid #ccd3de;background:white;border-radius:8px;padding:8px 10px;color:var(--ink)}
    .matrix-scroll{overflow:auto;max-height:calc(100vh - 255px)}table{border-collapse:separate;border-spacing:0;width:100%;font-size:13px}th,td{border-right:1px solid var(--line);border-bottom:1px solid var(--line);padding:10px;vertical-align:top}thead th{position:sticky;top:0;background:#f8f9fb;z-index:8;text-align:left;min-width:158px}thead th:first-child{left:0;z-index:10;min-width:110px}.nio-cell{position:sticky;left:0;background:white;z-index:5;font-weight:800}.requirement-cell{min-width:330px;max-width:520px;line-height:1.45}.section-row td{background:#edf1f7;font-weight:800;padding:8px 12px;position:sticky;left:0}.section-toggle{border:0;background:transparent;color:var(--ink);font-weight:800}.implementation-select{width:100%;font-size:11px;margin-top:7px;padding:5px;border:1px solid #d3d8e1;border-radius:6px;background:white}.preferred-missing{font-size:10px;color:#906000;margin-top:4px}.empty-state{padding:45px;text-align:center;color:var(--muted)}
    .cell-button{border:0;border-radius:7px;padding:7px 9px;font-size:11px;font-weight:850;letter-spacing:.025em;min-width:94px;text-align:center}.cell-button:hover{outline:2px solid rgba(52,87,213,.25)}.no-result{color:#8b94a4;font-size:12px}.status{display:inline-flex;align-items:center;border-radius:999px;padding:5px 9px;font-size:11px;font-weight:850;letter-spacing:.03em}.PASS{color:var(--pass);background:var(--pass-bg)}.FAIL{color:var(--fail);background:var(--fail-bg)}.REVIEW{color:var(--review);background:var(--review-bg)}.ERROR{color:var(--error);background:var(--error-bg)}.BLOCKED{color:var(--blocked);background:var(--blocked-bg)}.NOT_APPLICABLE{color:var(--na);background:var(--na-bg)}
    .explorer{display:none}.explorer.active,.matrix-view.active{display:block}.matrix-view:not(.active){display:none}.explorer-toolbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}.back{border:1px solid var(--line);background:white;border-radius:8px;padding:8px 12px}.compare-button{border:0;background:var(--accent);color:white;border-radius:8px;padding:9px 13px;font-weight:750}.compare-button[disabled]{opacity:.45;cursor:not-allowed}
    .explorer-header{padding:21px}.eyebrow{font-size:11px;text-transform:uppercase;letter-spacing:.11em;color:var(--muted);font-weight:800}.explorer-header h2{margin:7px 0 6px}.requirement-box{margin-top:15px;background:var(--soft);border-left:4px solid #8b9bd9;padding:13px 15px;border-radius:5px;line-height:1.5;white-space:pre-wrap}.facts{display:flex;gap:18px;flex-wrap:wrap;color:var(--muted);font-size:12px}.result-grid{display:grid;gap:16px;margin-top:16px}.result-card{padding:20px}.result-card h3{margin:0 0 12px}.result-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.message{font-size:15px;line-height:1.5;margin:13px 0}.detail-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;margin:13px 0}.detail{background:var(--soft);border-radius:8px;padding:10px}.detail label{display:block;color:var(--muted);font-size:10px;text-transform:uppercase;font-weight:800;letter-spacing:.06em}.detail div{margin-top:4px;word-break:break-word}
    .section-card{border-top:1px solid var(--line);padding-top:15px;margin-top:17px}.section-card h4{margin:0 0 11px;font-size:14px}.trace-block{background:#f7f8fa;border:1px solid var(--line);border-radius:9px;padding:12px;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.45;font:12px ui-monospace,SFMono-Regular,Menlo,monospace;max-height:360px;overflow:auto}.trace-token{display:inline-block;padding:1px 5px;border-radius:4px;font-weight:900;color:#263044}.evidence-grid,.candidate-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}.evidence-card,.candidate-card{border:1px solid rgba(70,80,100,.15);border-radius:11px;padding:14px;position:relative}.evidence-card h5,.candidate-card h5{margin:0 0 9px;font-size:14px}.evidence-0{background:var(--e1)}.evidence-1{background:var(--e2)}.evidence-2{background:var(--e3)}.evidence-3{background:var(--e4)}.evidence-4{background:var(--e5)}.evidence-tag{display:inline-flex;border:1px solid rgba(30,40,60,.18);padding:3px 7px;border-radius:6px;margin-right:6px;font-weight:900}.provenance{font-size:11px;color:#536074;display:grid;grid-template-columns:1fr 1fr;gap:4px}.evidence-text{white-space:pre-wrap;line-height:1.45;margin-top:11px;max-height:270px;overflow:auto;background:rgba(255,255,255,.46);padding:9px;border-radius:7px}.citation{font-size:10px;font-weight:800}.candidate-card{background:#f4f1fb}.confirmed{box-shadow:inset 0 0 0 2px #9d6cc0}.candidate-text{white-space:pre-wrap;background:white;border-radius:7px;padding:9px;margin:8px 0;line-height:1.4}.judgment{font-weight:850;font-size:11px}
    details{margin-top:10px}summary{cursor:pointer;color:#44506a;font-weight:700;font-size:12px}.raw-json{margin-top:10px}.comparison{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start}.comparison .result-card{margin:0}.muted{color:var(--muted)}.hidden{display:none!important}.nowrap{white-space:nowrap}
    @media(max-width:950px){.layout{grid-template-columns:230px minmax(0,1fr)}.summary{grid-template-columns:1fr 1fr}.comparison{grid-template-columns:1fr}.main{padding:16px}}
  </style>
</head>
<body>
  <header class="topbar">
    <div class="brand"><div class="brand-mark">PC</div><div><h1>Protocol Check Report</h1><small id="report-subtitle">Offline audit dataset</small></div></div>
    <div class="tabs"><button class="tab active" data-view="matrix">Matrix</button><button class="tab" data-view="explorer">Result Explorer</button></div>
  </header>
  <div class="layout">
    <aside class="sidebar">
      <div id="coverage"></div>
      <p class="side-title">Checklist hierarchy</p>
      <nav id="checklist-nav"></nav>
    </aside>
    <main class="main">
      <section id="matrix-view" class="matrix-view active">
        <div id="dataset-summary" class="summary"></div>
        <div id="warnings"></div>
        <div id="framework-issues"></div>
        <div class="panel">
          <div class="matrix-head"><div><h2 id="matrix-title">Matrix</h2><p id="matrix-description">NIO × conceptual sub-check</p></div><div class="filters"><input id="matrix-search" type="search" placeholder="Search NIO or requirement"><select id="status-filter"><option value="">All statuses</option><option>PASS</option><option>FAIL</option><option>REVIEW</option><option>ERROR</option><option>BLOCKED</option><option>NOT_APPLICABLE</option></select></div></div>
          <div id="matrix-container" class="matrix-scroll"></div>
        </div>
      </section>
      <section id="explorer-view" class="explorer">
        <div class="explorer-toolbar"><button id="back-to-matrix" class="back">← Back to Matrix</button><button id="compare-button" class="compare-button" disabled>Compare implementations</button></div>
        <div id="explorer-content"><div class="panel empty-state">Select a result in the Matrix to inspect it.</div></div>
      </section>
    </main>
  </div>
  <script id="report-data" type="application/json">__REPORT_DATA__</script>
  <script>
  (() => {
    'use strict';
    const report = JSON.parse(document.getElementById('report-data').textContent);
    const severity = {ERROR:0,BLOCKED:1,FAIL:2,REVIEW:3,PASS:4,NOT_APPLICABLE:5};
    const evidenceClasses = ['evidence-0','evidence-1','evidence-2','evidence-3','evidence-4'];
    const targets = report.dataset.target_by_id;
    const variants = Object.fromEntries(report.dataset.variants.map(v => [v.variant_id,v]));
    const concepts = {};
    const items = {};
    report.catalog.categories.forEach(category => category.items.forEach(item => {
      items[item.item_id] = item;
      item.concepts.forEach(concept => concepts[concept.concept_id] = concept);
    }));
    const unmappedItem = buildUnmappedItem();
    if (unmappedItem) items[unmappedItem.item_id] = unmappedItem;
    const firstItem = report.catalog.categories.flatMap(c => c.items).find(item => actionableConcepts(item).length) || report.catalog.categories[0].items[0];
    const state = {view:'matrix', itemId:firstItem.item_id, selectedVariants:{}, collapsedSections:new Set(), explorer:null, compare:false};
    Object.values(concepts).forEach(c => state.selectedVariants[c.concept_id] = c.selected_variant_id);
    if (unmappedItem) unmappedItem.concepts.forEach(c => state.selectedVariants[c.concept_id] = c.selected_variant_id);

    const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    const textOr = (value, fallback='—') => value === null || value === undefined || value === '' ? fallback : esc(value);
    const statusBadge = status => `<span class="status ${esc(status)}">${esc(status)}</span>`;
    const aggregate = indexes => indexes.map(i => report.dataset.results[i]).sort((a,b) => severity[a.status]-severity[b.status])[0].status;
    const displayVariant = variant => `${variant.implementation} · ${variant.check_id}`;

    function actionableConcepts(item) {
      if (item.item_id === '__unmapped__') return item.concepts;
      return item.concepts.filter(c => c.interpretation_status !== 'NOT_CHECK');
    }

    function buildUnmappedItem() {
      if (!report.unmapped_checker_ids.length) return null;
      return {item_id:'__unmapped__',title:'Unmapped checks',concepts:report.unmapped_checker_ids.map(checkerId => {
        const available = report.dataset.variants.filter(v => v.check_id === checkerId);
        return {concept_id:`unmapped:${checkerId}`,title:checkerId,checker_ids:[checkerId],available_variants:available,selected_variant_id:available[0]?.variant_id || null,preferred_available:true,interpretation_status:'CHECK',maturity:'not_implemented'};
      })};
    }

    function renderCoverage() {
      const c = report.coverage;
      const percentage = c.actionable_concepts ? Math.round(c.implemented_concepts / c.actionable_concepts * 100) : 0;
      document.getElementById('coverage').innerHTML = `<p class="side-title">Checklist coverage</p><div class="coverage-card"><div class="coverage-big">${c.item_count} items</div><div class="coverage-sub">System implementation capability</div><div class="coverage-grid"><div class="coverage-stat"><b>${c.fully_covered}</b>Full</div><div class="coverage-stat"><b>${c.partially_covered}</b>Partial</div><div class="coverage-stat"><b>${c.not_implemented}</b>Not implemented</div><div class="coverage-stat"><b>${c.not_checkable}</b>Not checkable</div></div><div class="coverage-bar"><div class="coverage-fill" style="width:${percentage}%"></div></div><div class="coverage-sub">Atomic checks: ${c.implemented_concepts} / ${c.actionable_concepts} implemented</div>${c.categories.map(category=>`<div class="coverage-sub" style="margin-top:8px"><b style="color:white">${esc(category.title)}</b> · ${category.implemented_concepts}/${category.actionable_concepts} atomic · ${category.fully_covered} full, ${category.partially_covered} partial</div>`).join('')}</div>`;
    }

    function renderSummary() {
      const d = report.dataset;
      document.getElementById('dataset-summary').innerHTML = [['Result files',d.result_files.length],['Checker implementations',d.checker_implementation_count],['NIOs represented',d.target_count],['Result records',d.record_count]].map(([label,value]) => `<div class="metric"><b>${value}</b><span>${label}</span></div>`).join('');
      document.getElementById('report-subtitle').textContent = `${report.provenance.protocol_source} · generated ${report.provenance.generated_at}`;
      const warnings = document.getElementById('warnings');
      const provenance=`<details class="notice"><summary>Report dataset provenance</summary><div style="margin-top:9px"><b>Protocol:</b> ${esc(report.provenance.protocol_source)}<br><b>Result files:</b> ${report.provenance.result_files.map(esc).join(', ')||'—'}<br><b>Checker IDs:</b> ${report.provenance.checker_ids.map(esc).join(', ')||'—'}<br><b>Implementations:</b> ${report.provenance.implementations.map(esc).join(', ')||'—'}<br><b>Generated:</b> ${esc(report.provenance.generated_at)}</div></details>`;
      warnings.innerHTML = (report.warnings.length ? `<div class="notice">${report.warnings.map(esc).join('<br>')}</div>` : '')+provenance;
      const issueIndexes = report.dataset.framework_result_indexes;
      document.getElementById('framework-issues').innerHTML = issueIndexes.length ? `<div class="notice issues"><b>Framework issues</b><ul>${issueIndexes.map(index => {const r=report.dataset.results[index];return `<li>${esc(r.check_id)} · ${esc(r.implementation)} · ${statusBadge(r.status)} — ${esc(r.message)}</li>`}).join('')}</ul></div>` : '';
    }

    function renderNav() {
      const html = report.catalog.categories.map(category => `<div class="category"><button class="category-toggle" type="button">▾ ${esc(category.title)} <span class="muted">${category.items.length}</span></button><div class="category-body">${category.items.map(item => navItem(item)).join('')}</div></div>`).join('') + (unmappedItem ? `<div class="category"><button class="category-toggle" type="button">▾ Unmapped checks</button><div class="category-body">${navItem(unmappedItem)}</div></div>` : '');
      const nav = document.getElementById('checklist-nav');
      nav.innerHTML = html;
      nav.querySelectorAll('.category-toggle').forEach(button => button.addEventListener('click', () => button.parentElement.classList.toggle('collapsed')));
      nav.querySelectorAll('.item-button').forEach(button => button.addEventListener('click', () => {state.itemId=button.dataset.item;state.view='matrix';renderAll();}));
    }

    function navItem(item) {
      const active = item.item_id === state.itemId ? ' active' : '';
      const conceptsHere = actionableConcepts(item); const coverage=report.coverage.items.find(value=>value.item_id===item.item_id); const label=coverage?({fully_covered:'Full',partially_covered:'Partial',not_implemented:'Not impl.',not_checkable:'N/A'}[coverage.classification]):`${conceptsHere.length}`;
      return `<button class="item-button${active}" data-item="${esc(item.item_id)}"><span>${esc(item.title)}</span><small>${esc(label)}</small></button>${active && conceptsHere.length ? `<div class="concept-list">${conceptsHere.map(c => esc(c.title)).join('<br>')}</div>` : ''}`;
    }

    function renderMatrix() {
      const item = items[state.itemId];
      const activeConcepts = actionableConcepts(item);
      document.getElementById('matrix-title').textContent = item.title;
      document.getElementById('matrix-description').textContent = item.item_id === '__unmapped__' ? 'Results without a checklist-catalog mapping' : 'NIO × conceptual sub-check';
      const container = document.getElementById('matrix-container');
      if (!activeConcepts.length) { container.innerHTML='<div class="empty-state"><b>No actionable conceptual sub-checks</b><br>This checklist item is currently classified as not checkable.</div>'; return; }
      const search = document.getElementById('matrix-search').value.trim().toLowerCase();
      const filterStatus = document.getElementById('status-filter').value;
      const groups = report.dataset.section_groups.map((group, groupIndex) => {
        const rows = group.target_ids.filter(targetId => {
          const target = targets[targetId];
          if (search && !`${target.id} ${target.specification}`.toLowerCase().includes(search)) return false;
          if (!filterStatus) return true;
          return activeConcepts.some(concept => {
            const variantId=state.selectedVariants[concept.concept_id];
            const indexes=variantId && report.dataset.cells[variantId]?.[targetId];
            return indexes?.length && aggregate(indexes)===filterStatus;
          });
        }).map(targetId => matrixRow(targetId,activeConcepts)).join('');
        if (!rows) return '';
        const collapsed=state.collapsedSections.has(groupIndex);
        return `<tbody><tr class="section-row"><td colspan="${activeConcepts.length+2}"><button class="section-toggle" data-group="${groupIndex}">${collapsed?'▸':'▾'} ${esc(group.label)} · ${group.target_ids.length} NIOs</button></td></tr>${collapsed?'':rows}</tbody>`;
      }).join('');
      container.innerHTML = `<table><thead><tr><th>NIO</th><th>Requirement</th>${activeConcepts.map(conceptHeader).join('')}</tr></thead>${groups || `<tbody><tr><td colspan="${activeConcepts.length+2}" class="empty-state">No rows match the current filters.</td></tr></tbody>`}</table>`;
      container.querySelectorAll('.implementation-select').forEach(select => select.addEventListener('change', () => {state.selectedVariants[select.dataset.concept]=select.value;renderMatrix();}));
      container.querySelectorAll('.cell-button').forEach(button => button.addEventListener('click', () => openExplorer(button.dataset.concept,button.dataset.target,button.dataset.variant)));
      container.querySelectorAll('.section-toggle').forEach(button => button.addEventListener('click', () => {const index=Number(button.dataset.group);state.collapsedSections.has(index)?state.collapsedSections.delete(index):state.collapsedSections.add(index);renderMatrix();}));
    }

    function conceptHeader(concept) {
      const available=concept.available_variants || [];
      const selector=available.length ? `<select class="implementation-select" data-concept="${esc(concept.concept_id)}">${available.map(v => `<option value="${v.variant_id}" ${state.selectedVariants[concept.concept_id]===v.variant_id?'selected':''}>${esc(displayVariant(v))}</option>`).join('')}</select>` : '<div class="muted" style="font-size:11px;margin-top:7px">No implementation data</div>';
      const missing=available.length && !concept.preferred_available ? '<div class="preferred-missing">Preferred implementation absent</div>' : '';
      return `<th>${esc(concept.title)}${selector}${missing}</th>`;
    }

    function matrixRow(targetId, activeConcepts) {
      const target=targets[targetId];
      return `<tr><td class="nio-cell">${esc(target.id)}</td><td class="requirement-cell">${esc(target.specification)}</td>${activeConcepts.map(concept => matrixCell(targetId,concept)).join('')}</tr>`;
    }

    function matrixCell(targetId,concept) {
      const variantId=state.selectedVariants[concept.concept_id];
      const indexes=variantId && report.dataset.cells[variantId]?.[targetId];
      if (!indexes?.length) return '<td><span class="no-result">—<br>No result</span></td>';
      const status=aggregate(indexes); const count=indexes.length>1?` ×${indexes.length}`:'';
      return `<td><button class="cell-button ${status}" data-concept="${esc(concept.concept_id)}" data-target="${esc(targetId)}" data-variant="${esc(variantId)}">${esc(status)}${count}</button></td>`;
    }

    function openExplorer(conceptId,targetId,variantId) { state.explorer={conceptId,targetId,variantId}; state.compare=false; state.view='explorer'; renderAll(); }

    function renderExplorer() {
      const root=document.getElementById('explorer-content'); const button=document.getElementById('compare-button');
      if (!state.explorer) {root.innerHTML='<div class="panel empty-state">Select a result in the Matrix to inspect it.</div>';button.disabled=true;return;}
      const {conceptId,targetId,variantId}=state.explorer; const concept=concepts[conceptId] || unmappedItem?.concepts.find(c=>c.concept_id===conceptId); const target=targets[targetId];
      const available=(concept.available_variants||[]).filter(v => report.dataset.cells[v.variant_id]?.[targetId]?.length);
      button.disabled=available.length<2; button.textContent=state.compare?'Show selected implementation':'Compare implementations';
      const header=`<div class="panel explorer-header"><div class="eyebrow">${esc(concept.title)}</div><h2>${esc(target.id)}</h2><div class="facts"><span>Section: ${textOr(target.section_number,'Unsectioned')}</span><span>Req: ${textOr(target.req)}</span><span>Source: ${sourceLabel(target.source)}</span></div><div class="requirement-box">${esc(target.specification)}</div></div>`;
      if (state.compare && available.length>=2) {
        root.innerHTML=header+`<div class="comparison">${available.map(v => resultGroup(concept,target,v,true)).join('')}</div>`;
      } else {
        const selected=available.find(v=>v.variant_id===variantId) || available[0];
        root.innerHTML=header+(selected?`<div class="result-grid">${resultGroup(concept,target,selected,false)}</div>`:'<div class="panel empty-state">No result is available for this implementation.</div>');
      }
    }

    function sourceLabel(source) { if (!source) return '—'; return [source.file,source.table!=null?`table ${source.table}`:'',source.word_row!=null?`row ${source.word_row}`:''].filter(Boolean).map(esc).join(' · ') || '—'; }

    function resultGroup(concept,target,variant,compact) {
      const indexes=report.dataset.cells[variant.variant_id]?.[target.id] || [];
      return `<div>${indexes.length>1?`<div class="notice">${indexes.length} result records were emitted for this checker-target invocation.</div>`:''}${indexes.map((index,recordIndex)=>renderResult(report.dataset.results[index],concept,target,variant,recordIndex,indexes.length,compact)).join('')}</div>`;
    }

    function renderResult(result,concept,target,variant,recordIndex,recordCount,compact) {
      const metadata=result.metadata||{};
      return `<article class="panel result-card"><div class="result-heading"><div><div class="eyebrow">${esc(result.check_id)}</div><h3>${esc(result.implementation)}${recordCount>1?` · Result ${recordIndex+1}/${recordCount}`:''}</h3></div>${statusBadge(result.status)}</div><div class="message">${esc(result.message)}</div><div class="detail-grid"><div class="detail"><label>Checklist concept</label><div>${esc(concept.title)}</div></div><div class="detail"><label>Checker ID</label><div>${esc(result.check_id)}</div></div><div class="detail"><label>Implementation</label><div>${esc(result.implementation)}</div></div><div class="detail"><label>Related IDs</label><div>${result.related_ids.length?result.related_ids.map(esc).join(', '):'—'}</div></div></div>${renderDiagnostics(metadata)}${renderChunks(result)}${renderCandidates(metadata,result,target)}${renderTrace(result)}${renderEvidence(result.evidence)}<details class="raw-json"><summary>Generic result JSON</summary><pre class="trace-block">${esc(JSON.stringify(cleanResult(result),null,2))}</pre></details><div class="muted" style="font-size:11px;margin-top:10px">Source: ${esc(result._source_file)} line ${result._source_line}</div></article>`;
    }

    function renderDiagnostics(metadata) {
      const ignored=new Set(['prompt','raw_model_response','parsed_model_response','model','retrieved_chunks','supporting_chunk_ids','target_requirement','candidates']);
      const entries=Object.entries(metadata).filter(([key,value])=>!ignored.has(key)&&(value===null||['string','number','boolean'].includes(typeof value)));
      if (!entries.length) return '';
      return `<div class="section-card"><h4>Diagnostics</h4><div class="detail-grid">${entries.map(([key,value])=>`<div class="detail"><label>${esc(key)}</label><div>${textOr(value)}</div></div>`).join('')}</div></div>`;
    }

    function renderChunks(result) {
      const metadata=result.metadata||{};
      if (!Array.isArray(metadata.retrieved_chunks)||!metadata.retrieved_chunks.length) return '';
      const chunks=result._presentation?.retrieved_chunks||[...metadata.retrieved_chunks].sort((a,b)=>(a.rank||0)-(b.rank||0)).map(chunk=>({...chunk,cited:(metadata.supporting_chunk_ids||[]).includes(chunk.chunk_id)}));
      return `<div class="section-card"><h4>Retrieved ARINC evidence</h4><p class="muted">Similarity records retrieval ranking only; it is not factual support.</p><div class="evidence-grid">${chunks.map((chunk,index)=>`<article class="evidence-card ${evidenceClasses[index%5]}"><h5><span class="evidence-tag">E${index+1}</span><span class="citation">${chunk.cited?'Cited by model':'Not cited'}</span></h5><div class="provenance"><span>${textOr(chunk.document)}</span><span>${textOr(chunk.content_type)}</span><span>Section ${textOr(chunk.section_number)}</span><span>${pageLabel(chunk)}</span><span>${textOr(chunk.chunk_id)}</span><span>Similarity ${numberOr(chunk.similarity)}</span></div><div class="evidence-text">${esc(chunk.text||'')}</div></article>`).join('')}</div></div>`;
    }

    function pageLabel(chunk){if(chunk.page_start==null)return 'Pages —';return chunk.page_start===chunk.page_end?`Page ${chunk.page_start}`:`Pages ${chunk.page_start}–${chunk.page_end}`}
    function numberOr(value){return typeof value==='number'&&Number.isFinite(value)?value.toFixed(4):'—'}

    function renderCandidates(metadata,result,target) {
      if (!Array.isArray(metadata.candidates)||!metadata.candidates.length) return '';
      const related=new Set(result.related_ids||[]);
      return `<div class="section-card"><h4>Candidate comparisons</h4><div class="candidate-grid">${metadata.candidates.map((candidate,index)=>{const candidateTarget=targets[candidate.id];return `<article class="candidate-card ${related.has(candidate.id)?'confirmed':''}"><h5><span class="evidence-tag">C${index+1}</span>${esc(candidate.id||'Unknown candidate')}</h5><div class="candidate-text">${candidateTarget?esc(candidateTarget.specification):'<span class="muted">Requirement text unavailable in represented report targets.</span>'}</div><div class="detail-grid"><div class="detail"><label>Similarity</label><div>${numberOr(candidate.similarity)}</div></div><div class="detail"><label>Judgment</label><div class="judgment">${textOr(candidate.judgment)}</div></div></div><p>${textOr(candidate.reason)}</p>${candidate.prompt?`<details><summary>Candidate prompt and response</summary><p class="muted">Prompt</p><pre class="trace-block">${esc(candidate.prompt)}</pre><p class="muted">Parsed response</p><pre class="trace-block">${esc(JSON.stringify(candidate.parsed_response??{},null,2))}</pre><details><summary>Show raw response</summary><pre class="trace-block">${esc(candidate.raw_response??'No raw response')}</pre></details></details>`:''}</article>`}).join('')}</div></div>`;
    }

    function renderTrace(result) {
      const metadata=result.metadata||{}; if (!metadata.prompt&&!metadata.model&&!metadata.parsed_model_response&&!metadata.raw_model_response) return '';
      const presentation=result._presentation?.tokenized_prompt; const displayPrompt=presentation?.available?presentation.text:metadata.prompt;
      return `<div class="section-card"><h4>LLM trace</h4><div class="detail"><label>Model</label><div>${textOr(metadata.model)}</div></div>${metadata.prompt?`<p class="muted">${presentation?.available?'Tokenized display prompt':'Prompt'}</p><pre class="trace-block">${presentation?.available?coloredTokens(displayPrompt):esc(displayPrompt)}</pre>${presentation?.available?`<details><summary>Show original prompt</summary><pre class="trace-block">${esc(metadata.prompt)}</pre></details>`:''}`:''}${metadata.parsed_model_response?`<p class="muted">Parsed response</p><pre class="trace-block">${esc(JSON.stringify(metadata.parsed_model_response,null,2))}</pre>`:''}<details><summary>Show raw response</summary><pre class="trace-block">${esc(metadata.raw_model_response??'No raw response')}</pre></details></div>`;
    }

    function coloredTokens(value) {
      const safe=esc(value); return safe.replace(/&lt;E(\d+)&gt;/g,(_,number)=>{const index=(Number(number)-1)%5;return `<span class="trace-token ${evidenceClasses[index]}">&lt;E${number}&gt;</span>`});
    }

    function renderEvidence(evidence) {
      if (!Array.isArray(evidence)||!evidence.length) return '';
      return `<div class="section-card"><h4>Supporting evidence envelope</h4><div class="evidence-grid">${evidence.map((entry,index)=>`<article class="evidence-card ${evidenceClasses[index%5]}"><h5>${textOr(entry.source_type)} · ${textOr(entry.source_id)}</h5>${entry.text?`<div class="evidence-text">${esc(entry.text)}</div>`:''}<details><summary>Evidence metadata</summary><pre class="trace-block">${esc(JSON.stringify(entry.metadata||{},null,2))}</pre></details></article>`).join('')}</div></div>`;
    }

    function cleanResult(result){const clean={};Object.entries(result).forEach(([key,value])=>{if(!key.startsWith('_'))clean[key]=value});return clean}

    function setView(view){state.view=view;renderAll()}
    function renderAll(){document.querySelectorAll('.tab').forEach(tab=>tab.classList.toggle('active',tab.dataset.view===state.view));document.getElementById('matrix-view').classList.toggle('active',state.view==='matrix');document.getElementById('explorer-view').classList.toggle('active',state.view==='explorer');renderNav();if(state.view==='matrix')renderMatrix();else renderExplorer()}

    document.querySelectorAll('.tab').forEach(tab=>tab.addEventListener('click',()=>setView(tab.dataset.view)));
    document.getElementById('back-to-matrix').addEventListener('click',()=>setView('matrix'));
    document.getElementById('compare-button').addEventListener('click',()=>{state.compare=!state.compare;renderExplorer()});
    document.getElementById('matrix-search').addEventListener('input',renderMatrix);
    document.getElementById('status-filter').addEventListener('change',renderMatrix);
    renderCoverage();renderSummary();renderAll();
  })();
  </script>
</body>
</html>'''
