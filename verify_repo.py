#!/usr/bin/env python3
"""Pre-publish gate for the staged skills repo. Any FAIL blocks the push."""
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent
SKILLS = REPO / 'skills'
fails, warns = [], []


def shipped_files():
    """Everything a consumer downloads: the skill tree plus repo metadata.
    The gate's own source is skipped — it necessarily contains the very patterns
    it searches for, and it is not part of any skill bundle."""
    meta = {'README.md', 'LICENSE', 'skills.sh.json', 'sync.sh'}
    for f in REPO.rglob('*'):
        if not f.is_file():
            continue
        if f.is_relative_to(SKILLS) or f.name in meta:
            yield f

skills = sorted(p.parent for p in SKILLS.rglob('SKILL.md'))
print(f'skills found: {len(skills)}\n')

# 1. structure: name matches dirname, description present, body non-empty
for d in skills:
    text = (d / 'SKILL.md').read_text(errors='replace')
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.S)
    if not m:
        fails.append(f'{d.name}: frontmatter does not parse')
        continue
    fm = dict(
        (k.strip(), v.strip().strip('"\''))
        for k, v in (l.split(':', 1) for l in m.group(1).splitlines()
                     if ':' in l and not l.startswith((' ', '\t', '#')))
    )
    if fm.get('name') != d.name:
        fails.append(f'{d.name}: frontmatter name={fm.get("name")!r}')
    if not fm.get('description'):
        fails.append(f'{d.name}: no description')
    if not text[m.end():].strip():
        fails.append(f'{d.name}: empty body')
    if not fm.get('license'):
        warns.append(f'{d.name}: no license field')
    if len(fm.get('description', '')) > 60:
        warns.append(f'{d.name}: description {len(fm["description"])}ch (>60, repo house rule)')

# 2. secrets
SECRET = re.compile(
    r'(gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}'
    r'|[0-9]{8,10}:AA[A-Za-z0-9_-]{30,}|AKIA[0-9A-Z]{16}'
    r'|-----BEGIN [A-Z ]*PRIVATE KEY|eyJ[A-Za-z0-9_-]{20,}\.)')
for f in shipped_files():
    if f.suffix not in {'.md', '.py', '.sh', '.json'}:
        continue
    try:
        for i, line in enumerate(f.read_text(errors='replace').splitlines(), 1):
            if SECRET.search(line):
                fails.append(f'SECRET {f.relative_to(REPO)}:{i}')
    except OSError:
        pass

# 3. personal identifiers / machine-local paths
PII = re.compile(r'420604246961|8708695574|/opt/data|/Users/mimi|mimi1vx@|osukup|suse\.com')
for f in shipped_files():
    if f.suffix not in {'.md', '.py', '.sh', '.json'}:
        continue
    for i, line in enumerate(f.read_text(errors='replace').splitlines(), 1):
        if PII.search(line):
            # mimi1vx as the repo/author identity is fine
            if 'mimi1vx' in line and not re.search(r'mimi1vx@|osukup|suse\.com', line):
                continue
            fails.append(f'PII {f.relative_to(REPO)}:{i}: {line.strip()[:70]}')

# 4. junk that must not ship
for f in REPO.rglob('*'):
    if f.is_file() and ('__pycache__' in f.parts or f.suffix in {'.pyc', '.DS_Store'}):
        fails.append(f'junk {f.relative_to(REPO)}')

# 5. skills.sh.json covers every skill exactly once
groups = json.loads((REPO / 'skills.sh.json').read_text())['groupings']
listed = [s for g in groups for s in g['skills']]
names = sorted(d.name for d in skills)
if sorted(listed) != names:
    fails.append(f'skills.sh.json mismatch: missing={set(names)-set(listed)} '
                 f'extra={set(listed)-set(names)}')
if len(listed) != len(set(listed)):
    fails.append('skills.sh.json lists a skill twice')

# 6. every README link resolves
readme = (REPO / 'README.md').read_text()
for link in re.findall(r'\]\((skills/[^)]+)\)', readme):
    if not (REPO / link).is_dir():
        fails.append(f'README link dead: {link}')
for skill in names:
    if skill not in readme:
        warns.append(f'{skill}: not mentioned in README')

# 7. scripts referenced by SKILL.md prose actually exist
for d in skills:
    text = (d / 'SKILL.md').read_text(errors='replace')
    for ref in set(re.findall(r'`((?:scripts|references|templates)/[A-Za-z0-9_.-]+)`', text)):
        if not (d / ref).exists():
            warns.append(f'{d.name}: prose references missing {ref}')

print(f'WARN {len(warns)}')
for w in warns:
    print(f'  ~ {w}')
print(f'\nFAIL {len(fails)}')
for f in fails:
    print(f'  ! {f}')
print('\nRESULT:', 'BLOCKED' if fails else 'CLEAN — safe to publish')
sys.exit(1 if fails else 0)