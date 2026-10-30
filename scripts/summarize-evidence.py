#!/usr/bin/env python3
"""Derive the submission's metrics from completed raw evidence, without network access."""
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / 'evidence/final'

def read(path):
    return json.loads(path.read_text())

def benchmark(name):
    folder = ROOT / name
    metadata = (folder / 'metadata.txt').read_text()
    assert 'finished_at=' in metadata and 'hey_exit=0' in metadata, f'{name} is incomplete'
    raw = (folder / 'hey.txt').read_text()
    number = lambda pattern: float(re.search(pattern, raw).group(1))
    statuses = {code: int(count) for code, count in re.findall(r'\[(\d{3})\]\s+(\d+) responses', raw)}
    error_counts = re.findall(r'^\s*\[(\d+)\]\s+.+$', raw.split('Error distribution:', 1)[1], re.M) if 'Error distribution:' in raw else []
    errors = sum(map(int, error_counts))
    hpas = sorted(folder.glob('*/hpa.json'), key=lambda path: (path.parent / 'commands.txt').read_text().split()[0])
    counts = [read(path)['status']['currentReplicas'] for path in hpas]
    node_counts = sorted(set(len(read(path.parent / 'nodes.json')['items']) for path in hpas))
    before = read(folder / 'before/deployment.json')
    return {'duration_seconds': number(r'Total:\s+([\d.]+)'),
            'requests_per_second': number(r'Requests/sec:\s+([\d.]+)'),
            'p50_ms': number(r'50%% in ([\d.]+)') * 1000,
            'p95_ms': number(r'95%% in ([\d.]+)') * 1000,
            'p99_ms': number(r'99%% in ([\d.]+)') * 1000,
            'statuses': statuses, 'request_errors': errors,
            'attempts': sum(statuses.values()) + errors,
            'start_replicas': before['spec']['replicas'], 'peak_sampled_replicas': max(counts),
            'end_sampled_replicas': counts[-1], 'node_counts': node_counts,
            'scaling_scope': 'Before, during, after load, and recovery snapshots; peak may follow the load window.'}

def reliability(name):
    folder = ROOT / name
    meta = read(folder / 'metadata.json')
    assert meta['action_succeeded'], f'{name} action did not complete'
    requests = [json.loads(line) for line in (folder / 'http.jsonl').read_text().splitlines()]
    rows = [json.loads(line) for line in (folder / 'cluster.jsonl').read_text().splitlines()]
    deployments = [item for row in rows if 'resources' in row for item in row['resources']['items'] if item['kind'] == 'Deployment']
    latencies = sorted(row['latency_ms'] for row in requests)
    return {'samples': len(requests), 'http_200': sum(row.get('status') == 200 for row in requests),
            'errors': sum(row.get('status') != 200 or 'error' in row for row in requests),
            'first_sample': requests[0]['at'], 'last_sample': requests[-1]['at'],
            'p95_ms': latencies[min(len(latencies) - 1, int(len(latencies) * .95))],
            'max_ms': max(latencies),
            'recovery_seconds': (datetime.fromisoformat(meta['recovered_at']) - datetime.fromisoformat(meta['action_started_at'])).total_seconds(),
            'minimum_sampled_available': min(d['status'].get('availableReplicas', 0) for d in deployments),
            'sampled_desired_replicas': sorted(set(d['spec']['replicas'] for d in deployments)),
            'nodes': dict(Counter(row.get('node') for row in requests))}

summary = {name: benchmark(name) for name in ['light', 'work', 'persistent-work']}
summary.update({name: reliability(name) for name in ['rollout', 'pod-recovery']})
(ROOT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
