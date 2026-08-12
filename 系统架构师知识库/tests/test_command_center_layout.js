const assert = require('assert');
const fs = require('fs');
const path = require('path');

const siteRoot = path.resolve(__dirname, '..', 'site');
const read = name => fs.readFileSync(path.join(siteRoot, name), 'utf8');
const html = read('index.html');
const css = read('styles.css');
const app = read('app.js');
const tokens = fs.existsSync(path.join(siteRoot, 'tokens.css')) ? read('tokens.css') : '';

for (const id of ['app-sidebar', 'workspace-root', 'workspace-menu', 'workspace-drawer', 'study-dialog', 'podcast-mini-player', 'podcast-audio']) {
  assert.match(html, new RegExp(`id="${id}"`), `missing #${id}`);
}

assert.match(html, /class="app-shell"/);
assert.match(html, /class="workspace-nav"/);
assert.match(html, /data-route="today"/);
assert.match(html, /data-route="records"/);
assert.match(html, /href="tokens\.css"[\s\S]*href="styles\.css"/);
assert.match(html, /src="router\.js"[\s\S]*src="app\.js"/);

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
assert.match(app, /renderRoute/);
assert.match(app, /updateActiveNavigation/);

console.log('command center layout tests: OK');
