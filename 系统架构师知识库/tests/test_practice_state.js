'use strict';
const assert = require('node:assert/strict');
const state = require('../site/practice-state.js');

const session = state.createSession(['q1', 'q2'], 10, 1000);
state.setAnswer(session, 'q1', 'B');
assert.equal(state.progress(session, 'q1').nextId, 'q2');
assert.equal(state.progress(session, 'q2').previousId, 'q1');
assert.equal(state.remainingSeconds(session, 61000), 540);
assert.equal(state.formatSeconds(65), '01:05');
const summary = state.summarize(session, [
  { id: 'q1', type: 'single_choice', title: '一', answer: 'B', knowledge_ids: ['7.1'] },
  { id: 'q2', type: 'single_choice', title: '二', answer: 'A', knowledge_ids: ['8.1'] },
]);
assert.deepEqual({ total: summary.total, answered: summary.answered, correct: summary.correct, accuracy: summary.accuracy }, { total: 2, answered: 1, correct: 1, accuracy: 50 });
assert.deepEqual(summary.weakKnowledge, [{ knowledgeId: '8.1', count: 1 }]);

const questions = [
  { id: 'q1', type: 'single_choice', title: '一', answer: 'B', explanation: '解析1', options: [{ label: 'A', text: '甲' }, { label: 'B', text: '乙' }], knowledge_ids: ['7.1'] },
  { id: 'q2', type: 'single_choice', title: '二', answer: 'A', explanation: '解析2', options: [{ label: 'A', text: '丙' }, { label: 'B', text: '丁' }], knowledge_ids: ['8.1'] },
];
const snapshot = state.submitSnapshot(session, questions, 7000);
state.setAnswer(session, 'q1', 'A');
assert.equal(snapshot.answers.q1, 'B');
assert.equal(snapshot.finishedAt, 7000);
assert.equal(Object.isFrozen(snapshot), true);
assert.equal(Object.isFrozen(snapshot.answers), true);
assert.equal(Object.isFrozen(snapshot.questions[0].options), true);
assert.throws(() => { snapshot.answers.q1 = 'A'; }, TypeError);
assert.deepEqual(state.reviewData(snapshot, 'q1'), {
  id: 'q1', title: '一', selected: 'B', answer: 'B', correct: true, explanation: '解析1',
  options: [{ label: 'A', text: '甲', selected: false, correct: false }, { label: 'B', text: '乙', selected: true, correct: true }],
});
const subjectiveSession = state.createSession(['case1']);
state.setAnswer(subjectiveSession, 'case1', { part1: { text: '原答案' } });
const subjectiveSnapshot = state.submitSnapshot(subjectiveSession, [], 8000);
subjectiveSession.answers.case1.part1.text = '篡改答案';
assert.equal(subjectiveSnapshot.answers.case1.part1.text, '原答案');
assert.equal(Object.isFrozen(subjectiveSnapshot.answers.case1.part1), true);

const caseIntent = state.caseRecordIntent({ id: 'case1', type: 'case_analysis' }, [
  { item: { id: 'a', reference_points: ['要点1'] }, text: '作答1', rating: '已覆盖' },
  { item: { id: 'b', reference_points: ['要点2'] }, text: '', rating: '未覆盖' },
]);
assert.equal(caseIntent.result, '部分完成');
assert.match(caseIntent.promptEvidence, /a\[已覆盖\]：作答1/);
assert.equal(caseIntent.hitKeywords, 'a');
assert.equal(caseIntent.missedKeywords, '要点2');
const essayIntent = state.essayRecordIntent({ abstract: '摘要', project: '背景', project_code: 'P1', solution: '方案', tradeoff: '取舍', outcome: '效果', body: '提纲' });
assert.deepEqual({ projectCode: essayIntent.projectCode, decision: essayIntent.decision, tradeoff: essayIntent.tradeoff, outcome: essayIntent.outcome }, { projectCode: 'P1', decision: '方案', tradeoff: '取舍', outcome: '效果' });
assert.equal(state.recordIntent(null), null);
assert.deepEqual(state.recordIntent({ type: '真题', result: '正确' }), { type: '真题', result: '正确' });
const restored = state.restoreSession(JSON.parse(JSON.stringify(session)));
assert.deepEqual(restored.questionIds, session.questionIds);
assert.deepEqual(restored.answers, session.answers);
assert.equal(restored.startedAt, session.startedAt);
assert.equal(restored.finishedAt, session.finishedAt);
assert.equal(restored.limitMinutes, session.limitMinutes);
console.log('practice-state tests: OK');
