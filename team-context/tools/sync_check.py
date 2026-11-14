#!/usr/bin/env python3
"""Pre-commit gate for team-context/: copy staged files in (optional) and refuse anything risky.
Usage: python tools/sync_check.py [--copy SRC DEST_REL] ...   then run with no args to just check.
Fails (exit 1) on: denylisted names/extensions, files > 50 MB, likely secrets, team-private info (lead's name, agent UUIDs, token holders), absolute machine paths such as /workspace, /tmp or /home (warning only).
Team-private names are NOT stored here (A1-18): set SYNC_CHECK_DENY='name1,name2' or list them, one per line,
in an untracked file given by SYNC_CHECK_DENY_FILE (default ~/.config/team-context/sync_check_deny)."""
import os, re, sys, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAP = 50 * 1024 * 1024
DENY_EXT = {'.nc', '.nc4', '.h5', '.hdf', '.zarr', '.npz', '.parquet', '.log', '.zip', '.shp', '.dbf', '.shx'}
DENY_NAME = {'.env', '.netrc', '.cdsapirc', 'cookies.txt', '.urs_cookies'}
SECRET = re.compile(r'(eyJ[A-Za-z0-9_-]{30,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|(PASSWORD|TOKEN|API_KEY)\s*=\s*["\']?[A-Za-z0-9:_-]{12,})')
_deny = [x.strip() for x in os.environ.get('SYNC_CHECK_DENY', '').split(',') if x.strip()]
_deny_file = os.path.expanduser(os.environ.get('SYNC_CHECK_DENY_FILE', '~/.config/team-context/sync_check_deny'))
if os.path.isfile(_deny_file):
    _deny += [l.strip() for l in open(_deny_file, encoding='utf-8') if l.strip() and not l.startswith('#')]
_names = ''.join(re.escape(n) + '|' for n in _deny)
PRIVATE = re.compile(r'(?i)(' + _names + r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|(holds?|held|gave|only with|lives only|given to|only i hold)[^\n]{0,60}(TOKEN|API_KEY|CDSAPI_KEY)|(TOKEN|API_KEY|CDSAPI_KEY)[^\n]{0,60}(holds?|held by|only with|lives only|given to))')
# machine-specific absolute paths in quotes or after whitespace (A1-11); built from parts so this file is not self-matching
ABS_PATH = re.compile(r'''(?:^|[\s"'(=])/(?:''' + '|'.join(['work' + 'space', 't' + 'mp', 'ho' + 'me']) + r''')/''', re.M)
args = sys.argv[1:]
while args[:1] == ['--copy']:
    src, dst = args[1], os.path.join(ROOT, args[2]); args = args[3:]
    os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy2(src, dst)
bad, warn = [], []
for d, dirs, files in os.walk(ROOT):
    dirs[:] = [x for x in dirs if x not in {'.git', '__pycache__', 'cache', 'raw', 'global'}]
    for f in files:
        p = os.path.join(d, f); r = os.path.relpath(p, ROOT)
        if f in DENY_NAME or os.path.splitext(f)[1].lower() in DENY_EXT: bad.append(f'denylisted: {r}'); continue
        if os.path.getsize(p) > CAP: bad.append(f'>50MB: {r}'); continue
        try: t = open(p, encoding='utf-8', errors='ignore').read()
        except Exception: continue
        if SECRET.search(t): bad.append(f'possible secret: {r}')
        if r != 'tools/sync_check.py':
            m = PRIVATE.search(t)
            if m: bad.append(f'private team info (name/agent id/token holder) {m.group(0)[:40]!r}: {r}')
        if ABS_PATH.search(t) and r != 'tools/sync_check.py': warn.append(r)
print(f'{len(warn)} files still contain absolute machine paths (rewrite before commit):', *warn[:40], sep='\n  ')
if bad: print('BLOCKED:', *bad, sep='\n  '); sys.exit(1)
print('OK: no denylisted, oversized or secret-looking files')
