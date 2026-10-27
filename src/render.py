#!/usr/bin/env python3
# Renders the AntiDiffamine diff, conflict markers and range-diff into
# diff.html and the job step summary. Run from inside the cloned repo.
#
# usage: render.py <from> <to> <repo> <source> <source_base> <target_base> <rebase_failed> <html_enabled>
import subprocess, sys, html

from_ref, to_ref, repo, source_sha, source_base, target_base, rebase_failed, html_enabled = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7], sys.argv[8]
rebase_failed = rebase_failed == 'true'
html_enabled = html_enabled != 'false'

import pathlib

def _read(name, default=''):
  p = pathlib.Path(name)
  return p.read_text(errors='replace') if p.exists() else default

# Change the stopped PR commit tried to make to the files it could not apply (partial mode only)
intended_diff = ''
stopped_commit = ''

if from_ref == '__partial__':
  # Second rebase failed: read diff saved before abort. Unmerged paths have no
  # content to diff, so drop their placeholder lines and show the intended change instead.
  stat = '\n'.join(l for l in _read('rebase_partial_stat.txt').splitlines() if '| Unmerged' not in l and 'files changed' not in l and 'file changed' not in l).strip()
  stat = stat or '(no changes could be applied before the conflict)'
  raw_diff = '\n'.join(l for l in _read('rebase_partial_diff.txt').splitlines() if not l.startswith('* Unmerged path '))
  commits  = _read('rebase_partial_commits.txt', '').strip()
  intended_diff = _read('rebase_intended_diff.txt')
  stopped_commit = _read('rebase_stopped_commit.txt').strip()
else:
  stat = subprocess.check_output(
    ['git', 'diff', '--stat', from_ref, to_ref]
  ).decode('utf-8', errors='replace').strip()
  raw_diff = subprocess.check_output(
    ['git', 'diff', '--unified=3', from_ref, to_ref]
  ).decode('utf-8', errors='replace')
  commits = subprocess.check_output(
    ['git', 'log', '--oneline', f'{from_ref}..{to_ref}']
  ).decode('utf-8', errors='replace').strip()

# range-diff: old range = source_base..source_sha, new range = target_base..to_ref,
# so it shows how the author's commits were rewritten, added or dropped
range_diff = ''
range_diff_error = ''
try:
  range_diff = subprocess.check_output(
    ['git', 'range-diff', f'{source_base}..{source_sha}', f'{target_base}..{to_ref}'],
    stderr=subprocess.PIPE
  ).decode('utf-8', errors='replace').strip()
  if not range_diff:
    range_diff_error = 'No output — the commit ranges may be empty or identical.'
except subprocess.CalledProcessError as e:
  range_diff_error = f'git range-diff failed: {e.stderr.decode("utf-8", errors="replace").strip()}'

def render_range_diff(raw):
  import re
  commit_re = re.compile(r'^\s*(\d+|-):  \S+ (=|!|<|>) (\d+|-):')
  S = 'font-family:ui-monospace,monospace;font-size:12px;padding:1px 6px;white-space:pre-wrap;word-break:break-all;vertical-align:top'
  M = f'{S};width:24px;text-align:center;font-weight:700;border-right:1px solid #d0d7de'
  commit_row  = {'=':'background:#f6f8fa','!':'background:#fff8c5','<':'background:#ffebe9','>':'background:#e6ffec'}
  commit_mark = {'=':'color:#57606a',     '!':'color:#9a6700',    '<':'color:#82071e',    '>':'color:#116329'}
  rows = []
  file_additions = {}
  current_file = None
  for line in raw.splitlines():
    m = commit_re.match(line)
    if m:
      sym = m.group(2)
      rows.append(f'<tr style="{commit_row[sym]}"><td style="{M};{commit_mark[sym]}">{html.escape(sym)}</td><td style="{S}">{html.escape(line)}</td></tr>')
    elif line.startswith('    +++'):
      fm = re.match(r'    \+\+\+ b/(.*)', line)
      current_file = fm.group(1) if fm else line[8:]
      file_additions.setdefault(current_file, [0, 0])
      rows.append(f'<tr><td style="{M}"></td><td style="{S};color:#116329;font-weight:600">{html.escape(line)}</td></tr>')
    elif line.startswith('    ---'):
      rows.append(f'<tr><td style="{M}"></td><td style="{S};color:#82071e;font-weight:600">{html.escape(line)}</td></tr>')
    elif line.startswith('    ++'):
      if current_file: file_additions[current_file][0] += 1
      rows.append(f'<tr style="background:#e6ffec"><td style="{M};color:#116329">++</td><td style="{S};color:#116329">{html.escape(line[6:])}</td></tr>')
    elif line.startswith('    +-'):
      if current_file: file_additions[current_file][1] += 1
      rows.append(f'<tr style="background:#ffebe9"><td style="{M};color:#82071e">+-</td><td style="{S};color:#82071e">{html.escape(line[6:])}</td></tr>')
    elif line.startswith('    @@'):
      rows.append(f'<tr style="background:#ddf4ff"><td style="{M}"></td><td style="{S};color:#0550ae">{html.escape(line)}</td></tr>')
    else:
      rows.append(f'<tr><td style="{M}"></td><td style="{S}">{html.escape(line)}</td></tr>')
  summary = ''
  if file_additions:
    sr = []
    for fname, (adds, dels) in file_additions.items():
      bar = f'<span style="color:#116329">{"+" * min(adds,10)}</span><span style="color:#82071e">{"-" * min(dels,10)}</span>'
      sr.append(f'<tr><td style="padding:1px 8px;{S}">{html.escape(fname)}</td><td style="padding:1px 8px;white-space:nowrap">{bar} <span style="color:#116329">+{adds}</span> <span style="color:#82071e">-{dels}</span></td></tr>')
    summary = f'<div style="background:#f6f8fa;border-bottom:1px solid #d0d7de;padding:8px 0"><table>{"".join(sr)}</table></div>'
  return summary + f'<table style="width:100%;border-collapse:collapse">{"".join(rows)}</table>'

# Split diff into per-file blocks
def split_blocks(diff):
  blocks = []
  current = []
  for line in diff.splitlines():
    if line.startswith('diff --git ') and current:
      blocks.append('\n'.join(current))
      current = []
    current.append(line)
  if current:
    blocks.append('\n'.join(current))
  return [b for b in blocks if b.strip()]

file_blocks = split_blocks(raw_diff)
intended_blocks = split_blocks(intended_diff)
stopped_label = f' — from commit {stopped_commit}' if stopped_commit else ''

def render_file(block):
  lines = block.splitlines()
  filename = ''
  for l in lines:
    if l.startswith('+++ b/'):
      filename = l[6:]
      break
  rows = []
  old_ln, new_ln = 0, 0
  for l in lines:
    if l.startswith('@@'):
      import re
      m = re.search(r'-(\d+)(?:,\d+)? \+(\d+)', l)
      if m:
        old_ln, new_ln = int(m.group(1)), int(m.group(2))
      rows.append(f'<tr><td colspan="3" class="hunk">{html.escape(l)}</td></tr>')
    elif l.startswith('---') or l.startswith('+++') or l.startswith('diff') or l.startswith('index'):
      continue
    elif l.startswith('-'):
      rows.append(f'<tr class="del"><td class="ln">{old_ln}</td><td class="ln"></td><td class="code">{html.escape(l)}</td></tr>')
      old_ln += 1
    elif l.startswith('+'):
      rows.append(f'<tr class="add"><td class="ln"></td><td class="ln">{new_ln}</td><td class="code">{html.escape(l)}</td></tr>')
      new_ln += 1
    else:
      rows.append(f'<tr><td class="ln">{old_ln}</td><td class="ln">{new_ln}</td><td class="code">{html.escape(l)}</td></tr>')
      old_ln += 1; new_ln += 1
  table = '<table class="diff">' + ''.join(rows) + '</table>'
  return filename, table

# Parse conflict_details.txt if present
import os, re
conflict_sections = []  # list of (filename, lines)
if os.path.exists('conflict_details.txt'):
  with open('conflict_details.txt') as cf:
    raw = cf.read()
  cur_file, cur_lines = None, []
  for line in raw.splitlines():
    if line.startswith('=== ') and line.endswith(' ==='):
      if cur_file is not None:
        conflict_sections.append((cur_file, cur_lines))
      cur_file = line[4:-4]
      cur_lines = []
    elif cur_file is not None:
      cur_lines.append(line)
  if cur_file is not None:
    conflict_sections.append((cur_file, cur_lines))

# Conflict type per file from `git status --porcelain`. During a rebase, "us" is
# the base branch and "them" is the PR commit being replayed.
CONFLICT_KINDS = {
  'UU': 'modified on both the base branch and in the PR',
  'AA': 'added on both the base branch and in the PR, with different content',
  'DU': 'deleted on the base branch, modified in the PR',
  'UD': 'modified on the base branch, deleted in the PR',
  'AU': 'added on the base branch, conflicting with the PR',
  'UA': 'added in the PR, conflicting with the base branch',
  'DD': 'deleted on both sides',
}
conflict_kinds = {}
for line in _read('conflict_status.txt').splitlines():
  if len(line) > 3:
    conflict_kinds[line[3:]] = CONFLICT_KINDS.get(line[:2], f'unmerged ({line[:2]})')

def render_conflict_file(filename, lines, context=3):
  # Conflicts without markers (modify/delete, ...) have nothing to highlight; say what happened
  if not any(l.startswith('<<<<<<<') for l in lines):
    kind = conflict_kinds.get(filename, 'conflict without content markers')
    S = 'font-family:ui-monospace,monospace;font-size:12px;padding:6px 8px'
    return f'<table style="width:100%;border-collapse:collapse"><tr style="background:#fff8c5"><td style="{S};color:#6e4f0a">{html.escape(filename)}: {html.escape(kind)}. There are no conflict markers to show.</td></tr></table>'
  # Find conflict block ranges (0-based indices)
  conflict_ranges = []
  i = 0
  while i < len(lines):
    if lines[i].startswith('<<<<<<<'):
      start = i
      while i < len(lines) and not lines[i].startswith('>>>>>>>'):
        i += 1
      conflict_ranges.append((start, i))
    i += 1
  # Expand each conflict with context lines and merge overlapping windows
  windows = []
  for s, e in conflict_ranges:
    ws, we = max(0, s - context), min(len(lines) - 1, e + context)
    if windows and ws <= windows[-1][1] + 1:
      windows[-1] = (windows[-1][0], max(windows[-1][1], we))
    else:
      windows.append([ws, we])
  S  = 'font-family:ui-monospace,monospace;font-size:12px;padding:1px 8px;white-space:pre-wrap;word-break:break-all;vertical-align:top'
  LN = f'{S};width:1%;min-width:40px;color:#57606a;text-align:right;border-right:1px solid #d0d7de'
  LB = f'{S};width:48px;font-size:10px;font-weight:600;text-align:center;border-right:1px solid #d0d7de'
  rows = []
  prev_end = -1
  skip_tr = f'<tr style="background:#ddf4ff"><td colspan="3" style="{S};color:#0550ae;padding:4px 8px">{{msg}}</td></tr>'
  for ws, we in windows:
    if prev_end >= 0:
      rows.append(skip_tr.format(msg=f'... {ws - prev_end - 1} lines skipped ...'))
    elif ws > 0:
      rows.append(skip_tr.format(msg=f'... {ws} lines skipped ...'))
    region = None
    for idx in range(ws, we + 1):
      ln = idx + 1
      l = lines[idx]
      if l.startswith('<<<<<<<'):
        region = 'ours'
        rows.append(f'<tr style="background:#fdb8c0"><td colspan="2" style="{LN};color:#86181d;font-weight:600">{ln}</td><td style="{S};color:#86181d;font-weight:600">{html.escape(l)}</td></tr>')
      elif l.startswith('======='):
        region = 'theirs'
        rows.append(f'<tr style="background:#eee"><td colspan="2" style="{LN};color:#57606a;font-weight:600">{ln}</td><td style="{S};color:#57606a;font-weight:600">{html.escape(l)}</td></tr>')
      elif l.startswith('>>>>>>>'):
        region = None
        rows.append(f'<tr style="background:#acf2bd"><td colspan="2" style="{LN};color:#1a7f37;font-weight:600">{ln}</td><td style="{S};color:#1a7f37;font-weight:600">{html.escape(l)}</td></tr>')
      elif region == 'ours':
        rows.append(f'<tr style="background:#ffeef0"><td style="{LN}">{ln}</td><td style="{LB};background:#fdb8c0;color:#86181d">base</td><td style="{S}">{html.escape(l)}</td></tr>')
      elif region == 'theirs':
        rows.append(f'<tr style="background:#e6ffec"><td style="{LN}">{ln}</td><td style="{LB};background:#acf2bd;color:#1a7f37">PR</td><td style="{S}">{html.escape(l)}</td></tr>')
      else:
        rows.append(f'<tr><td style="{LN}">{ln}</td><td style="{LB}"></td><td style="{S}">{html.escape(l)}</td></tr>')
    prev_end = we
  tail = len(lines) - 1 - prev_end
  if tail > 0:
    rows.append(skip_tr.format(msg=f'... {tail} lines skipped ...'))
  return f'<table style="width:100%;border-collapse:collapse">{"".join(rows)}</table>'

css = """<style>
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;font-size:14px;color:#24292f;margin:0;padding:16px}
.header{background:#f6f8fa;border:1px solid #d0d7de;border-radius:6px;padding:16px;margin-bottom:16px}
.header h2{margin:0 0 8px;font-size:20px}
.stat{font-family:ui-monospace,monospace;font-size:12px;white-space:pre;background:#f6f8fa;border:1px solid #d0d7de;border-radius:6px;padding:12px;margin-bottom:16px}
details{border:1px solid #d0d7de;border-radius:6px;margin-bottom:8px;overflow:hidden}
summary{background:#f6f8fa;padding:8px 12px;cursor:pointer;font-family:ui-monospace,monospace;font-size:12px;font-weight:600}
summary:hover{background:#eef1f4}
.conflict-header{background:#fff8c5;border:1px solid #d4a72c;border-radius:6px;padding:10px 14px;margin-bottom:12px;font-weight:600;color:#6e4f0a}
.conflict-header summary{background:#fff8c5;color:#6e4f0a}
table.diff{width:100%;border-collapse:collapse;font-family:ui-monospace,monospace;font-size:12px}
.diff td{padding:1px 8px;vertical-align:top;white-space:pre-wrap;word-break:break-all}
.diff .ln{width:1%;min-width:40px;color:#57606a;text-align:right;user-select:none;border-right:1px solid #d0d7de}
.diff .code{width:100%}
.diff tr.add{background:#e6ffec}.diff tr.add .code{color:#116329}
.diff tr.del{background:#ffebe9}.diff tr.del .code{color:#82071e}
.diff tr.add .ln,.diff tr.del .ln{background:inherit}
.hunk{background:#ddf4ff;color:#0550ae;padding:4px 8px}
.commits{font-family:ui-monospace,monospace;font-size:12px;background:#f6f8fa;border:1px solid #d0d7de;border-radius:6px;padding:12px;margin-bottom:16px}
.conflict-label{width:48px;font-size:10px;font-weight:600;text-align:center;user-select:none;border-right:1px solid #d0d7de;color:#57606a}
.conflict-ours{background:#ffeef0}.conflict-ours .conflict-label{background:#fdb8c0;color:#86181d}
.conflict-theirs{background:#e6ffec}.conflict-theirs .conflict-label{background:#acf2bd;color:#1a7f37}
.ours-marker{background:#fdb8c0;color:#86181d;font-weight:600}
.theirs-marker{background:#acf2bd;color:#1a7f37;font-weight:600}
.sep-marker{background:#eee;color:#57606a;font-weight:600}
.range-diff td{padding:1px 6px;font-family:ui-monospace,monospace;font-size:12px;white-space:pre-wrap;word-break:break-all}
.rd-marker{width:24px;text-align:center;font-weight:700;user-select:none;border-right:1px solid #d0d7de;color:#57606a}
.rd-line{width:100%}
.rd-same{background:#f6f8fa}.rd-same .rd-marker{color:#57606a}
.rd-changed{background:#fff8c5}.rd-changed .rd-marker{color:#9a6700}
.rd-removed{background:#ffebe9}.rd-removed .rd-marker{color:#82071e}
.rd-added{background:#e6ffec}.rd-added .rd-marker{color:#116329}
.rd-indent{width:16px;text-align:center;font-weight:700;user-select:none;border-right:1px solid #d0d7de;color:#57606a}
.rd-sign{font-weight:700}
.rd-code{font-family:ui-monospace,monospace;font-size:12px}
.rd-num{color:#57606a}
.rd-sha{color:#0550ae;font-weight:600}
.rd-msg{color:#24292f}
.rd-sym{font-weight:700;padding:0 4px}
.rd-sym-eq{color:#57606a}.rd-sym-changed{color:#9a6700}.rd-sym-removed{color:#82071e}.rd-sym-added{color:#116329}
.rd-same{background:#f6f8fa}.rd-same .rd-marker{color:#57606a}
.rd-changed{background:#fff8c5}.rd-changed .rd-marker{color:#9a6700}
.rd-removed{background:#ffebe9}.rd-removed .rd-marker{color:#82071e}
.rd-added{background:#e6ffec}.rd-added .rd-marker{color:#116329}
.rd-hunk{background:#ddf4ff}.rd-hunk .rd-code{color:#0550ae}
.rd-ctx{background:#f6f8fa}
.rd-del{background:#ffebe9}.rd-del .rd-code{color:#82071e}.rd-del .rd-indent{color:#82071e}
.rd-add{background:#e6ffec}.rd-add .rd-code{color:#116329}.rd-add .rd-indent{color:#116329}
.rd-fh-del{background:#ffebe9}.rd-fh-del .rd-code{color:#57606a;font-style:italic}
.rd-fh-add{background:#e6ffec}.rd-fh-add .rd-code{color:#57606a;font-style:italic}
</style>"""

compare_url = f"https://github.com/{repo}/compare/{source_sha[:7]}..{to_ref[:7]}"
body = css
body += '<div style="background:#0969da;color:#fff;padding:10px 20px;margin:-16px -16px 16px;font-size:16px;font-weight:700;letter-spacing:0.03em">🧪 AntiDiffamine</div>\n'
body += f'<p style="color:#57606a;font-size:13px;margin-bottom:8px">This page shows a visual comparison of three views of a force-push: the <a href="{compare_url}">original Git diff</a>, the <strong>🧪 AntiDiffamine diff</strong>, and the <strong>📊 range-diff</strong>.</p>\n'
body += '<p style="color:#57606a;font-size:13px;margin-bottom:16px">On <em>hetero-ancestral</em> pairs,  where the source (before) and target (after) commits of a force-push do not share the same ancestor on their base branch,  a plain <code>git diff</code> conflates with branch updates. AntiDiffamine rebases the source range onto the target base to isolate changes within the PR-scope. The git range-diff comparison match and compare ranges of commits pairing using a cost fudge factor (default=60).</p>\n'
if rebase_failed:
  body += '<div style="background:#fff8c5;border:1px solid #d4a72c;border-radius:6px;padding:12px 16px;margin-bottom:16px;color:#6e4f0a;font-weight:600">⚠️ AntiDiffamine failed to resolve merge conflicts automatically. The diff, conflict markers, and range-diff below are based on the original commits without successful rebase — they are partial and may not be accurate.</div>\n'
body += f'<div class="header"><h2>Comparing <code>{source_sha[:7]}</code> → <code>{to_ref[:7]}</code></h2>'
body += f'<a href="{compare_url}">{compare_url}</a></div>\n'
if commits:
  body += f'<div class="commits"><strong>Commits</strong><br><pre>{html.escape(commits)}</pre></div>\n'
body += '<div style="border:2px solid #0969da;border-radius:8px;padding:16px;margin-bottom:16px">\n'
body += '<div style="font-size:13px;font-weight:700;color:#0969da;margin-bottom:10px;letter-spacing:0.02em">🧪 AntiDiffamine diff</div>\n'
body += f'<div class="stat"><strong>Files changed</strong><br>{html.escape(stat)}</div>\n'
for block in file_blocks:
  if not block.strip():
    continue
  fname, table = render_file(block)
  body += f'<details><summary>{html.escape(fname)}</summary>{table}</details>\n'
if intended_blocks:
  body += f'<div class="conflict-header" style="margin-top:12px">⚠️ Intended change (could not be applied){html.escape(stopped_label)}</div>\n'
  for block in intended_blocks:
    fname, table = render_file(block)
    body += f'<details class="conflict-header"><summary>{html.escape(fname)}</summary>{table}</details>\n'
if conflict_sections:
  body += '<div class="conflict-header" style="margin-top:12px">⚠️ Merge Conflicts detected during first rebase</div>\n'
  for fname, lines in conflict_sections:
    table = render_conflict_file(fname, lines)
    body += f'<details class="conflict-header"><summary>⚠️ CONFLICT: {html.escape(fname)}</summary>{table}</details>\n'
body += '</div>\n'
if range_diff:
  rd_table = render_range_diff(range_diff)
  body += f'<details><summary>📊 Range-diff</summary>{rd_table}</details>\n'
else:
  body += f'<details><summary>📊 Range-diff</summary><div style="padding:8px 12px;font-family:ui-monospace,monospace;font-size:12px;color:#57606a">{html.escape(range_diff_error)}</div></details>\n'

if html_enabled:
  with open('diff.html', 'w') as f:
    f.write(body)

# Write a markdown link to the summary
summary_path = os.environ.get('GITHUB_STEP_SUMMARY', '/dev/stdout')
with open(summary_path, 'a') as f:
  f.write("# 🧪 AntiDiffamine\n\n")
  f.write(f"Comparing `{source_sha[:7]}` → `{to_ref[:7]}`\n\n")
  f.write(f"This summary shows three views of a force-push: the [original Git diff]({compare_url}), the **🧪 AntiDiffamine diff** (how the rebased result differs from the base branch), and the **📊 range-diff** (how individual commits were rewritten).\n\n")
  f.write(f"On _hetero-ancestral_ pairs — where the before and after commits do not share a common ancestor — a plain `git diff` conflates unrelated history and produces a misleading result. AntiDiffamine rebases the source range onto the target base to isolate only the intentional change. The range-diff pairing uses the default cost fudge factor of 60.\n\n")
  if rebase_failed:
    f.write('> [!WARNING]\n> **AntiDiffamine failed to resolve merge conflicts automatically.** The diff, conflict markers, and range-diff below are based on the original commits without successful rebase — they are partial and may not be accurate.\n\n')
  # 1. AntiDiffamine diff (framed section)
  f.write('<div style="border:2px solid #0969da;border-radius:8px;padding:16px;margin-bottom:16px">\n\n')
  f.write('### 🧪 AntiDiffamine diff\n\n')
  f.write(f"```\n{stat}\n```\n\n")
  for block in file_blocks:
    if not block.strip():
      continue
    blines = block.splitlines()
    fname = next((l[6:] for l in blines if l.startswith('+++ b/')), 'unknown')
    f.write(f"<details><summary><code>{html.escape(fname)}</code></summary>\n\n```diff\n{block}\n```\n\n</details>\n\n")
  if intended_blocks:
    f.write(f"#### ⚠️ Intended change (could not be applied){stopped_label}\n\n")
    for block in intended_blocks:
      fname = next((l[6:] for l in block.splitlines() if l.startswith('+++ b/')), 'unknown')
      f.write(f"<details><summary><code>{html.escape(fname)}</code></summary>\n\n```diff\n{block}\n```\n\n</details>\n\n")
  f.write('</div>\n\n')
  # 2. Merge conflicts with line numbers and context
  if conflict_sections:
    f.write(f"### ⚠️ Merge Conflicts\n\n")
    for fname, lines in conflict_sections:
      table = render_conflict_file(fname, lines)
      f.write(f"<details><summary>⚠️ CONFLICT: <code>{html.escape(fname)}</code></summary>\n{table}\n</details>\n\n")
  # 3. Range-diff
  f.write('<div style="border:2px solid #0969da;border-radius:8px;padding:16px;margin-bottom:16px">\n\n')
  f.write('### 📊 Range-diff\n\n')
  if range_diff:
    rd_html = render_range_diff(range_diff)
    f.write(f"<details><summary>Range-diff output</summary>\n{rd_html}\n</details>\n\n")
  else:
    f.write(f"> ⚠️ {range_diff_error}\n\n")
  f.write('</div>\n\n')
