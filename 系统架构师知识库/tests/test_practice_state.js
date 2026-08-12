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
console.log('practice-state tests: OK');
