const { test } = require('node:test');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const { once } = require('node:events');
const net = require('node:net');
const http = require('node:http');

test('HTTP regressions and graceful shutdown', { timeout: 20000 }, async (t) => {
  const child = spawn(process.execPath, ['server.js'], {
    cwd: __dirname, env: { ...process.env, PORT: '0' }, stdio: ['ignore', 'pipe', 'pipe'],
  });
  t.after(() => { if (child.exitCode === null) child.kill('SIGKILL'); });
  const startup = await new Promise((resolve, reject) => {
    child.stdout.once('data', (data) => resolve(String(data)));
    child.once('error', reject);
    child.once('exit', (code) => reject(new Error(`server exited: ${code}`)));
  });
  const port = Number(startup.match(/:(\d+)/)[1]);
  function request(path) {
    return new Promise((resolve, reject) => {
      http.get({ hostname: '127.0.0.1', port, path, agent: false }, (res) => {
        let body = '';
        res.on('data', (chunk) => { body += chunk; });
        res.on('end', () => resolve({ status: res.statusCode, body }));
      }).on('error', reject);
    });
  }
  await t.test('malformed raw request returns 400 without crashing', async () => {
    const reply = await new Promise((resolve, reject) => {
      const socket = net.connect(port, '127.0.0.1', () => socket.end('GET // HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n'));
      let result = '';
      socket.on('data', (data) => { result += data; });
      socket.on('end', () => resolve(result));
      socket.on('error', reject);
    });
    assert.match(reply, /^HTTP\/1.1 400 /);
    assert.equal((await request('/healthz')).status, 200);
  });
  await t.test('invalid work durations are rejected', async () => {
    for (const ms of ['-1', 'NaN', 'Infinity', '-Infinity', 'abc', '', '%20', '1e309']) {
      assert.equal((await request(`/work?ms=${ms}`)).status, 400, ms);
    }
  });
  await t.test('work default, zero, decimal and cap', async () => {
    for (const [path, expected] of [['/work', 50], ['/work?ms=0', 0], ['/work?ms=0.5', 0.5], ['/work?ms=999', 500]]) {
      const res = await request(path);
      assert.equal(res.status, 200);
      assert.equal(JSON.parse(res.body).workedMs, expected);
    }
  });
  await t.test('normal endpoints and unknown route', async () => {
    assert.equal((await request('/')).status, 200);
    assert.equal((await request('/readyz')).status, 200);
    const result = await request('/api/info');
    assert.equal(result.status, 200);
    assert.equal(JSON.parse(result.body).version, require('./package.json').version);
    assert.equal((await request('/missing')).status, 404);
  });
  await t.test('health checks stay responsive during concurrent CPU work', async () => {
    const work = Array.from({ length: 8 }, () => request('/work?ms=250'));
    await new Promise((resolve) => setTimeout(resolve, 30));
    const start = performance.now();
    assert.equal((await request('/readyz')).status, 200);
    assert.equal((await request('/healthz')).status, 200);
    const elapsed = performance.now() - start;
    assert.ok(elapsed < 1000, `health checks took ${elapsed.toFixed(1)} ms during CPU work`);
    for (const response of await Promise.all(work)) assert.equal(response.status, 200);
  });
  await t.test('SIGTERM marks unready, then exits cleanly', async () => {
    const exit = once(child, 'exit');
    child.kill('SIGTERM');
    for (let i = 0; i < 50; i += 1) {
      if ((await request('/readyz')).status === 503) break;
      await new Promise((resolve) => setTimeout(resolve, 10));
    }
    assert.equal((await request('/readyz')).status, 503);
    assert.equal((await request('/healthz')).status, 200);
    assert.equal((await exit)[0], 0);
  });
});
