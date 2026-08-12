(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.PracticeState = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  function createSession(questionIds, limitMinutes = 0, now = Date.now()) {
    return { questionIds: [...questionIds], answers: {}, submitted: {}, startedAt: now, limitMinutes: Math.max(0, Number(limitMinutes) || 0), finishedAt: 0 };
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
  return { createSession, setAnswer, progress, remainingSeconds, formatSeconds, summarize };
}));
