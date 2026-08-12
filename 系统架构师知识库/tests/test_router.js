const assert = require('assert');
const Router = require('../site/router.js');

assert.deepStrictEqual(Router.parseHash(''), { name: 'today', params: {} });
assert.deepStrictEqual(Router.parseHash('#/knowledge'), { name: 'knowledge', params: {} });
assert.deepStrictEqual(Router.parseHash('#/questions/q001'), { name: 'question-detail', params: { id: 'q001' } });
assert.deepStrictEqual(Router.parseHash('#/missing'), { name: 'today', params: {} });
assert.strictEqual(Router.toHash('practice'), '#/practice');
assert.strictEqual(Router.toHash('question-detail', { id: 'q 001' }), '#/questions/q%20001');

console.log('router tests: OK');
