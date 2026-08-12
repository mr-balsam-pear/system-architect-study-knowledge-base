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

console.log('multi-workspace layout tests: OK');
