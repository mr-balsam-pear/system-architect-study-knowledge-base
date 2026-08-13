const assert = require('assert');
const WorkspaceState = require('../site/workspace-state.js');

const store = WorkspaceState.createStore();
store.patch('knowledge', { activeId: '7.3.4', query: '黑板系统', scrollTop: 320 });
store.patch('questions', { filters: { year: '2022' }, scrollTop: 480 });
assert.deepStrictEqual(store.read('knowledge'), { activeId: '7.3.4', query: '黑板系统', scrollTop: 320 });
assert.deepStrictEqual(store.read('questions').filters, { year: '2022' });
assert.deepStrictEqual(store.read('missing'), {});
assert.notStrictEqual(store.read('knowledge'), store.read('knowledge'));
store.patch('knowledge', { expandedChapters: ['7', '8'] });
assert.deepStrictEqual(store.read('knowledge'), { activeId: '7.3.4', query: '黑板系统', scrollTop: 320, expandedChapters: ['7', '8'] });
const knowledgeSource = require('fs').readFileSync(require('path').join(__dirname, '../site/workspaces/knowledge.js'), 'utf8');
assert.match(knowledgeSource, /context\.state\.patch\('knowledge'/);

console.log('workspace-state tests: OK');
