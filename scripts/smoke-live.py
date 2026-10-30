#!/usr/bin/env python3
"""Bounded public HTTP checks; prints JSON evidence. Supply the demo LB IP."""
from datetime import datetime, timezone
import http.client
import json
import sys

host = sys.argv[1]
expected_version = sys.argv[2] if len(sys.argv) > 2 else '1.0.2'
checks = [('/', 200), ('/healthz', 200), ('/readyz', 200), ('/api/info', 200),
          ('//', 400), ('/work?ms=', 400), ('/work?ms=NaN', 400),
          ('/work?ms=-1', 400), ('/work?ms=1e309', 400),
          ('/work?ms=0', 200), ('/work?ms=10000', 200), ('/missing', 404), ('/api/info', 200)]
rows = []
for path, expected in checks:
    connection = http.client.HTTPConnection(host, timeout=10)
    connection.request('GET', path)
    response = connection.getresponse()
    body = response.read().decode()
    row = {'at': datetime.now(timezone.utc).isoformat(), 'path': path,
           'expected_status': expected, 'status': response.status, 'passed': response.status == expected}
    if path == '/api/info' and response.status == 200:
        row['info'] = json.loads(body)
        row['passed'] &= row['info']['version'] == expected_version
    if path.startswith('/work?') and response.status == 200:
        row['work'] = json.loads(body)
        row['passed'] &= row['work']['workedMs'] == (0 if path.endswith('=0') else 500)
    rows.append(row)
    connection.close()
result = {'host': host, 'expected_version': expected_version,
          'checks': rows, 'passed': all(x['passed'] for x in rows)}
print(json.dumps(result, indent=2))
raise SystemExit(0 if result['passed'] else 1)
