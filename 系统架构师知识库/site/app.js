(function () {
  const workspaceRoot = document.getElementById('workspace-root');
  const themeStorageKey = 'system-architect-study-theme';
  const state = WorkspaceState.createStore();
  const workspaces = new Map();
  let active = null;

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

  const context = {
    state,
    navigate,
    questionRecords: Array.isArray(window.KNOWLEDGE_BASE_DATA) ? window.KNOWLEDGE_BASE_DATA : [],
    knowledgeRecords: Array.isArray(window.KNOWLEDGE_POINT_DATA) ? window.KNOWLEDGE_POINT_DATA : [],
  };

  async function renderRoute(route) {
    active?.unmount?.();
    workspaceRoot.replaceChildren();
    const workspace = workspaces.get(route.name) || workspaces.get('today');
    active = workspace;
    try {
      await workspace.mount(workspaceRoot, { ...context, route });
    } catch (_) {
      const error = document.createElement('section');
      error.className = 'workspace-error';
      error.innerHTML = `<h1>${titles[route.name] || '今日指挥台'}</h1><p>工作区暂时无法加载，请稍后重试。</p>`;
      workspaceRoot.append(error);
    }
    updateActiveNavigation(route.name === 'question-detail' ? 'questions' : route.name);
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
  drawer.addEventListener('click', event => { if (event.target.closest('a,[data-close-drawer]')) drawer.close(); });
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
