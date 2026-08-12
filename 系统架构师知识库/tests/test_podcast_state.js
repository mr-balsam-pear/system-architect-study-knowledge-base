'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const state = require('../site/podcast-state.js');

assert.deepEqual(state.parseProgress(null), { lastChapter: '', chapters: {} });
assert.deepEqual(state.parseProgress('{"lastChapter":"7","chapters":{"7":{"positionSeconds":760,"updatedAt":"x"}}}'), {
  lastChapter: '7', chapters: { '7': { positionSeconds: 760, updatedAt: 'x' } },
});
assert.deepEqual(state.parseProgress('{bad'), { lastChapter: '', chapters: {} });
assert.deepEqual(state.parseProgress('{"lastChapter":"../7","chapters":{"../7":{"positionSeconds":-2}}}'), { lastChapter: '', chapters: {} });

let progress = state.savePosition({ lastChapter: '', chapters: {} }, '7', 760.9, 900, '2026-08-12T00:00:00Z');
assert.equal(progress.lastChapter, '7');
assert.deepEqual(progress.chapters['7'], { positionSeconds: 760, updatedAt: '2026-08-12T00:00:00Z' });
assert.equal(state.savedPosition(progress, '7'), 760);
assert.equal(state.isFinished(progress, '7'), false);

progress = state.savePosition(progress, '7', 897, 900, 'later');
assert.equal(state.savedPosition(progress, '7'), 0);
assert.equal(state.isFinished(progress, '7'), true);
assert.equal(state.formatSeconds(65), '01:05');
assert.equal(state.formatSeconds(3665), '1:01:05');

const podcasts = [{ chapter: '1', available: false }, { chapter: '2', available: true }, { chapter: '7', available: true }];
assert.deepEqual(state.filterPodcasts(podcasts, progress, false), podcasts);
assert.deepEqual(state.filterPodcasts(podcasts, progress, true).map(item => item.chapter), ['1', '2']);
assert.deepEqual(state.playerView({ available: false }, progress, true, 0, 0), {
  showAudio: false, showPrimary: false, showRecord: false, progressText: '本章暂无播客', primaryText: '', miniText: '', playing: false,
});
assert.deepEqual(state.playerView({ chapter: '7', available: true, duration_seconds: 900 }, progress, true, 0, 900), {
  showAudio: true, showPrimary: true, showRecord: true, progressText: '本章已听完', primaryText: '重播本章', miniText: '已暂停 · 本章已听完', playing: false,
});
assert.equal(state.playIntentOnSelection(false, true), false);
assert.equal(state.playIntentOnSelection(true, true), true);
assert.equal(state.playIntentOnSelection(true, false), false);
const app = fs.readFileSync(path.join(__dirname, '../site/app.js'), 'utf8');
const recordHandler = app.slice(app.lastIndexOf("getElementById('podcast-record').addEventListener"), app.indexOf("podcastAudio.addEventListener('loadedmetadata'"));
assert.match(recordHandler, /openStudyRecord/);
assert.doesNotMatch(recordHandler, /fetch\s*\(/);
console.log('podcast-state tests: OK');
