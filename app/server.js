// Simple web app for the DigitalOcean Kubernetes (DOKS) demo.
// No external dependencies: uses Node's built-in http module.
//
// Endpoints
//   GET /          HTML page showing which pod and node served the request
//   GET /api/info  Same information as JSON (used by the load-balancer demo script)
//   GET /work      Burns CPU for a short time to simulate a heavy request (drives autoscaling)
//   GET /healthz   Liveness probe: the process is up
//   GET /readyz    Readiness probe: the pod can take traffic (false while shutting down)

const http = require('http');
const os = require('os');

const PORT = Number(process.env.PORT || 8080);
const POD_NAME = process.env.POD_NAME || os.hostname();
const NODE_NAME = process.env.NODE_NAME || 'local';
const APP_VERSION = process.env.APP_VERSION || '1.0.0';
const STARTED_AT = new Date();

let ready = true;
let requestCount = 0;

// Busy-loop for `ms` milliseconds to simulate CPU-heavy work (e.g. rendering, image resize).
function burnCpu(ms) {
  const end = Date.now() + ms;
  let x = 0;
  while (Date.now() < end) {
    x += Math.sqrt(Math.random() * 1000);
  }
  return x;
}

function info() {
  return {
    message: 'Hello from DigitalOcean Kubernetes',
    pod: POD_NAME,
    node: NODE_NAME,
    version: APP_VERSION,
    uptimeSeconds: Math.round((Date.now() - STARTED_AT.getTime()) / 1000),
    requestsServed: requestCount,
  };
}

function page(i) {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DOKS Scalable Web App</title>
<style>
  body { font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; background: #f4f7fb; color: #1b2a41; margin: 0; }
  main { max-width: 640px; margin: 48px auto; padding: 32px; background: #fff; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,.08); }
  h1 { color: #0069ff; font-size: 26px; margin-top: 0; }
  dt { font-weight: 600; margin-top: 12px; }
  dd { margin: 4px 0 0; font-family: Menlo, Consolas, monospace; }
  p.note { color: #5a6472; font-size: 14px; }
</style>
</head>
<body>
<main>
  <h1>${i.message}</h1>
  <dl>
    <dt>Served by pod</dt><dd>${i.pod}</dd>
    <dt>Running on node</dt><dd>${i.node}</dd>
    <dt>App version</dt><dd>${i.version}</dd>
    <dt>Requests served by this pod</dt><dd>${i.requestsServed}</dd>
  </dl>
  <p class="note">Refresh the page: the load balancer spreads requests across pods, so the pod name changes.</p>
</main>
</body>
</html>`;
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  requestCount += 1;

  if (url.pathname === '/healthz') {
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    return res.end('ok');
  }

  if (url.pathname === '/readyz') {
    res.writeHead(ready ? 200 : 503, { 'Content-Type': 'text/plain' });
    return res.end(ready ? 'ready' : 'shutting down');
  }

  if (url.pathname === '/api/info') {
    res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    return res.end(JSON.stringify(info()));
  }

  if (url.pathname === '/work') {
    // Cap the work per request so a single call can't hang a pod.
    const ms = Math.min(Number(url.searchParams.get('ms') || 50), 500);
    burnCpu(ms);
    res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    return res.end(JSON.stringify({ pod: POD_NAME, workedMs: ms }));
  }

  if (url.pathname === '/') {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
    return res.end(page(info()));
  }

  res.writeHead(404, { 'Content-Type': 'text/plain' });
  res.end('not found');
});

server.listen(PORT, () => {
  console.log(`web-app ${APP_VERSION} listening on :${PORT} (pod=${POD_NAME}, node=${NODE_NAME})`);
});

// Graceful shutdown: stop taking new traffic, finish in-flight requests, then exit.
// Kubernetes sends SIGTERM during rolling updates and scale-down.
process.on('SIGTERM', () => {
  console.log('SIGTERM received: draining connections');
  ready = false;
  setTimeout(() => {
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(0), 10000).unref();
  }, 5000);
});
