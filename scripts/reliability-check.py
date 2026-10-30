#!/usr/bin/env python3
"""Measure HTTP availability during a rollout or one PDB-respecting pod eviction.

Usage: python3 scripts/reliability-check.py rollout|pod-recovery [--execute]
The default is a read-only plan. Requires the configured cluster identity, two
ready app pods, a healthy PDB, and no internal load generator. It never drains,
stops, or deletes a worker. Sampling is sequential at up to 10 requests/second.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('action', choices=['rollout', 'pod-recovery'])
parser.add_argument('--execute', action='store_true')
parser.add_argument('--output', type=Path, help='New evidence directory; defaults to a timestamped directory under evidence/runs')
args = parser.parse_args()

def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')

def run(command, **kwargs):
    return subprocess.run(command, check=True, text=True, capture_output=True, **kwargs).stdout

context = run(['bash', '-c', 'source scripts/lib.sh; set -e; verify_cluster_identity; printf "%s" "$EXPECTED_CONTEXT"'], cwd=ROOT).strip()
KUBE = ['kubectl', '--context', context, '--request-timeout=20s']

def get(kind, *extra):
    return json.loads(run(KUBE + ['-n', 'web-app', 'get', kind, *extra, '-o', 'json']))

def ready(pod):
    return not pod['metadata'].get('deletionTimestamp') and any(
        c['type'] == 'Ready' and c['status'] == 'True' for c in pod.get('status', {}).get('conditions', []))

pods = get('pods')['items']
app_pods = [p for p in pods if p['metadata'].get('labels', {}).get('app') == 'web-app']
if any(p['metadata'].get('labels', {}).get('app') != 'web-app' for p in pods):
    raise SystemExit('Refusing: remove other demo/load-generator pods from web-app first.')
deployment = get('deployment', 'web-app')
if deployment['spec'].get('replicas') != 2 or len(app_pods) != 2 or not all(map(ready, app_pods)):
    raise SystemExit('Refusing: wait for exactly two ready app replicas before this controlled check.')
pdb = get('pdb', 'web-app')
if pdb['status'].get('disruptionsAllowed', 0) < 1:
    raise SystemExit('Refusing: PDB does not allow one voluntary eviction.')
target = sorted(app_pods, key=lambda p: p['metadata']['name'])[0]
ip = get('service', 'web-app')['status']['loadBalancer']['ingress'][0]['ip']
url = f'http://{ip}/api/info'
plan = {'action': args.action, 'context': context, 'url': url,
        'pod': target['metadata']['name'] if args.action == 'pod-recovery' else None,
        'placement': {p['metadata']['name']: p['spec']['nodeName'] for p in app_pods}}
print(json.dumps(plan, indent=2), flush=True)
if not args.execute:
    print('Read-only plan. Pass --execute to perform the measured action.')
    raise SystemExit(0)

out = args.output or ROOT / 'evidence/runs' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + args.action)
out = out.resolve()
out.mkdir(parents=True, exist_ok=False)
metadata = {**plan, 'started_at': timestamp(), 'interval_seconds': .1, 'request_timeout_seconds': 3,
            'source_sha256': hashlib.sha256((ROOT / 'app/server.js').read_bytes()).hexdigest(),
            'scope': 'Rolling deployment' if args.action == 'rollout' else 'One voluntary pod eviction through policy/v1; not a node-failure test'}
(out / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
print(run(['bash', 'scripts/capture-evidence.sh', 'before', str(out)], cwd=ROOT), flush=True)
stop = threading.Event()
samples = []

def http_monitor():
    with (out / 'http.jsonl').open('w') as log:
        while not stop.is_set():
            start = time.monotonic()
            row = {'at': timestamp()}
            try:
                with urllib.request.urlopen(url, timeout=3) as response:
                    row['status'] = response.status
                    body = json.load(response)
                    row.update({k: body.get(k) for k in ['pod', 'node', 'version']})
            except Exception as exc:
                row.update(status=getattr(exc, 'code', None), error=str(exc))
            row['latency_ms'] = round((time.monotonic() - start) * 1000, 3)
            samples.append(row)
            log.write(json.dumps(row) + '\n'); log.flush()
            stop.wait(max(0, .1 - (time.monotonic() - start)))

def cluster_monitor():
    with (out / 'cluster.jsonl').open('w') as log:
        while not stop.is_set():
            row = {'at': timestamp()}
            try:
                row['resources'] = get('deployment,pods,hpa,pdb')
            except Exception as exc:
                row['error'] = str(exc)
            log.write(json.dumps(row) + '\n'); log.flush()
            stop.wait(2)

threads = [threading.Thread(target=http_monitor), threading.Thread(target=cluster_monitor)]
for thread in threads:
    thread.start()
success = False
try:
    time.sleep(10)
    metadata['action_started_at'] = timestamp()
    if args.action == 'rollout':
        result = run(['bash', 'scripts/03-deploy.sh'], cwd=ROOT)
    else:
        # UID precondition prevents targeting a different pod with a reused name.
        eviction = {'apiVersion': 'policy/v1', 'kind': 'Eviction',
                    'metadata': {'name': target['metadata']['name'], 'namespace': 'web-app'},
                    'deleteOptions': {'preconditions': {'uid': target['metadata']['uid']}}}
        (out / 'eviction.json').write_text(json.dumps(eviction, indent=2) + '\n')
        result = run(KUBE + ['create', '--raw', f'/api/v1/namespaces/web-app/pods/{target["metadata"]["name"]}/eviction', '-f', str(out / 'eviction.json')])
    (out / 'action.txt').write_text(result)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        current = get('pods', '-l', 'app=web-app')['items']
        healthy = [p for p in current if ready(p)]
        replaced = args.action == 'rollout' or not any(p['metadata']['uid'] == target['metadata']['uid'] for p in current)
        if len(healthy) >= 2 and len(current) == 2 and replaced:
            break
        time.sleep(1)
    else:
        raise RuntimeError('Two ready replicas did not recover within 180 seconds.')
    metadata['recovered_at'] = timestamp()
    time.sleep(20)
    success = True
finally:
    stop.set()
    for thread in threads:
        thread.join()
    metadata.update(finished_at=timestamp(), action_succeeded=success)
    (out / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    if samples:
        latencies = sorted(s['latency_ms'] for s in samples)
        summary = {'samples': len(samples), 'http_200': sum(s.get('status') == 200 for s in samples),
                   'errors': sum(s.get('status') != 200 or 'error' in s for s in samples),
                   'p95_ms': latencies[min(len(latencies) - 1, int(len(latencies) * .95))],
                   'max_ms': max(latencies), 'pods': dict(Counter(s.get('pod') for s in samples)),
                   'nodes': dict(Counter(s.get('node') for s in samples)),
                   'note': 'Short sequential sample; gaps between samples and longer outages outside this window are not measured.'}
        (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        print(json.dumps(summary, indent=2), flush=True)
    print(run(['bash', 'scripts/capture-evidence.sh', 'after', str(out)], cwd=ROOT), flush=True)
if not success or any(s.get('status') != 200 or 'error' in s for s in samples):
    raise SystemExit(1)
