const assert = require('assert');
const fs = require('fs');
const path = require('path');

const siteRoot = path.resolve(__dirname, '..', 'site');
const html = fs.readFileSync(path.join(siteRoot, 'index.html'), 'utf8');

assert.match(html, /id="app-sidebar"/);
assert.match(html, /id="workspace-root"/);
assert.match(html, /id="workspace-menu"/);
assert.match(html, /data-route="today"/);
assert.match(html, /data-route="records"/);
assert.doesNotMatch(html, /id="chapter-tree"/);
assert.doesNotMatch(html, /id="practice-reader"/);
assert.doesNotMatch(html, /id="question-list"/);
assert.match(html, /src="router\.js"[\s\S]*src="app\.js"/);
assert.doesNotMatch(html, /id="question-dialog"|id="question-pdf"/);
const modules = ['today', 'knowledge', 'practice', 'questions', 'question-detail', 'training', 'podcasts', 'records'];
for (const name of modules) {
  const source = fs.readFileSync(path.join(siteRoot, 'workspaces', `${name}.js`), 'utf8');
  assert.match(source, /mount\s*\(/, `${name} must expose mount`);
  assert.match(source, /unmount\s*\(/, `${name} must expose unmount`);
}
const dialogs = fs.readFileSync(path.join(siteRoot, 'dialogs.js'), 'utf8');
assert.match(dialogs, /createDialogController/);
assert.match(dialogs, /returnFocus/);
assert.match(dialogs, /dirty/);
assert.match(dialogs, /requestClose/);
const knowledge = fs.readFileSync(path.join(siteRoot, 'workspaces', 'knowledge.js'), 'utf8');
const practice = fs.readFileSync(path.join(siteRoot, 'workspaces', 'practice.js'), 'utf8');
const detail = fs.readFileSync(path.join(siteRoot, 'workspaces', 'question-detail.js'), 'utf8');
assert.match(knowledge, /data-knowledge-rail-toggle/);
assert.match(knowledge, /id="knowledge-rail"/);
assert.match(practice, /practice-index-rail/);
assert.match(detail, /question-related-rail/);

console.log('multi-workspace layout tests: OK');
