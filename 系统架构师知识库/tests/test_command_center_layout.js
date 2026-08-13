const assert = require('assert');
const fs = require('fs');
const path = require('path');

const siteRoot = path.resolve(__dirname, '..', 'site');
const read = name => fs.readFileSync(path.join(siteRoot, name), 'utf8');
const html = read('index.html');
const css = read('styles.css');
const shellCss = read(path.join('styles', 'app-shell.css'));
const workspaceCss = read(path.join('styles', 'workspaces.css'));
const overlayCss = read(path.join('styles', 'overlays.css'));
const combinedCss = [css, shellCss, workspaceCss, overlayCss].join('\n');
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
assert.match(tokens, /--reading-measure:/);
assert.match(tokens, /--rail-collapsed:/);
assert.match(tokens, /--player-safe-space:/);
assert.match(css, /^\/\* Hallmark · pre-emit critique: P\d H\d E\d S\d R\d V\d/m);
assert.match(css, /genre: atmospheric · macrostructure: Workbench/);
assert.match(css, /contrast: pass \(40–41\)/);
assert.match(css, /responsive\/mobile: pass/);
assert.match(combinedCss, /overflow-x:\s*clip/);
assert.match(combinedCss, /@media\s*\(max-width:\s*48rem\)/);
assert.match(combinedCss, /@media\s*\(max-width:\s*64rem\)/);
assert.match(workspaceCss, /\.is-rail-collapsed/);
assert.match(workspaceCss, /max-width:\s*var\(--reading-measure\)/);
assert.match(combinedCss, /@media\s*\(prefers-reduced-motion:\s*reduce\)/);
assert.doesNotMatch(combinedCss, /#[0-9a-fA-F]{3,8}\b|rgba?\(/, 'component CSS must use tokens');
assert.match(app, /renderRoute/);
assert.match(app, /updateActiveNavigation/);

console.log('command center layout tests: OK');
