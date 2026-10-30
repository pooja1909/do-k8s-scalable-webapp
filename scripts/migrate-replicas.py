#!/usr/bin/env python3
"""Remove only replicas from the historical client-side apply annotation.

Preserve all other historical fields, so kubectl can still remove obsolete
settings. No output means there is no replica ownership to migrate.
"""
import json
import sys

deployment = json.load(sys.stdin)
saved = deployment.get("metadata", {}).get("annotations", {}).get(
    "kubectl.kubernetes.io/last-applied-configuration"
)
if saved:
    previous = json.loads(saved)
    if "replicas" in previous.get("spec", {}):
        del previous["spec"]["replicas"]
        json.dump(previous, sys.stdout)
        print()
