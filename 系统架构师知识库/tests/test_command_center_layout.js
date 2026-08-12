const assert = require('assert');
const fs = require('fs');
const path = require('path');

const siteRoot = path.resolve(__dirname, '..', 'site');
const read = name => fs.readFileSync(path.join(siteRoot, name), 'utf8');
const html = read('index.html');
const css = read('styles.css');
const app = read('app.js');
const tokens = fs.existsSync(path.join(siteRoot, 'tokens.css')) ? read('tokens.css') : '';

for (const id of [
  'countdown', 'record-count', 'study-dashboard', 'due-review-count',
  'recent-record-count', 'weak-topic-count', 'essay-material-count',
  'open-podcast-workspace', 'podcast-workspace', 'practice', 'knowledge',
  'questions', 'training', 'question-dialog', 'study-dialog',
]) assert.match(html, new RegExp(`id="${id}"`), `missing #${id}`);

assert.match(html, /class="command-header"/);
assert.match(html, /class="command-grid"/);
assert.match(html, /class="work-panel mission-sequence"/);
assert.match(html, /id="mission-review"/);
assert.match(html, /id="mission-practice"/);
assert.match(html, /id="mission-rule"/);
assert.match(html, /href="tokens\.css"[\s\S]*href="styles\.css"/);
assert.doesNotMatch(html.match(/<nav[^>]+aria-label="页面导航"[\s\S]*?<\/nav>/)?.[0] || '', /播客/);

assert.match(tokens, /--color-paper:/);
assert.match(tokens, /--color-accent:/);
assert.match(tokens, /--font-display:/);
assert.match(tokens, /--space-md:/);
assert.match(tokens, /:root\[data-theme="dark"\]/);
assert.match(css, /^\/\* Hallmark · genre: atmospheric · macrostructure: Workbench/m);
assert.match(css, /overflow-x:\s*clip/);
assert.match(css, /@media\s*\(max-width:\s*48rem\)/);
assert.match(css, /@media\s*\(prefers-reduced-motion:\s*reduce\)/);
assert.doesNotMatch(css, /#[0-9a-fA-F]{3,8}\b|rgba?\(/, 'component CSS must use tokens');
assert.match(app, /mission-review/);
assert.match(app, /mission-practice/);
assert.match(app, /mission-rule/);

console.log('command center layout tests: OK');
