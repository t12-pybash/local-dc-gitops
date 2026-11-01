#!/usr/bin/env python3
import json, sys

current = json.load(open('/tmp/current-scan.json'))
baseline = json.load(open('.secrets.baseline'))

current_keys = {(f, s['line_number'], s['type']) for f, ss in current.get('results', {}).items() for s in ss}
baseline_keys = {(f, s['line_number'], s['type']) for f, ss in baseline.get('results', {}).items() for s in ss}

new = current_keys - baseline_keys
if new:
    print('❌ New secrets found:')
    for f, ln, t in sorted(new):
        print(f'  {f}:{ln} [{t}]')
    sys.exit(1)

print('✅ No new secrets found')
