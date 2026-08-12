(function () {
  const questionRecords = Array.isArray(window.KNOWLEDGE_BASE_DATA) ? window.KNOWLEDGE_BASE_DATA : [];
  const knowledgeRecords = Array.isArray(window.KNOWLEDGE_POINT_DATA) ? window.KNOWLEDGE_POINT_DATA : [];
  const recordById = new Map(knowledgeRecords.map(record => [record.id, record]));
  const chapterTree = document.getElementById('chapter-tree');
  const reader = document.getElementById('knowledge-reader');
  const knowledgeSearch = document.getElementById('knowledge-search');
  const searchResults = document.getElementById('search-results');
  const searchSummary = document.getElementById('search-summary');
  const themeToggle = document.getElementById('theme-toggle');
  const themeStorageKey = 'system-architect-study-theme';
  const questionDialog = document.getElementById('question-dialog');
  const questionMeta = document.getElementById('question-meta');
  const questionTitle = document.getElementById('question-title');
  const questionState = document.getElementById('question-state');
  const questionPdf = document.getElementById('question-pdf');
  const relatedKnowledge = document.getElementById('related-knowledge');
  const openQuestionTab = document.getElementById('open-question-tab');
  const studyDialog = document.getElementById('study-dialog');
  const studyForm = document.getElementById('study-form');
  const studyState = document.getElementById('study-state');
  const studyKnowledge = document.getElementById('study-knowledge-id');
  const practiceList = document.getElementById('practice-list');
  const practiceReader = document.getElementById('practice-reader');
  const practiceState = document.getElementById('practice-state');
  const practiceFilters = {
    type: document.getElementById('practice-type'), year: document.getElementById('practice-year'),
    subject: document.getElementById('practice-subject'), source_id: document.getElementById('practice-source'),
    knowledge_id: document.getElementById('practice-knowledge'),
  };
  let practiceQuestions = [];
  let activePracticeQuestion = null;
  let practiceSession = PracticeState.createSession([]);
  let submittedPractice = null;
  const practiceQuestionCache = new Map();
  let practiceTicker = 0;
  let practiceAutoSubmitBlocked = false;
  let previewRequestId = 0;
  let previewController = null;
  const podcastStorageKey = 'system-architect-podcast-progress-v1';
  const podcastWorkspace = document.getElementById('podcast-workspace');
  const podcastList = document.getElementById('podcast-list');
  const podcastAudio = document.getElementById('podcast-audio');
  const podcastState = document.getElementById('podcast-state');
  const podcastMini = document.getElementById('podcast-mini-player');
  let podcasts = [];
  let activePodcast = null;
  let podcastProgress = readPodcastProgress();
  let lastPodcastSave = 0;

  function systemTheme() {
    try {
      return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    } catch (_) {
      return 'light';
    }
  }
  function savedTheme() {
    try {
      const theme = localStorage.getItem(themeStorageKey);
      return theme === 'dark' || theme === 'light' ? theme : null;
    } catch (_) {
      return null;
    }
  }
  function applyTheme(theme) {
    const activeTheme = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.dataset.theme = activeTheme;
    themeToggle.textContent = activeTheme === 'dark' ? '🌙 黑夜' : '☀️ 白天';
    themeToggle.setAttribute('aria-pressed', String(activeTheme === 'dark'));
    themeToggle.setAttribute('aria-label', activeTheme === 'dark' ? '切换到白天模式' : '切换到黑夜模式');
  }
  function toggleTheme() {
    const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    applyTheme(theme);
    try {
      localStorage.setItem(themeStorageKey, theme);
    } catch (_) {
      // Storage may be unavailable in private or restricted browsing contexts.
    }
  }
  function scrollToSection(id) {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function setKnowledge(id, shouldScroll) {
    if (!recordById.has(id)) return;
    if (location.hash !== `#knowledge=${encodeURIComponent(id)}`) history.pushState(null, '', `#knowledge=${encodeURIComponent(id)}`);
    renderReader(id); renderTree();
    if (shouldScroll) document.getElementById('knowledge').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  function populateStudyKnowledge() {
    knowledgeRecords.forEach(record => { const option = element('option', '', `${record.id} ${record.title}`); option.value = record.id; studyKnowledge.append(option); });
  }
  function field(name) { return studyForm.elements.namedItem(name); }
  function closeStudyDialog() { if (studyDialog.open) studyDialog.close(); }
  function openStudyRecord(context = {}) {
    if (typeof studyDialog.showModal !== 'function') { window.alert('当前浏览器不支持学习记录表单，请使用现代浏览器。'); return; }
    studyForm.reset(); studyState.textContent = '提交后会同时追加到本周档案与关联知识点专题档案。';
    field('type').value = context.type || '知识点学习';
    if (context.knowledgeId && recordById.has(context.knowledgeId)) field('knowledge_id').value = context.knowledgeId;
    else if (readHash() && recordById.has(readHash())) field('knowledge_id').value = readHash();
    else field('knowledge_id').value = knowledgeRecords[0]?.id || '';
    field('title').value = context.title || '';
    field('subject').value = context.subject || context.source || '';
    field('tags').value = context.tags || '';
    if (!studyDialog.open) studyDialog.showModal();
  }

  function readPodcastProgress() {
    try { return PodcastState.parseProgress(localStorage.getItem(podcastStorageKey)); }
    catch (_) { return PodcastState.emptyProgress(); }
  }
  function persistPodcastProgress() {
    if (!activePodcast || !activePodcast.available) return;
    const duration = Number.isFinite(podcastAudio.duration) ? podcastAudio.duration : activePodcast.duration_seconds;
    podcastProgress = PodcastState.savePosition(podcastProgress, activePodcast.chapter, podcastAudio.currentTime, duration);
    try { localStorage.setItem(podcastStorageKey, JSON.stringify(podcastProgress)); }
    catch (_) { podcastState.textContent = '当前浏览器无法保存进度，但仍可继续播放。'; }
    renderPodcastList(); updatePodcastUi();
  }
  function podcastForChapter(chapter) { return podcasts.find(item => item.chapter === String(chapter)); }
  function firstKnowledgeInChapter(chapter) { return knowledgeRecords.find(record => String(record.chapter) === String(chapter)); }
  function podcastProgressLabel(item) {
    if (!item.available) return '本章暂无播客';
    if (PodcastState.isFinished(podcastProgress, item.chapter)) return '本章已听完';
    const position = PodcastState.savedPosition(podcastProgress, item.chapter);
    return position ? `已听 ${PodcastState.formatSeconds(position)} / ${PodcastState.formatSeconds(item.duration_seconds)}` : `时长 ${PodcastState.formatSeconds(item.duration_seconds)}`;
  }
  function renderPodcastList() {
    if (!podcastList) return;
    const onlyIncomplete = document.getElementById('podcast-only-incomplete').checked;
    const visible = PodcastState.filterPodcasts(podcasts, podcastProgress, onlyIncomplete);
    podcastList.replaceChildren();
    visible.forEach(item => {
      const button = element('button', `podcast-item ${activePodcast?.chapter === item.chapter ? 'active' : ''}`); button.type = 'button';
      button.append(element('strong', '', `第${item.chapter}章 · ${item.title}`), element('span', '', podcastProgressLabel(item)));
      if (!item.available) button.classList.add('unavailable');
      button.addEventListener('click', () => selectPodcast(item.chapter, false)); podcastList.append(button);
    });
  }
  function openPodcastWorkspace() {
    podcastWorkspace.hidden = false;
    renderPodcastList();
    podcastWorkspace.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  function closePodcastWorkspace() {
    podcastWorkspace.hidden = true;
    document.getElementById('study-dashboard').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  function updatePodcastUi() {
    if (!activePodcast) return;
    const position = podcastAudio.currentTime || PodcastState.savedPosition(podcastProgress, activePodcast.chapter);
    const duration = Number.isFinite(podcastAudio.duration) ? podcastAudio.duration : activePodcast.duration_seconds;
    const view = PodcastState.playerView(activePodcast, podcastProgress, podcastAudio.paused, position, duration);
    document.getElementById('podcast-current-progress').textContent = view.progressText;
    const primary = document.getElementById('podcast-primary-action');
    primary.hidden = !view.showPrimary; primary.textContent = view.primaryText;
    podcastAudio.hidden = !view.showAudio;
    document.getElementById('podcast-record').hidden = !view.showRecord;
    document.getElementById('podcast-mini-title').textContent = `第${activePodcast.chapter}章 · ${activePodcast.title}`;
    document.getElementById('podcast-mini-status').textContent = view.miniText;
    const miniToggle = document.getElementById('podcast-mini-toggle'); miniToggle.textContent = podcastAudio.paused ? '播放' : '暂停'; miniToggle.setAttribute('aria-label', `${podcastAudio.paused ? '播放' : '暂停'}第${activePodcast.chapter}章播客`);
  }
  async function togglePodcastPlayback() {
    if (!activePodcast?.available) return;
    if (!podcastAudio.paused) { podcastAudio.pause(); return; }
    try { await podcastAudio.play(); podcastState.textContent = '正在播放；进度只保存在当前浏览器。'; }
    catch (_) { podcastState.textContent = '浏览器未允许播放。请再点击播放，或检查本机音频设置。'; }
    updatePodcastUi();
  }
  function selectPodcast(chapter, shouldPlay) {
    const item = podcastForChapter(chapter); if (!item) return;
    const changed = activePodcast?.chapter !== item.chapter;
    const wasPlaying = changed && !podcastAudio.paused;
    const keepPlaying = PodcastState.playIntentOnSelection(wasPlaying, item.available);
    if (wasPlaying) podcastAudio.pause();
    activePodcast = item;
    document.getElementById('podcast-chapter-label').textContent = `第${item.chapter}章 · ${item.available ? '本机节目' : '暂无节目'}`;
    document.getElementById('podcast-current-title').textContent = item.title;
    const canOpenKnowledge = Boolean(firstKnowledgeInChapter(item.chapter));
    document.getElementById('podcast-open-knowledge').disabled = !canOpenKnowledge;
    document.getElementById('podcast-record').disabled = !item.available || !canOpenKnowledge;
    document.getElementById('podcast-primary-action').disabled = !item.available;
    if (!item.available) {
      podcastAudio.removeAttribute('src'); podcastAudio.load(); podcastMini.hidden = true;
      podcastState.textContent = '本章暂无播客，可继续使用知识点阅读与练习。';
    } else {
      const source = `/api/podcasts/${encodeURIComponent(item.chapter)}/audio`;
      if (podcastAudio.getAttribute('src') !== source) { podcastAudio.src = source; podcastAudio.load(); }
      podcastMini.hidden = false; podcastState.textContent = '播放进度只保存在当前浏览器。';
      podcastProgress.lastChapter = item.chapter;
      try { localStorage.setItem(podcastStorageKey, JSON.stringify(podcastProgress)); } catch (_) {}
      if (shouldPlay || keepPlaying) togglePodcastPlayback();
    }
    renderPodcastList(); updatePodcastUi();
  }
  async function loadPodcasts() {
    try {
      const response = await fetch('/api/podcasts', { headers: { Accept: 'application/json' } }); const payload = await response.json();
      if (!response.ok || !Array.isArray(payload.podcasts)) throw new Error();
      podcasts = payload.podcasts; const available = podcasts.filter(item => item.available).length;
      document.getElementById('podcast-count').textContent = `${available} 期可收听 · 共 20 章；第 1、4 章暂无节目。`;
      selectPodcast(podcastForChapter(podcastProgress.lastChapter)?.chapter || podcasts.find(item => item.available)?.chapter, false);
    } catch (_) { document.getElementById('podcast-count').textContent = '未连接本地学习服务，节目库暂不可用。'; }
  }
  function addReaderPodcast(record) {
    const item = podcastForChapter(record.chapter);
    const card = element('section', `reader-podcast-card ${item?.available ? '' : 'unavailable'}`);
    if (!item?.available) { card.append(element('strong', '', '本章暂无播客'), element('span', '', '可继续使用知识点阅读与练习。')); reader.append(card); return; }
    card.append(element('strong', '', `本章播客 · ${item.title}`), element('span', '', podcastProgressLabel(item)));
    const button = element('button', 'podcast-control', PodcastState.savedPosition(podcastProgress, item.chapter) ? '继续收听' : '播放本章播客'); button.type = 'button';
    button.addEventListener('click', () => { selectPodcast(item.chapter, true); }); card.append(button); reader.append(card);
  }
  function dashboardItem(record, label) {
    const button = element('button', 'dashboard-item'); button.type = 'button';
    button.append(element('strong', '', `${record.knowledge_id} ${record.knowledge_title || ''}`));
    button.append(element('span', '', label));
    button.addEventListener('click', () => { if (recordById.has(record.knowledge_id)) setKnowledge(record.knowledge_id, true); });
    return button;
  }
  function renderDashboard(data) {
    const due = Array.isArray(data.due_reviews) ? data.due_reviews : [];
    const recent = Array.isArray(data.recent_records) ? data.recent_records : [];
    const weak = Array.isArray(data.weak_topics) ? data.weak_topics : [];
    document.getElementById('due-review-count').textContent = `${due.length} 项`;
    document.getElementById('recent-record-count').textContent = `${recent.length} 条`;
    document.getElementById('weak-topic-count').textContent = `${weak.length} 项`;
    document.getElementById('essay-material-count').textContent = `${data.essay_material_count || 0} 条`;
    const draw = (id, values, maker, empty) => { const target = document.getElementById(id); target.replaceChildren(); if (!values.length) target.append(element('p', 'muted', empty)); else values.forEach(value => target.append(maker(value))); };
    draw('due-review-list', due, item => dashboardItem(item, `应复习：${item.review_date}`), '今天没有到期复习。');
    draw('recent-record-list', recent, item => dashboardItem(item, `${item.type} · ${item.result || '未填写'}`), '近 7 天还没有记录。');
    draw('weak-topic-list', weak, item => { const button = element('button', 'dashboard-item'); button.type = 'button'; button.append(element('strong', '', `${item.knowledge_id} ${item.title}`)); button.append(element('span', '', `待强化 ${item.count} 次 · ${item.errors.join('、') || '待归因'}`)); button.addEventListener('click', () => setKnowledge(item.knowledge_id, true)); return button; }, '暂未识别出薄弱专题。');
  }
  async function refreshDashboard() {
    const state = document.getElementById('dashboard-state');
    try { const response = await fetch('/api/study/dashboard', { headers: { Accept: 'application/json' } }); if (!response.ok) throw new Error(); renderDashboard(await response.json()); state.textContent = '学习档案已读取；记录仅追加，不会覆盖手工笔记。'; }
    catch (_) { state.textContent = '未连接本地学习服务。请通过“启动知识库.py”或“本地学习服务.py”启动本站后使用记录功能。'; }
  }
  async function submitStudyRecord(event) {
    event.preventDefault(); const submit = document.getElementById('submit-study'); const payload = {};
    [...new FormData(studyForm).entries()].forEach(([key, value]) => { payload[key] = String(value); });
    submit.disabled = true; studyState.textContent = '正在追加到 Markdown 学习档案…';
    try { const response = await fetch('/api/study/records', { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify(payload) }); const result = await response.json(); if (!response.ok) throw new Error(result.error || '学习档案写入失败'); studyState.textContent = result.duplicate === 'true' ? `记录 ${result.id} 已存在，未重复追加。` : `已追加记录 ${result.id}；周报：${result.week_file}；专题：${result.topic_file}`; await refreshDashboard(); }
    catch (error) { studyState.textContent = error instanceof TypeError ? '无法连接本地学习服务，请确认通过本地服务启动网站。' : error.message; }
    finally { submit.disabled = false; }
  }
  function practiceKnowledgeLinks(container, question) {
    const wrap = element('div', 'practice-knowledge-links');
    (question.knowledge_ids || []).forEach(id => {
      if (!recordById.has(id)) return;
      const button = element('button', 'text-action', `知识点：${id} ${recordById.get(id).title}`); button.type = 'button';
      button.addEventListener('click', () => setKnowledge(id, true)); wrap.append(button);
    });
    if (wrap.childElementCount) container.append(wrap);
  }
  function practiceDuration() {
    if (!practiceSession.startedAt) return '';
    return `${Math.max(1, Math.round(((practiceSession.finishedAt || Date.now()) - practiceSession.startedAt) / 60000))} 分钟`;
  }
  function recordPractice(question, context = {}) {
    const clipped = (value, maximum) => String(value || '').slice(0, maximum);
    const knowledgeId = question.knowledge_ids?.[0] || readHash() || knowledgeRecords[0]?.id;
    const others = (question.knowledge_ids || []).slice(1).join('、');
    openStudyRecord({
      type: context.type || (question.type === 'essay' ? '论文素材' : question.type === 'case_analysis' ? '案例' : context.result === '错误' ? '错题复习' : '真题'),
      knowledgeId, title: `${question.year} ${question.subject}｜${question.title}`, subject: question.source?.label || question.subject,
    });
    field('result').value = context.result || '待复习'; field('duration').value = clipped(practiceDuration(), 40);
    field('error_type').value = clipped(context.errorType, 80); field('rule').value = clipped(context.rule, 800);
    field('missed_keywords').value = clipped(context.missedKeywords, 600); field('tags').value = others ? clipped(`关联知识点：${others}`, 300) : '';
    field('prompt_evidence').value = clipped(context.promptEvidence, 1200); field('hit_keywords').value = clipped(context.hitKeywords, 600);
    field('project_code').value = clipped(context.projectCode, 120); field('decision').value = clipped(context.decision, 1200);
    field('tradeoff').value = clipped(context.tradeoff, 1200); field('outcome').value = clipped(context.outcome, 1200);
  }
  function practiceProgress() { return PracticeState.progress(practiceSession, activePracticeQuestion?.id || ''); }
  function updatePracticeClock() {
    const elapsed = Math.max(0, Math.floor((Date.now() - practiceSession.startedAt) / 1000));
    const remaining = PracticeState.remainingSeconds(practiceSession);
    document.getElementById('practice-timer').textContent = remaining === null ? `已用 ${PracticeState.formatSeconds(elapsed)}` : `剩余 ${PracticeState.formatSeconds(remaining)}`;
    if (remaining === 0 && !practiceSession.finishedAt && !practiceAutoSubmitBlocked) finishPracticePaper();
  }
  function renderPracticeNavigation() {
    const nav = element('div', 'practice-navigation'); const progress = practiceProgress();
    document.getElementById('practice-progress').textContent = `进度 ${progress.current} / ${progress.total}`;
    const previous = element('button', 'button secondary', '← 上一题'); previous.type = 'button'; previous.disabled = !progress.previousId; previous.onclick = () => openPracticeQuestion(progress.previousId);
    const next = element('button', 'button secondary', '下一题 →'); next.type = 'button'; next.disabled = !progress.nextId; next.onclick = () => openPracticeQuestion(progress.nextId);
    nav.append(previous, element('strong', '', `第 ${progress.current} / ${progress.total} 题`), next); practiceReader.append(nav);
  }
  function addPracticeHeader(question, label) {
    practiceReader.replaceChildren();
    practiceReader.append(element('p', 'breadcrumb', `${label} · ${question.year} ${question.session} · ${question.subject}`));
    practiceReader.append(element('h3', 'point-title', question.title));
    practiceReader.append(element('p', 'source-meta', `来源：${question.source?.label || '未标注'}${question.source?.url ? '（公开来源）' : ''} · 已人工核对`));
    practiceReader.append(element('p', 'practice-stem', question.stem)); practiceKnowledgeLinks(practiceReader, question);
  }
  function addExplanation(question) {
    const details = element('details', 'practice-explanation'); details.open = true; details.append(element('summary', '', '参考答案与解析'));
    if (question.answer) details.append(element('p', '', `参考答案：${question.answer}`));
    if (question.explanation) details.append(element('p', '', question.explanation)); practiceReader.append(details);
  }
  function renderSingleChoice(question) {
    addPracticeHeader(question, '单项选择'); const form = element('form', 'choice-form');
    question.options.forEach(option => { const label = element('label', 'choice-option'); const radio = document.createElement('input'); radio.type = 'radio'; radio.name = 'practice-choice'; radio.value = option.label; radio.checked = practiceSession.answers[question.id] === option.label; radio.addEventListener('change', () => { PracticeState.setAnswer(practiceSession, question.id, option.label); renderPracticeCard(); }); label.append(radio, element('strong', '', option.label), document.createTextNode(` ${option.text}`)); form.append(label); });
    const paperMode = document.getElementById('practice-mode').value === 'paper'; const state = element('p', 'muted'); state.setAttribute('aria-live', 'polite'); const submit = element('button', 'button', paperMode ? '保存本题选择' : '提交本题'); submit.type = 'submit';
    form.append(submit, state); form.addEventListener('submit', event => { event.preventDefault(); const selected = form.querySelector('input[name="practice-choice"]:checked'); if (!selected) { state.textContent = '请选择一个选项后再提交。'; return; }
      PracticeState.setAnswer(practiceSession, question.id, selected.value); if (paperMode && !practiceSession.finishedAt) { state.textContent = '已保存到本次答题会话，交卷前不显示答案。'; renderPracticeCard(); return; }
      const correct = selected.value === question.answer; state.textContent = correct ? `回答正确：${selected.value}。` : `回答错误：你选 ${selected.value}，正确答案为 ${question.answer}。`; state.className = correct ? 'practice-result correct' : 'practice-result incorrect'; submit.disabled = true; addExplanation(question);
      const record = element('button', 'button secondary', correct ? '记录本次练习' : '记录错题复盘'); record.type = 'button'; record.addEventListener('click', () => recordPractice(question, { result: correct ? '正确' : '错误', errorType: correct ? '' : '选项判断错误', rule: question.explanation || '' })); practiceReader.append(record);
    }); practiceReader.append(form); renderPracticeNavigation();
  }
  function renderCaseAnalysis(question) {
    addPracticeHeader(question, '案例分析'); const material = element('section', 'practice-material'); material.append(element('h4', '', '案例材料'), element('p', '', question.material)); practiceReader.append(material);
    const form = element('form', 'subjective-form'); const answers = []; const saved = practiceSession.answers[question.id] || {};
    question.questions.forEach(item => { const section = element('section', 'case-question'); section.append(element('h4', '', `${item.id}（${item.score} 分）`), element('p', '', item.prompt)); const text = document.createElement('textarea'); text.name = `case-${item.id}`; text.placeholder = '按要点分条作答；提交后可对照参考要点自评。'; text.value = saved[item.id]?.text || ''; section.append(text); const rating = document.createElement('select'); rating.name = `rating-${item.id}`; [['','请选择自评'],['已覆盖','已覆盖'],['部分覆盖','部分覆盖'],['未覆盖','未覆盖']].forEach(([value,label]) => { const option = element('option', '', label); option.value = value; rating.append(option); }); rating.value = saved[item.id]?.rating || ''; const save = () => { if (!practiceSession.answers[question.id] || typeof practiceSession.answers[question.id] !== 'object') practiceSession.answers[question.id] = {}; practiceSession.answers[question.id][item.id] = { text: text.value, rating: rating.value }; renderPracticeCard(); }; text.addEventListener('input', save); rating.addEventListener('change', save); section.append(rating); answers.push({ item, text, rating }); form.append(section); });
    const submit = element('button', 'button', '保存案例自评'); submit.type = 'submit'; const state = element('p', 'muted'); state.setAttribute('aria-live', 'polite'); form.append(submit, state);
    form.addEventListener('submit', event => { event.preventDefault(); const missing = answers.filter(answer => !answer.rating.value); if (missing.length) { state.textContent = '请为每个分问选择自评状态。'; return; } submit.disabled = true; state.textContent = '已保存本次案例作答，可展开参考要点自评。'; const details = element('details', 'practice-explanation'); details.append(element('summary', '', '展开参考要点对照')); answers.forEach(answer => { const block = element('section', 'reference-points'); block.append(element('h4', '', `${answer.item.id} 参考要点`)); const list = element('ul', 'source-list'); answer.item.reference_points.forEach(point => list.append(element('li', '', point))); block.append(list); details.append(block); }); practiceReader.append(details); addExplanation(question); const record = element('button', 'button secondary', '记录案例复盘'); record.type = 'button'; record.addEventListener('click', () => { const intent = PracticeState.recordIntent(PracticeState.caseRecordIntent(question, answers.map(answer => ({ item: answer.item, text: answer.text.value, rating: answer.rating.value })))); if (intent) recordPractice(question, intent); }); practiceReader.append(record); }); practiceReader.append(form); renderPracticeNavigation();
  }
  function renderEssay(question) {
    addPracticeHeader(question, '论文训练'); const form = element('form', 'subjective-form'); const fields = [['abstract','摘要'],['project_code','项目代号'],['project','项目背景与本人职责'],['solution','架构方案'],['tradeoff','关键取舍'],['outcome','效果验证'],['body','正文 / 详细提纲']];
    const saved = practiceSession.answers[question.id] || {}; fields.forEach(([name,label]) => { const wrap = element('label', 'essay-field', label); const area = document.createElement('textarea'); area.name = name; area.placeholder = `填写${label}`; area.value = saved[name] || ''; area.addEventListener('input', () => { if (!practiceSession.answers[question.id] || typeof practiceSession.answers[question.id] !== 'object') practiceSession.answers[question.id] = {}; practiceSession.answers[question.id][name] = area.value; }); wrap.append(area); form.append(wrap); }); const submit = element('button', 'button', '保存论文提纲'); submit.type = 'submit'; const state = element('p', 'muted'); state.setAttribute('aria-live', 'polite'); form.append(submit, state);
    form.addEventListener('submit', event => { event.preventDefault(); const project = form.elements.namedItem('project').value.trim(); if (!project) { state.textContent = '请至少填写项目背景与本人职责。'; return; } submit.disabled = true; state.textContent = '论文提纲已保留在当前页面，可展开参考提纲并记录论文素材。'; const details = element('details', 'practice-explanation'); details.append(element('summary', '', '展开参考审题与提纲')); const req = element('ul', 'source-list'); question.requirements.forEach(item => req.append(element('li', '', item))); details.append(element('h4', '', '写作要求'), req); const outline = element('ul', 'source-list'); question.reference_outline.forEach(item => outline.append(element('li', '', item))); details.append(element('h4', '', '参考提纲'), outline); practiceReader.append(details); addExplanation(question); const record = element('button', 'button secondary', '记录论文素材'); record.type = 'button'; record.addEventListener('click', () => { const intent = PracticeState.recordIntent(PracticeState.essayRecordIntent(Object.fromEntries(new FormData(form).entries()))); if (intent) recordPractice(question, intent); }); practiceReader.append(record); }); practiceReader.append(form); renderPracticeNavigation();
  }
  async function loadPracticeQuestion(id) {
    const cached = practiceQuestionCache.get(id);
    if (cached) return cached;
    const response = await fetch(`/api/practice/questions/${encodeURIComponent(id)}`, { headers: { Accept: 'application/json' } });
    let payload;
    try { payload = await response.json(); }
    catch (_) { throw new Error('题目数据格式无效'); }
    if (!response.ok || !payload.question) throw new Error(payload.error || '题目加载失败');
    practiceQuestionCache.set(id, payload.question);
    return payload.question;
  }
  async function openPracticeQuestion(id) {
    if (submittedPractice) { renderSubmittedReview(id); return; }
    practiceState.textContent = '正在加载已核对题目…';
    try { const question = await loadPracticeQuestion(id); activePracticeQuestion = question; practiceState.textContent = `正在练习：${question.title}`; if (question.type === 'single_choice') renderSingleChoice(question); else if (question.type === 'case_analysis') renderCaseAnalysis(question); else renderEssay(question); renderPracticeList(); renderPracticeCard(); }
    catch (error) { practiceState.textContent = error instanceof TypeError ? '无法连接本地学习服务。' : error.message; }
  }
  function renderPracticeCard() {
    const card = document.getElementById('practice-card'); card.replaceChildren();
    if (document.getElementById('practice-mode').value !== 'paper') return;
    card.append(element('strong', '', '答题卡'));
    practiceSession.questionIds.forEach((id, index) => { const answers = submittedPractice?.answers || practiceSession.answers; const button = element('button', `practice-card-item ${answers[id] ? 'answered' : ''}`, String(index + 1)); button.type = 'button'; button.setAttribute('aria-label', `第 ${index + 1} 题${answers[id] ? '，已作答' : ''}`); button.onclick = () => submittedPractice ? renderSubmittedReview(id) : openPracticeQuestion(id); card.append(button); });
    if (submittedPractice) return;
    const finish = element('button', 'button', '交卷并查看汇总'); finish.type = 'button'; finish.onclick = finishPracticePaper; card.append(finish);
  }
  function renderPracticeSummary() {
    const summary = submittedPractice.summary; practiceReader.replaceChildren();
    practiceReader.append(element('h3', 'point-title', '本次选择题交卷汇总'), element('p', 'practice-result', `共 ${summary.total} 题，已答 ${summary.answered} 题，正确 ${summary.correct} 题，正确率 ${summary.accuracy}%。`));
    practiceReader.append(element('p', 'muted', summary.weakKnowledge.length ? `薄弱知识点：${summary.weakKnowledge.map(item => `${item.knowledgeId}（${item.count}）`).join('、')}` : '本次未识别出薄弱知识点。'));
    summary.results.forEach(result => { const details = element('details', 'practice-explanation'); details.append(element('summary', '', `${result.correct ? '✓' : '✗'} ${result.title}｜你选 ${result.selected || '未答'}｜正确 ${result.answer}`)); const review = element('button', 'text-action', '打开本题解析'); review.type = 'button'; review.onclick = () => renderSubmittedReview(result.id); details.append(review); practiceReader.append(details); });
    if (summary.results.length) { const record = element('button', 'button secondary', '记录本次整卷练习'); record.type = 'button'; record.onclick = () => { const first = practiceQuestionCache.get(summary.results[0].id); if (first) recordPractice(first, { result: summary.correct === summary.total ? '正确' : '部分完成', errorType: summary.correct === summary.total ? '' : '整卷薄弱点', rule: `正确率 ${summary.accuracy}%`, missedKeywords: summary.weakKnowledge.map(item => item.knowledgeId).join('、') }); }; practiceReader.append(record); }
    practiceState.textContent = '已交卷，可逐题查看只读解析。'; renderPracticeCard(); updatePracticeClock();
  }
  function renderSubmittedReview(questionId) {
    const review = PracticeState.reviewData(submittedPractice, questionId);
    if (!review) { practiceState.textContent = '未找到该题的交卷快照。'; return; }
    practiceReader.replaceChildren(element('p', 'breadcrumb', '交卷后只读复盘'), element('h3', 'point-title', review.title));
    const form = element('form', 'choice-form');
    review.options.forEach(option => { const label = element('label', `choice-option${option.correct ? ' correct' : option.selected ? ' incorrect' : ''}`); const radio = document.createElement('input'); radio.type = 'radio'; radio.name = 'submitted-practice-choice'; radio.disabled = true; radio.checked = option.selected; label.append(radio, element('strong', '', option.label), document.createTextNode(` ${option.text}`)); if (option.selected) label.append(element('span', 'muted', '（你的选择）')); if (option.correct) label.append(element('span', 'muted', '（正确答案）')); form.append(label); });
    practiceReader.append(form, element('p', review.correct ? 'practice-result correct' : 'practice-result incorrect', review.correct ? `回答正确：${review.selected}。` : `回答错误：你选 ${review.selected || '未答'}，正确答案为 ${review.answer}。`));
    const details = element('details', 'practice-explanation'); details.open = true; details.append(element('summary', '', '参考答案与解析'), element('p', '', `参考答案：${review.answer}`), element('p', '', review.explanation || '暂无解析。')); practiceReader.append(details);
    const back = element('button', 'button secondary', '返回交卷汇总'); back.type = 'button'; back.onclick = renderPracticeSummary; practiceReader.append(back); practiceState.textContent = `只读复盘：${review.title}`; renderPracticeCard();
  }
  async function finishPracticePaper() {
    if (document.getElementById('practice-mode').value !== 'paper' || practiceSession.finishedAt) return;
    practiceSession.finishedAt = Date.now(); clearInterval(practiceTicker);
    try { const questions = await Promise.all(practiceSession.questionIds.map(loadPracticeQuestion)); submittedPractice = PracticeState.submitSnapshot(practiceSession, questions, practiceSession.finishedAt); renderPracticeSummary(); }
    catch (error) { practiceSession.finishedAt = 0; submittedPractice = null; practiceAutoSubmitBlocked = true; clearInterval(practiceTicker); practiceTicker = window.setInterval(updatePracticeClock, 1000); practiceState.textContent = `交卷失败：${error instanceof TypeError ? '无法连接本地学习服务' : error.message || '题目加载失败'}，请点击交卷按钮重试。`; renderPracticeCard(); }
  }
  function startPracticeSession() {
    const mode = document.getElementById('practice-mode').value; const ids = practiceQuestions.filter(item => mode !== 'paper' || item.type === 'single_choice').map(item => item.id);
    practiceSession = PracticeState.createSession(ids, document.getElementById('practice-limit').value); submittedPractice = null; practiceAutoSubmitBlocked = false; activePracticeQuestion = null; practiceQuestionCache.clear(); clearInterval(practiceTicker); practiceTicker = window.setInterval(updatePracticeClock, 1000); updatePracticeClock(); renderPracticeCard(); renderPracticeList();
    if (ids[0]) openPracticeQuestion(ids[0]); else practiceReader.replaceChildren(element('p', 'muted', mode === 'paper' ? '当前筛选没有选择题。' : '当前筛选没有题目。'));
  }
  function renderPracticeList() { practiceList.replaceChildren(); if (!practiceQuestions.length) { practiceList.append(element('p', 'muted', '当前筛选没有已核对题目。')); return; } practiceQuestions.forEach(item => { const button = element('button', `practice-item ${activePracticeQuestion?.id === item.id ? 'active' : ''}`); button.type = 'button'; button.append(element('strong', '', item.title), element('span', '', `${item.year} · ${item.subject} · ${item.type === 'single_choice' ? '选择题' : item.type === 'case_analysis' ? '案例' : '论文'}`)); button.addEventListener('click', () => openPracticeQuestion(item.id)); practiceList.append(button); }); }
  async function loadPracticeQuestions() { const params = new URLSearchParams(); Object.entries(practiceFilters).forEach(([key, control]) => { if (control.value) params.set(key, control.value); }); try { const response = await fetch(`/api/practice/questions?${params.toString()}`, { headers: { Accept: 'application/json' } }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || '题库筛选失败'); practiceQuestions = payload.questions || []; submittedPractice = null; practiceAutoSubmitBlocked = false; activePracticeQuestion = null; practiceReader.replaceChildren(element('p', 'muted', '选择左侧题目，或设置整卷模式后开始。')); practiceState.textContent = `已加载 ${payload.count || 0} 道已核对题目。`; clearInterval(practiceTicker); practiceSession = PracticeState.createSession(practiceQuestions.map(item => item.id)); practiceTicker = window.setInterval(updatePracticeClock, 1000); updatePracticeClock(); renderPracticeList(); renderPracticeCard(); } catch (error) { practiceState.textContent = error instanceof TypeError ? '无法连接本地学习服务。' : error.message; } }
  async function loadPracticeCatalog() { try { const response = await fetch('/api/practice/catalog', { headers: { Accept: 'application/json' } }); const catalog = await response.json(); if (!response.ok) throw new Error('题库目录读取失败'); (catalog.years || []).forEach(value => { const option = element('option', '', value); option.value = value; practiceFilters.year.append(option); }); (catalog.subjects || []).forEach(value => { const option = element('option', '', value); option.value = value; practiceFilters.subject.append(option); }); (catalog.sources || []).forEach(value => { const option = element('option', '', value.label || value.source_id); option.value = value.source_id; practiceFilters.source_id.append(option); }); knowledgeRecords.forEach(record => { const option = element('option', '', `${record.id} ${record.title}`); option.value = record.id; practiceFilters.knowledge_id.append(option); }); Object.values(practiceFilters).forEach(control => control.addEventListener('change', loadPracticeQuestions)); document.getElementById('practice-start').addEventListener('click', startPracticeSession); await loadPracticeQuestions(); } catch (_) { practiceState.textContent = '未连接本地学习服务，互动题库不可用。'; } }
  function readHash() {
    const matched = location.hash.match(/^#knowledge=(.+)$/);
    return matched ? decodeURIComponent(matched[1]) : null;
  }
  function pointButton(record, extraClass) {
    const button = element('button', `tree-point ${extraClass || ''}`, `${record.id} ${record.title}`);
    button.type = 'button'; button.dataset.knowledgeId = record.id;
    button.addEventListener('click', () => setKnowledge(record.id, true));
    return button;
  }
  function renderTree() {
    const selected = readHash() || knowledgeRecords[0]?.id;
    chapterTree.replaceChildren();
    const byChapter = new Map();
    knowledgeRecords.forEach(record => { if (!byChapter.has(record.chapter)) byChapter.set(record.chapter, []); byChapter.get(record.chapter).push(record); });
    byChapter.forEach((chapterRecords, chapter) => {
      const details = element('details', 'chapter-node'); details.open = selected?.startsWith(`${chapter}.`);
      const title = element('summary', '', `第${chapter}章 ${chapterRecords[0].chapter_title}`); details.append(title);
      const sectionMap = new Map();
      chapterRecords.forEach(record => { if (!sectionMap.has(record.section)) sectionMap.set(record.section, []); sectionMap.get(record.section).push(record); });
      sectionMap.forEach((sectionRecords, section) => {
        const sectionNode = element('div', 'section-node');
        sectionNode.append(element('p', 'section-title', `${section} ${sectionRecords[0].section_title}`));
        sectionRecords.forEach(record => sectionNode.append(pointButton(record, record.id === selected ? 'active' : '')));
        details.append(sectionNode);
      });
      chapterTree.append(details);
    });
  }
  function addList(container, values) { const list = element('ul', 'source-list'); values.forEach(value => list.append(element('li', '', value))); container.append(list); }
  function addExamUse(container, label, text) { const card = element('section', 'exam-card'); card.append(element('h4', '', label)); card.append(element('p', '', text)); container.append(card); }
  function navButton(label, targetId) { const button = element('button', 'nav-point', label); button.type = 'button'; button.disabled = !targetId; if (targetId) button.addEventListener('click', () => setKnowledge(targetId, true)); return button; }
  function renderReader(id) {
    const record = recordById.get(id) || knowledgeRecords[0]; if (!record) { reader.textContent = '暂无可用知识点数据。'; return; }
    reader.replaceChildren();
    reader.append(element('p', 'breadcrumb', `第${record.chapter}章 ${record.chapter_title}  ·  ${record.section} ${record.section_title}`));
    reader.append(element('h3', 'point-title', `${record.id} ${record.title}`));
    addReaderPodcast(record);
    const summary = element('section', 'summary-card'); summary.append(element('h4', '', '核心结论')); summary.append(element('p', '', record.summary)); reader.append(summary);
    reader.append(element('h4', 'reader-heading', '结构化理解'));
    const structured = element('div', 'structured-grid'); Object.entries(record.structured).forEach(([label, text]) => { const card = element('section', 'structured-card'); card.append(element('h4', '', label)); card.append(element('p', '', text)); structured.append(card); }); reader.append(structured);
    reader.append(element('h4', 'reader-heading', '易错与答题'));
    const exam = element('div', 'exam-grid'); Object.entries(record.exam_use).forEach(([label, text]) => addExamUse(exam, label, text)); reader.append(exam);
    const details = element('details', 'source-details'); details.append(element('summary', '', '展开教材原文要点（文字层整理）')); details.append(element('p', 'source-note', '以下内容完整保留当前工作区教材 PDF 可提取文字，并已按句子分段；图、表、公式图片请回源 PDF 核对。')); addList(details, record.source_paragraphs.length ? record.source_paragraphs : ['本节未提取到可识别教材文字；请回源 PDF 核对。']); reader.append(details);
    const meta = element('p', 'source-meta', `来源：${record.chapter_source}`); reader.append(meta);
    const navigation = element('div', 'point-navigation'); navigation.append(navButton('← 上一知识点', record.prevId)); navigation.append(navButton('下一知识点 →', record.nextId)); reader.append(navigation);
    const studyButton = element('button', 'button secondary', '记录学习 / 错题'); studyButton.type = 'button'; studyButton.addEventListener('click', () => openStudyRecord({ type: '知识点学习', knowledgeId: record.id, title: `${record.id} ${record.title}` })); reader.append(studyButton);
  }
  function searchKnowledge() {
    const needle = knowledgeSearch.value.trim().toLocaleLowerCase(); searchResults.replaceChildren();
    if (!needle) { searchSummary.textContent = `共 ${knowledgeRecords.length} 个可直接学习的知识点；可从左侧章节树选择。`; return; }
    const matches = knowledgeRecords.filter(record => [record.id, record.title, record.summary, record.tags.join(' '), record.source_paragraphs.join(' ')].join('\n').toLocaleLowerCase().includes(needle)).slice(0, 40);
    searchSummary.textContent = `“${knowledgeSearch.value.trim()}”找到 ${matches.length}${matches.length === 40 ? '+' : ''} 个知识点。`;
    matches.forEach(record => { const button = element('button', 'search-result', ''); button.type = 'button'; button.append(element('strong', '', `${record.id} ${record.title}`)); button.append(element('span', '', record.summary)); button.addEventListener('click', () => setKnowledge(record.id, true)); searchResults.append(button); });
  }
  function clearQuestionPreview() {
    questionPdf.removeAttribute('src');
    openQuestionTab.removeAttribute('href');
    openQuestionTab.hidden = true;
  }
  function invalidateQuestionPreview() {
    previewRequestId += 1;
    if (previewController) previewController.abort();
    previewController = null;
    clearQuestionPreview();
  }
  function isCurrentPreview(id, requestId) {
    return requestId === previewRequestId && questionDialog.open && questionDialog.dataset.questionId === id;
  }
  function openPdfFallback(pdfUrl) {
    openQuestionTab.href = pdfUrl;
    openQuestionTab.hidden = false;
    const popup = window.open(pdfUrl, '_blank', 'noopener');
    const message = popup
      ? '当前浏览器不支持站内预览，已在新标签打开受控 PDF。'
      : '当前浏览器不支持站内预览，且新标签可能被拦截；请允许弹窗后重试。';
    setQuestionState(message);
    window.alert(message);
  }
  function setQuestionState(message) { questionState.textContent = message; }
  function renderRelatedKnowledge(matches) {
    relatedKnowledge.replaceChildren();
    if (!Array.isArray(matches) || !matches.length) {
      relatedKnowledge.append(element('p', 'muted', '未从已提取的题目文字中匹配到知识点。你仍可阅读题目后使用上方知识点搜索。'));
      return;
    }
    matches.forEach(match => {
      const button = element('button', 'related-knowledge-card');
      button.type = 'button';
      button.append(element('strong', '', `${match.id} ${match.title}`));
      if (Array.isArray(match.reasons) && match.reasons.length) button.append(element('span', 'match-reasons', `命中：${match.reasons.join('、')}`));
      if (match.summary) button.append(element('span', 'match-summary', match.summary));
      button.addEventListener('click', () => {
        setKnowledge(match.id, true);
        questionDialog.close();
      });
      relatedKnowledge.append(button);
    });
  }
  async function openQuestion(id) {
    const encodedId = encodeURIComponent(id);
    const pdfUrl = `/api/questions/${encodedId}/pdf`;
    invalidateQuestionPreview();
    const requestId = previewRequestId;
    previewController = new AbortController();
    const localRecord = questionRecords.find(item => item.id === id);
    questionDialog.dataset.questionId = id;
    questionMeta.textContent = localRecord ? `${localRecord.year} · ${localRecord.session} · ${localRecord.subject} · ${localRecord.material_type} · ${localRecord.status}` : '正在加载真题信息';
    questionTitle.textContent = localRecord ? localRecord.title : '真题预览';
    clearQuestionPreview();
    relatedKnowledge.replaceChildren();
    setQuestionState('正在获取题目预览与关联知识点…');
    if (typeof questionDialog.showModal !== 'function') {
      openPdfFallback(pdfUrl);
      return;
    }
    try {
      if (!questionDialog.open) questionDialog.showModal();
    } catch (error) {
      openPdfFallback(pdfUrl);
      return;
    }
    try {
      const response = await fetch(`/api/questions/${encodedId}`, { headers: { Accept: 'application/json' }, signal: previewController.signal });
      if (!isCurrentPreview(id, requestId)) return;
      if (!response.ok) {
        if (response.status === 404) throw new Error('未获取到受控真题接口。请确认通过“启动知识库.py”或“本地学习服务.py”启动本站；若服务已启动，则该题目文件可能未登记或已不存在。');
        throw new Error(`本地学习服务返回 HTTP ${response.status}，暂时无法提供该题目。`);
      }
      let payload;
      try { payload = await response.json(); } catch (error) { throw new Error('本地学习服务返回的数据格式异常，无法显示题目关联结果。'); }
      if (!isCurrentPreview(id, requestId)) return;
      questionMeta.textContent = [payload.year, payload.session, payload.subject, payload.material_type, payload.status].filter(Boolean).join(' · ') || questionMeta.textContent;
      questionTitle.textContent = payload.title || questionTitle.textContent;
      questionPdf.src = pdfUrl;
      openQuestionTab.href = pdfUrl;
      openQuestionTab.hidden = false;
      renderRelatedKnowledge(payload.matches);
      document.getElementById('record-question').onclick = () => openStudyRecord({ type: '真题', knowledgeId: payload.matches?.[0]?.id || readHash() || knowledgeRecords[0]?.id, title: payload.title || '', subject: [payload.year, payload.subject].filter(Boolean).join(' · ') });
      const textStatus = payload.text_status || '题目预览已加载。';
      setQuestionState(Array.isArray(payload.matches) && payload.matches.length ? `${textStatus} 已匹配到 ${payload.matches.length} 个关联知识点。` : `${textStatus} 未匹配到关联知识点。`);
    } catch (error) {
      if (!isCurrentPreview(id, requestId) || error?.name === 'AbortError') return;
      const isNetworkError = error instanceof TypeError;
      setQuestionState(isNetworkError ? '无法连接本地学习服务。请通过“启动知识库.py”或“本地学习服务.py”启动本站后重试。' : error.message);
      relatedKnowledge.replaceChildren();
      relatedKnowledge.append(element('p', 'muted', '预览不可用时，可先从知识点阅读器继续学习。'));
    }
  }
  function unique(key) { return [...new Set(questionRecords.map(x => x[key]).filter(Boolean))].sort((a, b) => String(b).localeCompare(String(a), 'zh-CN')); }
  function options(select, values) { values.forEach(value => { const option = element('option', '', value); option.value = value; select.append(option); }); }
  function setupQuestions() {
    const year = document.getElementById('year-filter'); const subject = document.getElementById('subject-filter'); const type = document.getElementById('type-filter'); const list = document.getElementById('question-list'); const summary = document.getElementById('filter-summary'); const template = document.getElementById('record-template');
    function filtered() { return questionRecords.filter(item => (!year.value || item.year === year.value) && (!subject.value || item.subject === subject.value) && (!type.value || item.material_type === type.value)); }
    function render() { const items = filtered(); list.replaceChildren(); summary.textContent = `显示 ${items.length} / ${questionRecords.length} 条本机索引记录。`; items.forEach(item => { const node = template.content.cloneNode(true); const tags = node.querySelectorAll('.tag'); tags[0].textContent = item.year; tags[1].textContent = item.subject; tags[2].textContent = item.material_type; node.querySelector('h3').textContent = item.title; node.querySelector('.session').textContent = `${item.session} · ${item.status}`; node.querySelector('.open-question').addEventListener('click', () => openQuestion(item.id)); list.append(node); }); }
    options(year, unique('year')); options(subject, unique('subject')); options(type, unique('material_type')); [year, subject, type].forEach(select => select.addEventListener('change', render)); render();
  }
  function countdown() { const target = new Date('2026-10-24T00:00:00+08:00'); document.getElementById('countdown').textContent = `${Math.max(0, Math.ceil((target - new Date()) / 86400000))} 天`; }
  applyTheme(savedTheme() || systemTheme());
  themeToggle.addEventListener('click', toggleTheme);
  knowledgeSearch.addEventListener('input', searchKnowledge);
  document.getElementById('close-question').addEventListener('click', () => questionDialog.close());
  document.getElementById('close-study').addEventListener('click', closeStudyDialog);
  studyForm.addEventListener('submit', submitStudyRecord);
  document.getElementById('record-case').addEventListener('click', () => openStudyRecord({ type: '案例', title: '案例分析复盘', subject: '案例分析' }));
  document.getElementById('record-essay').addEventListener('click', () => openStudyRecord({ type: '论文素材', title: '论文项目素材', subject: '论文' }));
  document.getElementById('record-essay-material').addEventListener('click', () => openStudyRecord({ type: '论文素材', title: '论文项目素材', subject: '论文' }));
  document.getElementById('mission-review').addEventListener('click', () => scrollToSection('study-dashboard'));
  document.getElementById('mission-practice').addEventListener('click', () => scrollToSection('practice'));
  document.getElementById('mission-rule').addEventListener('click', () => openStudyRecord({ type: '知识点学习' }));
  document.getElementById('open-podcast-workspace').addEventListener('click', openPodcastWorkspace);
  document.getElementById('close-podcast-workspace').addEventListener('click', closePodcastWorkspace);
  document.getElementById('podcast-only-incomplete').addEventListener('change', renderPodcastList);
  document.getElementById('podcast-primary-action').addEventListener('click', togglePodcastPlayback);
  document.getElementById('podcast-mini-toggle').addEventListener('click', togglePodcastPlayback);
  document.getElementById('podcast-mini-expand').addEventListener('click', openPodcastWorkspace);
  document.getElementById('podcast-open-knowledge').addEventListener('click', () => { const record = firstKnowledgeInChapter(activePodcast?.chapter); if (record) setKnowledge(record.id, true); });
  document.getElementById('podcast-record').addEventListener('click', () => { const record = firstKnowledgeInChapter(activePodcast?.chapter); if (!record || !activePodcast?.available) return; openStudyRecord({ type: '知识点学习', knowledgeId: record.id, title: `第${activePodcast.chapter}章播客｜${activePodcast.title}`, subject: '章节播客', tags: `章节播客、第${activePodcast.chapter}章` }); });
  podcastAudio.addEventListener('loadedmetadata', () => { const position = PodcastState.savedPosition(podcastProgress, activePodcast?.chapter); if (position && position < podcastAudio.duration - 5) podcastAudio.currentTime = position; updatePodcastUi(); });
  podcastAudio.addEventListener('play', updatePodcastUi);
  podcastAudio.addEventListener('pause', () => { persistPodcastProgress(); updatePodcastUi(); });
  podcastAudio.addEventListener('ended', () => { persistPodcastProgress(); updatePodcastUi(); podcastState.textContent = '本章已听完；可重播或主动记录复盘。'; });
  podcastAudio.addEventListener('error', () => { if (activePodcast?.available) podcastState.textContent = '本机播客文件不可用，你仍可进入本章知识点。'; });
  podcastAudio.addEventListener('timeupdate', () => { updatePodcastUi(); if (Date.now() - lastPodcastSave >= 5000) { lastPodcastSave = Date.now(); persistPodcastProgress(); } });
  document.addEventListener('visibilitychange', () => { if (document.hidden) persistPodcastProgress(); });
  questionDialog.addEventListener('close', invalidateQuestionPreview);
  questionDialog.addEventListener('cancel', invalidateQuestionPreview);
  window.addEventListener('popstate', () => { const id = readHash(); if (recordById.has(id)) { renderReader(id); renderTree(); } });
  document.getElementById('record-count').textContent = questionRecords.length; populateStudyKnowledge(); countdown(); setupQuestions(); renderTree(); loadPodcasts().finally(() => renderReader(recordById.has(readHash()) ? readHash() : knowledgeRecords[0]?.id)); searchKnowledge(); refreshDashboard(); loadPracticeCatalog();
}());
