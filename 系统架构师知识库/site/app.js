(function () {
  const workspaceRoot = document.getElementById('workspace-root');
  const themeStorageKey = 'system-architect-study-theme';
  const state = WorkspaceState.createStore();
  const workspaces = new Map();
  let active = null;
  let renderEpoch = 0;

  const titles = {
    today: '今日指挥台', knowledge: '知识点阅读器', practice: '互动题库',
    questions: '本机真题', 'question-detail': '真题详情', training: '训练中心',
    podcasts: '章节播客', records: '学习档案',
  };

  function stub(name) {
    return {
      mount(container) {
        const view = document.createElement('section');
        view.className = 'workspace-stub';
        view.innerHTML = `<p class="eyebrow">NIGHT COMMAND / WORKSPACE</p><h1>${titles[name]}</h1><p>工作区正在迁移，应用壳与路由已经可用。</p>`;
        container.append(view);
      },
      unmount() {},
    };
  }

  function register(name, workspace) { workspaces.set(name, workspace || stub(name)); }
  function updateActiveNavigation(name) {
    document.querySelectorAll('[data-route]').forEach(link => {
      if (link.dataset.route === name) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
  }
  function navigate(name, params) { location.hash = AppRouter.toHash(name, params); }

  const dialogs = Dialogs.createDialogController(document.getElementById('study-dialog'), Array.isArray(window.KNOWLEDGE_POINT_DATA) ? window.KNOWLEDGE_POINT_DATA : []);
  function createPodcastController() {
    const audio = document.getElementById('podcast-audio'); const mini = document.getElementById('podcast-mini-player'); const storageKey = 'system-architect-podcast-progress-v1';
    let catalog = []; let activeEpisode = null; let progress; let loading = null; const listeners = new Set(); let lastSave = 0;
    try { progress = PodcastState.parseProgress(localStorage.getItem(storageKey)); } catch (_) { progress = PodcastState.emptyProgress(); }
    function save() { if (!activeEpisode?.available) return; const duration = Number.isFinite(audio.duration) ? audio.duration : activeEpisode.duration_seconds; progress = PodcastState.savePosition(progress, activeEpisode.chapter, audio.currentTime, duration); try { localStorage.setItem(storageKey, JSON.stringify(progress)); } catch (_) {} }
    function snapshot() { const view = activeEpisode ? PodcastState.playerView(activeEpisode, progress, audio.paused, audio.currentTime || PodcastState.savedPosition(progress, activeEpisode.chapter), Number.isFinite(audio.duration) ? audio.duration : activeEpisode.duration_seconds) : null; return { catalog: [...catalog], active: activeEpisode ? { ...activeEpisode } : null, progress: PodcastState.parseProgress(progress), view }; }
    function emit() { const data = snapshot(); listeners.forEach(listener => listener(data)); if (!data.active?.available) { mini.hidden = true; return; } mini.hidden = false; mini.innerHTML = `<div><strong></strong><span></span></div><button type="button" class="mini-toggle"></button><a href="#/podcasts">节目库</a>`; mini.querySelector('strong').textContent = `第${data.active.chapter}章 · ${data.active.title}`; mini.querySelector('span').textContent = data.view.miniText; mini.querySelector('button').textContent = data.view.playing ? '暂停' : '播放'; mini.querySelector('button').onclick = toggle; }
    async function load() { if (!loading) loading = fetch('/api/podcasts', { headers: { Accept: 'application/json' } }).then(response => { if (!response.ok) throw new Error('节目目录读取失败'); return response.json(); }).then(payload => { catalog = payload.podcasts || []; if (!activeEpisode) selectChapter(progress.lastChapter || catalog.find(item => item.available)?.chapter); return catalog; }).catch(() => { catalog = []; return catalog; }); return loading; }
    function list() { return [...catalog]; }
    function selectChapter(chapter) { const item = catalog.find(entry => entry.chapter === String(chapter)); if (!item) { load().then(() => selectChapter(chapter)); return; } const changed = activeEpisode?.chapter !== item.chapter; if (changed && !audio.paused) { save(); audio.pause(); } activeEpisode = item; if (item.available) { const src = `/api/podcasts/${encodeURIComponent(item.chapter)}/audio`; if (audio.getAttribute('src') !== src) { audio.src = src; audio.load(); } progress.lastChapter = item.chapter; try { localStorage.setItem(storageKey, JSON.stringify(progress)); } catch (_) {} } emit(); }
    async function toggle() { if (!activeEpisode?.available) return; if (audio.paused) { try { await audio.play(); } catch (_) {} } else audio.pause(); emit(); }
    function subscribe(listener) { listeners.add(listener); listener(snapshot()); return () => listeners.delete(listener); }
    function openKnowledge(chapter) { const record = context.knowledgeRecords.find(item => String(item.chapter) === String(chapter)); if (record) { state.patch('knowledge', { activeId: record.id }); navigate('knowledge'); } }
    function record(trigger) { const record = context.knowledgeRecords.find(item => String(item.chapter) === String(activeEpisode?.chapter)); if (record && activeEpisode) dialogs.openStudyRecord({ type: '知识点学习', knowledgeId: record.id, title: `第${activeEpisode.chapter}章播客｜${activeEpisode.title}`, subject: '章节播客', tags: `第${activeEpisode.chapter}章` }, trigger); }
    audio.addEventListener('loadedmetadata', () => { const position = PodcastState.savedPosition(progress, activeEpisode?.chapter); if (position && position < audio.duration - 5) audio.currentTime = position; emit(); });
    ['play', 'pause', 'ended'].forEach(name => audio.addEventListener(name, () => { save(); emit(); })); audio.addEventListener('timeupdate', () => { if (Date.now() - lastSave > 5000) { lastSave = Date.now(); save(); emit(); } });
    return { load, list, selectChapter, toggle, snapshot, subscribe, openKnowledge, record };
  }
  const context = {
    state,
    navigate,
    questionRecords: Array.isArray(window.KNOWLEDGE_BASE_DATA) ? window.KNOWLEDGE_BASE_DATA : [],
    knowledgeRecords: Array.isArray(window.KNOWLEDGE_POINT_DATA) ? window.KNOWLEDGE_POINT_DATA : [],
    dialogs,
  };
  context.podcast = createPodcastController();
  context.podcast.load();

  async function renderRoute(route) {
    const epoch = ++renderEpoch;
    active?.unmount?.();
    workspaceRoot.replaceChildren();
    const workspace = workspaces.get(route.name) || workspaces.get('today');
    active = workspace;
    try {
      await workspace.mount(workspaceRoot, { ...context, route });
      if (epoch !== renderEpoch) return;
    } catch (_) {
      const error = document.createElement('section');
      error.className = 'workspace-error';
      error.innerHTML = `<h1>${titles[route.name] || '今日指挥台'}</h1><p>工作区暂时无法加载，请稍后重试。</p>`;
      workspaceRoot.append(error);
    }
    updateActiveNavigation(route.name === 'question-detail' ? 'questions' : route.name);
    document.title = `${titles[route.name] || titles.today} · 系统架构设计师`;
    workspaceRoot.focus({ preventScroll: true });
  }

  function applyTheme(theme) {
    const activeTheme = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.dataset.theme = activeTheme;
    document.querySelectorAll('[data-theme-toggle]').forEach(button => {
      button.textContent = activeTheme === 'dark' ? '🌙 黑夜' : '☀️ 白天';
      button.setAttribute('aria-pressed', String(activeTheme === 'dark'));
      button.setAttribute('aria-label', activeTheme === 'dark' ? '切换到白天模式' : '切换到黑夜模式');
    });
  }
  function toggleTheme() {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    try { localStorage.setItem(themeStorageKey, next); } catch (_) {}
  }
  function countdown() {
    const target = new Date('2026-10-24T00:00:00+08:00');
    document.getElementById('countdown').textContent = `${Math.max(0, Math.ceil((target - new Date()) / 86400000))} 天`;
  }

  const drawer = document.getElementById('workspace-drawer');
  const menu = document.getElementById('workspace-menu');
  drawer.querySelector('nav').append(...[...document.querySelectorAll('.workspace-nav a')].map(link => link.cloneNode(true)));
  menu.addEventListener('click', () => { menu.setAttribute('aria-expanded', 'true'); drawer.showModal(); drawer.querySelector('a')?.focus(); });
  drawer.addEventListener('close', () => { menu.setAttribute('aria-expanded', 'false'); menu.focus(); });
  drawer.addEventListener('click', event => { if (event.target === drawer || event.target.closest('a,[data-close-drawer]')) drawer.close(); });
  document.querySelectorAll('[data-theme-toggle]').forEach(button => button.addEventListener('click', toggleTheme));

  register('today', window.TodayWorkspace);
  register('knowledge', window.KnowledgeWorkspace);
  register('practice', window.PracticeWorkspace);
  register('questions', window.QuestionsWorkspace);
  register('question-detail', window.QuestionDetailWorkspace);
  register('training', window.TrainingWorkspace);
  register('podcasts', window.PodcastsWorkspace);
  register('records', window.RecordsWorkspace);

  applyTheme(document.documentElement.dataset.theme);
  countdown();
  AppRouter.subscribe(renderRoute);
  if (!location.hash || AppRouter.parseHash(location.hash).name === 'today' && location.hash !== '#/today') history.replaceState(null, '', '#/today');
  renderRoute(AppRouter.parseHash(location.hash));
}());
