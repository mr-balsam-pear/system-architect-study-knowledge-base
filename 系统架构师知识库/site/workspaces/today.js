(function (root) {
  let view; let generation = 0;
  const safe = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
  async function dashboard() {
    try { const response = await fetch('/api/study/dashboard', { headers: { Accept: 'application/json' } }); if (!response.ok) throw new Error(); return response.json(); }
    catch (_) { return { due_reviews: [], recent_records: [], weak_topics: [], essay_material_count: 0, record_count: 0, offline: true }; }
  }
  root.TodayWorkspace = {
    async mount(container, context) {
      const current = ++generation;
      const data = await dashboard();
      if (current !== generation || !container.isConnected) return;
      const due = data.due_reviews || []; const recent = data.recent_records || [];
      const next = due[0]; const last = recent[0]; const podcast = context.podcast?.snapshot?.();
      view = document.createElement('section'); view.className = 'workspace-view today-workspace';
      view.innerHTML = `<header class="workspace-hero today-hero"><div><p class="eyebrow">NIGHT COMMAND · ${data.offline ? 'LOCAL DATA' : 'LIVE ARCHIVE'}</p><h1>今天，只推进一个得分闭环。</h1><p>先处理到期复习，再做一组限时训练；把下一次判断规则写进档案。</p></div><a class="primary-action" href="${next ? '#/records' : '#/practice'}">${next ? `复习 ${safe(next.knowledge_id)}` : '开始今日训练'} →</a></header>
      <div class="today-rhythm"><article class="mission-panel"><span class="signal-label">NEXT ACTION</span><h2>${next ? safe(next.knowledge_title || next.knowledge_id) : '完成一组已核对题目'}</h2><p>${next ? `复习日期 ${safe(next.review_date)} · 先复述再核对` : '当前没有到期项，从选择题或案例训练开始。'}</p><div class="action-row"><a class="button" href="${next ? '#/knowledge' : '#/practice'}">进入学习</a><button class="quiet-action" type="button" data-record>记录判断规则</button></div></article>
      <aside class="continuity-panel"><p class="eyebrow">CONTINUE</p><h2>${last ? safe(last.title || last.knowledge_title || '最近学习') : '尚无学习记录'}</h2><p>${last ? `${safe(last.type)} · ${safe(last.result || '未填写')}` : '完成一次学习后，这里会给出继续入口。'}</p><a href="#/records">查看学习档案 →</a></aside></div>
      <section class="pulse-strip" aria-label="学习摘要"><div><span>到期复习</span><strong>${due.length}</strong></div><div><span>薄弱专题</span><strong>${(data.weak_topics || []).length}</strong></div><div><span>论文素材</span><strong>${data.essay_material_count || 0}</strong></div></section>
      <section class="recent-podcast"><div><p class="eyebrow">AUDIO THREAD</p><h2>${podcast?.active ? `第${safe(podcast.active.chapter)}章 · ${safe(podcast.active.title)}` : '章节播客待命'}</h2><p>${podcast?.active ? safe(podcast.view?.miniText || '进度保存在当前浏览器') : '在通勤和碎片时间继续章节学习。'}</p></div><a class="quiet-action" href="#/podcasts">打开节目库 →</a></section>`;
      view.querySelector('[data-record]').addEventListener('click', event => context.dialogs.openStudyRecord({ type: '知识点学习', knowledgeId: next?.knowledge_id, title: next?.knowledge_title || '今日判断规则' }, event.currentTarget));
      container.append(view);
    },
    unmount() { generation += 1; view = null; },
  };
}(globalThis));
