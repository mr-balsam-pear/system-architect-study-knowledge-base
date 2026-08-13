(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.PracticeState = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  function createSession(questionIds, limitMinutes = 0, now = Date.now()) {
    return { questionIds: [...questionIds], answers: {}, submitted: {}, startedAt: now, limitMinutes: Math.max(0, Number(limitMinutes) || 0), finishedAt: 0 };
  }
  function restoreSession(raw) {
    const value = raw && typeof raw === 'object' && !Array.isArray(raw) ? raw : {};
    const session = createSession(Array.isArray(value.questionIds) ? value.questionIds.filter(id => typeof id === 'string') : [], value.limitMinutes, Number(value.startedAt) || Date.now());
    session.answers = value.answers && typeof value.answers === 'object' && !Array.isArray(value.answers) ? JSON.parse(JSON.stringify(value.answers)) : {};
    session.submitted = value.submitted && typeof value.submitted === 'object' && !Array.isArray(value.submitted) ? JSON.parse(JSON.stringify(value.submitted)) : {};
    session.finishedAt = Number(value.finishedAt) || 0;
    return session;
  }
  function setAnswer(session, questionId, value) {
    session.answers[questionId] = value;
    return session;
  }
  function progress(session, questionId) {
    const index = Math.max(0, session.questionIds.indexOf(questionId));
    return { index, current: session.questionIds.length ? index + 1 : 0, total: session.questionIds.length,
      previousId: index > 0 ? session.questionIds[index - 1] : '', nextId: index + 1 < session.questionIds.length ? session.questionIds[index + 1] : '' };
  }
  function remainingSeconds(session, now = Date.now()) {
    if (!session.limitMinutes) return null;
    return Math.max(0, Math.ceil((session.startedAt + session.limitMinutes * 60000 - now) / 1000));
  }
  function formatSeconds(seconds) {
    const value = Math.max(0, Math.floor(seconds));
    return `${String(Math.floor(value / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`;
  }
  function summarize(session, questions) {
    const choices = questions.filter(item => item.type === 'single_choice');
    const results = choices.map(item => ({ id: item.id, title: item.title, selected: session.answers[item.id] || '', answer: item.answer,
      correct: Boolean(session.answers[item.id]) && session.answers[item.id] === item.answer, knowledge_ids: item.knowledge_ids || [] }));
    const correct = results.filter(item => item.correct).length;
    const weak = {};
    results.filter(item => !item.correct).forEach(item => item.knowledge_ids.forEach(id => { weak[id] = (weak[id] || 0) + 1; }));
    return { total: results.length, answered: results.filter(item => item.selected).length, correct,
      accuracy: results.length ? Math.round(correct * 100 / results.length) : 0, results,
      weakKnowledge: Object.entries(weak).sort((a, b) => b[1] - a[1]).map(([knowledgeId, count]) => ({ knowledgeId, count })) };
  }
  function immutableCopy(value) {
    if (!value || typeof value !== 'object') return value;
    if (Array.isArray(value)) return Object.freeze(value.map(immutableCopy));
    return Object.freeze(Object.fromEntries(Object.entries(value).map(([key, item]) => [key, immutableCopy(item)])));
  }
  function submitSnapshot(session, questions, now = Date.now()) {
    const copiedQuestions = questions.filter(item => item.type === 'single_choice').map(item => Object.freeze({
      id: item.id, title: item.title, answer: item.answer, explanation: item.explanation || '',
      options: Object.freeze((item.options || []).map(option => Object.freeze({ label: option.label, text: option.text }))),
      knowledge_ids: Object.freeze([...(item.knowledge_ids || [])]), type: item.type,
    }));
    const snapshot = { answers: immutableCopy(session.answers), questions: Object.freeze(copiedQuestions), startedAt: session.startedAt, finishedAt: now };
    const summary = summarize(snapshot, copiedQuestions);
    snapshot.summary = Object.freeze({ ...summary, results: Object.freeze(summary.results.map(Object.freeze)),
      weakKnowledge: Object.freeze(summary.weakKnowledge.map(Object.freeze)) });
    return Object.freeze(snapshot);
  }
  function reviewData(snapshot, questionId) {
    const question = snapshot.questions.find(item => item.id === questionId);
    if (!question) return null;
    const selected = snapshot.answers[questionId] || '';
    return { id: question.id, title: question.title, selected, answer: question.answer, correct: Boolean(selected) && selected === question.answer,
      explanation: question.explanation, options: question.options.map(option => ({ ...option, selected: option.label === selected, correct: option.label === question.answer })) };
  }
  function caseRecordIntent(question, answers) {
    const incomplete = answers.filter(answer => answer.rating !== '已覆盖');
    return { type: '案例', result: incomplete.length ? '部分完成' : '基本掌握',
      promptEvidence: answers.map(answer => `${answer.item.id}[${answer.rating}]：${String(answer.text || '').trim() || '未作答'}`).join(' | ').slice(0, 1200),
      hitKeywords: answers.filter(answer => answer.rating === '已覆盖').map(answer => answer.item.id).join('、').slice(0, 600),
      missedKeywords: incomplete.flatMap(answer => answer.item.reference_points || []).join('、').slice(0, 600),
      errorType: incomplete.length ? '要点覆盖不足' : '', rule: question.explanation || '' };
  }
  function essayRecordIntent(values) {
    return { type: '论文素材', result: '待复习', promptEvidence: `摘要：${values.abstract || ''}\n项目背景：${values.project || ''}`.slice(0, 1200),
      projectCode: String(values.project_code || '').slice(0, 120), decision: String(values.solution || '').slice(0, 1200),
      tradeoff: String(values.tradeoff || '').slice(0, 1200), outcome: String(values.outcome || '').slice(0, 1200),
      missedKeywords: String(values.body || '').slice(0, 600), rule: String(values.solution || '').slice(0, 800) };
  }
  function recordIntent(action) { return action ? { ...action } : null; }
  return { createSession, restoreSession, setAnswer, progress, remainingSeconds, formatSeconds, summarize, submitSnapshot, reviewData, caseRecordIntent, essayRecordIntent, recordIntent };
}));
