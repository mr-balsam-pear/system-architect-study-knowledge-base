const assert = require('assert');
const fs = require('fs');
const path = require('path');

const siteRoot = path.resolve(__dirname, '..', 'site');
const html = fs.readFileSync(path.join(siteRoot, 'index.html'), 'utf8');
const app = fs.readFileSync(path.join(siteRoot, 'app.js'), 'utf8');

assert.match(
  html,
  /id="theme-toggle"[^>]+aria-pressed="false"[^>]+aria-label="切换到黑夜模式"/,
  '初始浅色主题应说明按钮将切换到黑夜模式',
);
assert.match(
  app,
  /activeTheme === 'dark' \? '切换到白天模式' : '切换到黑夜模式'/,
  '主题切换后应同步更新下一步操作的可访问名称',
);

console.log('theme accessibility tests: OK');
