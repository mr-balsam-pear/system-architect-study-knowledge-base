(function (root) {
  let view; let context; let records = []; let byId; let activeId = ''; let expanded = [];
  let sidebarCollapsed = false; let mobileRailOpen = false; let railReturnFocus = null;
  const el = (tag, cls, text) => { const node = document.createElement(tag); if (cls) node.className = cls; if (text !== undefined) node.textContent = text; return node; };

  function syncRail() {
    if (!view) return;
    const toggle = view.querySelector('[data-knowledge-rail-toggle]');
    const mobile = matchMedia('(max-width: 48rem)').matches;
    view.classList.toggle('is-rail-collapsed', !mobile && sidebarCollapsed);
    view.classList.toggle('is-mobile-rail-open', mobile && mobileRailOpen);
    toggle.setAttribute('aria-expanded', String(mobile ? mobileRailOpen : !sidebarCollapsed));
    toggle.textContent = mobile ? (mobileRailOpen ? '关闭目录' : '章节目录') : (sidebarCollapsed ? '展开目录' : '收起目录');
  }
  function closeMobileRail() { if (!mobileRailOpen) return; mobileRailOpen = false; syncRail(); railReturnFocus?.focus(); }
  function toggleRail(event) {
    if (matchMedia('(max-width: 48rem)').matches) { railReturnFocus = event.currentTarget; mobileRailOpen = !mobileRailOpen; }
    else sidebarCollapsed = !sidebarCollapsed;
    syncRail();
  }
  function selectKnowledge(id, scroll = false) { if (!byId.has(id)) return; activeId = id; renderTree(); renderReader(); closeMobileRail(); if (scroll) view.querySelector('.knowledge-reader')?.scrollIntoView({ block: 'start' }); }
  function renderTree() {
    const target = view.querySelector('.chapter-tree'); target.replaceChildren(); const chapters = new Map();
    records.forEach(item => { if (!chapters.has(item.chapter)) chapters.set(item.chapter, []); chapters.get(item.chapter).push(item); });
    chapters.forEach((items, chapter) => { const details = el('details', 'chapter-node'); details.open = expanded.includes(chapter) || activeId.startsWith(`${chapter}.`); details.addEventListener('toggle', () => { expanded = [...target.querySelectorAll('details[open]')].map(item => item.dataset.chapter); }); details.dataset.chapter = chapter; details.append(el('summary', '', `第${chapter}章 ${items[0].chapter_title}`)); const list = el('div', 'chapter-points'); items.forEach(item => { const button = el('button', `tree-point${item.id === activeId ? ' active' : ''}`, `${item.id} ${item.title}`); button.type = 'button'; button.addEventListener('click', () => selectKnowledge(item.id, true)); list.append(button); }); details.append(list); target.append(details); });
  }
  function renderReader() {
    const item = byId.get(activeId) || records[0]; const target = view.querySelector('.knowledge-reader'); target.replaceChildren(); if (!item) { target.textContent = '暂无知识点数据。'; return; }
    target.append(el('p', 'breadcrumb', `第${item.chapter}章 ${item.chapter_title} · ${item.section} ${item.section_title}`), el('h2', 'point-title', `${item.id} ${item.title}`));
    const actions = el('div', 'action-row'); const record = el('button', 'button secondary', '记录学习'); record.type = 'button'; record.onclick = event => context.dialogs.openStudyRecord({ type: '知识点学习', knowledgeId: item.id, title: `${item.id} ${item.title}` }, event.currentTarget); const audio = el('button', 'quiet-action', '收听本章'); audio.type = 'button'; audio.onclick = () => { context.podcast.selectChapter(String(item.chapter)); context.navigate('podcasts'); }; actions.append(record, audio); target.append(actions);
    const summary = el('section', 'summary-card'); summary.append(el('h3', '', '核心结论'), el('p', '', item.summary)); target.append(summary);
    if (item.outline) { const outline = el('section', 'outline-card'); outline.append(el('h3', '', '考纲要求'), el('p', '', item.outline), el('p', 'outline-note', '摘自《系统架构设计师考试大纲》，用于对照复习范围。')); target.append(outline); }
    const structured = el('div', 'structured-grid'); Object.entries(item.structured || {}).forEach(([label, text]) => { const card = el('section', 'structured-card'); card.append(el('h3', '', label), el('p', '', text)); structured.append(card); }); target.append(el('h3', 'reader-heading', '结构化理解'), structured);
    const exam = el('div', 'exam-grid'); Object.entries(item.exam_use || {}).forEach(([label, text]) => { const card = el('section', 'exam-card'); card.append(el('h3', '', label), el('p', '', text)); exam.append(card); }); target.append(el('h3', 'reader-heading', '考试使用'), exam);
    const source = el('details', 'source-details'); source.append(el('summary', '', '展开教材文字层')); const list = el('ul', 'source-list'); (item.source_paragraphs || []).forEach(text => list.append(el('li', '', text))); source.append(list); target.append(source, el('p', 'source-meta', `来源：${item.chapter_source}`));
    const nav = el('div', 'point-navigation'); [['← 上一知识点', item.prevId], ['下一知识点 →', item.nextId]].forEach(([label, id]) => { const button = el('button', 'nav-point', label); button.disabled = !id; button.onclick = () => selectKnowledge(id, true); nav.append(button); }); target.append(nav);
  }
  function search() { const input = view.querySelector('[type=search]'); const needle = input.value.trim().toLocaleLowerCase(); const results = view.querySelector('.search-results'); results.replaceChildren(); const matches = needle ? records.filter(item => [item.id, item.title, item.summary, ...(item.tags || []), ...(item.source_paragraphs || [])].join(' ').toLocaleLowerCase().includes(needle)).slice(0, 30) : []; view.querySelector('.search-summary').textContent = needle ? `找到 ${matches.length}${matches.length === 30 ? '+' : ''} 个知识点` : `共 ${records.length} 个可直接学习的知识点`; matches.forEach(item => { const button = el('button', 'search-result'); button.append(el('strong', '', `${item.id} ${item.title}`), el('span', '', item.summary)); button.onclick = () => selectKnowledge(item.id, true); results.append(button); }); }

  root.KnowledgeWorkspace = { mount(container, nextContext) { context = nextContext; records = context.knowledgeRecords; byId = new Map(records.map(item => [item.id, item])); const saved = context.state.read('knowledge'); activeId = byId.has(saved.activeId) ? saved.activeId : records[0]?.id; expanded = saved.expandedChapters || []; sidebarCollapsed = saved.sidebarCollapsed === true; mobileRailOpen = false;
    view = el('section', 'workspace-view knowledge-workspace'); view.innerHTML = `<header class="workspace-heading workspace-heading-compact"><p class="eyebrow">TEXTBOOK FIRST · ${records.length} POINTS</p><h1>知识点阅读器</h1><p>从章节树进入正文；搜索覆盖标题、摘要、标签与教材文字层。</p></header><div class="knowledge-toolbar"><button type="button" class="rail-toggle quiet-action" data-knowledge-rail-toggle aria-controls="knowledge-rail" aria-expanded="true">收起目录</button><label class="search-field">搜索知识点<input type="search" autocomplete="off" placeholder="ATAM、黑板系统、微服务"></label></div><p class="search-summary" aria-live="polite"></p><div class="search-results"></div><div class="reader-layout"><aside id="knowledge-rail" class="chapter-tree-wrap" aria-label="章节目录"><div class="rail-heading"><strong>章节目录</strong><button type="button" data-mobile-rail-close aria-label="关闭章节目录">关闭</button></div><div class="chapter-tree"></div></aside><button type="button" class="rail-backdrop" aria-label="关闭章节目录"></button><article class="knowledge-reader" aria-live="polite"></article></div>`; container.append(view); const input = view.querySelector('[type=search]'); input.value = saved.query || ''; input.addEventListener('input', search); view.querySelector('[data-knowledge-rail-toggle]').addEventListener('click', toggleRail); view.querySelector('[data-mobile-rail-close]').addEventListener('click', closeMobileRail); view.querySelector('.rail-backdrop').addEventListener('click', closeMobileRail); view.addEventListener('keydown', event => { if (event.key === 'Escape') closeMobileRail(); }); renderTree(); renderReader(); search(); syncRail(); requestAnimationFrame(() => { view.querySelector('.knowledge-reader').scrollTop = saved.scrollTop || 0; }); },
    unmount() { if (view) context.state.patch('knowledge', { activeId, query: view.querySelector('[type=search]').value, expandedChapters: expanded, scrollTop: view.querySelector('.knowledge-reader').scrollTop, sidebarCollapsed }); mobileRailOpen = false; view = null; }, selectKnowledge };
}(globalThis));
