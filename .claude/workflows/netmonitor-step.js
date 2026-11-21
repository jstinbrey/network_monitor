export const meta = {
  name: 'netmonitor-step',
  description: 'Build and test one NetMonitor build step in a scratch copy, ready for the student to type',
  whenToUse: 'NetMonitor (CCS 234): the next or a named step of docs/Network-Monitor-Build-Steps.md. args: {scratch: "<absolute scratch folder>", step?: "6.2"}; without step, the first step not yet committed.',
  phases: [
    { title: 'Scope', detail: 'read the plan section and the code the step touches' },
    { title: 'Build', detail: 'implement it in a scratch copy, pytest until green' },
    { title: 'Verify', detail: 'code review and a real-window check, in parallel' },
    { title: 'Fix', detail: 'only when Verify found problems' },
  ],
}

// The student types every change from the chat, so no agent may touch the repository: all work happens in a copy.
const REPO = 'D:\\Claude Code\\Final Projects\\CCS 234 - Network and Communications'
const SRC = REPO + '\\SourceCode'
const PY = SRC + '\\.venv\\Scripts\\python.exe'

if (!args || !args.scratch) throw new Error('Pass args.scratch: an absolute folder for the scratch copy (the session scratchpad).')
const SCRATCH = args.scratch

const RULES = `Project: NetMonitor, a Windows Python 3.13 / CustomTkinter network monitor (CCS 234 final project).
Repository: ${REPO}. Code: ${SRC}. Build plan: ${REPO}\\docs\\Network-Monitor-Build-Steps.md.
Hard rules:
- NEVER create, edit or delete anything under ${REPO}, and never run a git command that changes it (no add, commit, checkout,
  stash, reset). The student types every change themselves. Read the repository freely; write only under ${SCRATCH}.
- Layers: gui -> services.py -> core/ and store.py. Views call services only through gui.worker.run_async. Every admin-only
  service function starts with require_admin(); the GUI hiding a button is a convenience, not the check.
- Smallest complete change: reuse helpers already in the codebase, no code "for later", no new dependencies. A known limit
  gets a comment "# shortcut: <the limit>, <when to upgrade>". Keep the house style: module and function docstrings, short
  why-comments, two blank lines between top-level definitions, lines under about 120 characters.
- New branchy logic gets a small pytest test.
- Run Python with "${PY}". Run pytest from inside the scratch copy:
  "${PY}" -m pytest -q -p no:cacheprovider --basetemp="<copy>\\pytest_tmp"
- Never send the student's name, email or other personal details to an external service.`

const SCOPE = {
  type: 'object',
  properties: {
    step: { type: 'string', description: 'e.g. "6.2"' },
    title: { type: 'string' },
    files: { type: 'array', items: { type: 'object', properties: {
      path: { type: 'string', description: 'relative to SourceCode' },
      change: { type: 'string' } }, required: ['path', 'change'] } },
    tests: { type: 'array', items: { type: 'string' } },
    checkpoint: { type: 'array', items: { type: 'string' }, description: 'what the student checks by hand in the window' },
    deviations: { type: 'array', items: { type: 'string' }, description: 'where the smallest correct code differs from the plan, and why' },
    risks: { type: 'array', items: { type: 'string' } },
  },
  required: ['step', 'title', 'files', 'tests', 'checkpoint', 'deviations', 'risks'],
}
const BUILD = {
  type: 'object',
  properties: {
    folder: { type: 'string' },
    changed: { type: 'array', items: { type: 'string' }, description: 'relative paths, new or modified' },
    pytest: { type: 'string', description: 'the final summary line, e.g. "87 passed in 3.1s"' },
    deviations: { type: 'array', items: { type: 'string' } },
    shortcuts: { type: 'array', items: { type: 'string' } },
  },
  required: ['folder', 'changed', 'pytest', 'deviations', 'shortcuts'],
}
const REVIEW = {
  type: 'object',
  properties: { findings: { type: 'array', items: { type: 'object', properties: {
    file: { type: 'string' }, problem: { type: 'string' }, scenario: { type: 'string' }, fix: { type: 'string' } },
    required: ['file', 'problem', 'scenario', 'fix'] } } },
  required: ['findings'],
}
const GUI = {
  type: 'object',
  properties: {
    checks: { type: 'array', items: { type: 'object', properties: {
      check: { type: 'string' }, passed: { type: 'boolean' }, observed: { type: 'string' } },
      required: ['check', 'passed', 'observed'] } },
    screenshots: { type: 'array', items: { type: 'string' } },
    notChecked: { type: 'array', items: { type: 'string' } },
  },
  required: ['checks', 'screenshots', 'notChecked'],
}
const FIX = {
  type: 'object',
  properties: {
    fixed: { type: 'array', items: { type: 'string' } },
    skipped: { type: 'array', items: { type: 'string' }, description: 'finding, and why it needed no change' },
    pytest: { type: 'string' },
  },
  required: ['fixed', 'skipped', 'pytest'],
}

phase('Scope')
const which = args.step
  ? `Step ${args.step}`
  : `the first step of the plan not yet committed (compare \`git -C "${REPO}" log --oneline -20\`, whose messages start "step X.Y:", with the plan's step headings)`
const scope = await agent(`${RULES}

Find ${which}. Read that step's section of the plan in full, then read every source file and test it touches.
Map the step onto the real code: each file to create or change and what changes, the tests to add, and the checkpoint items
the student checks by hand. List where the smallest correct implementation should differ from the plan text, and why
(for example: a field nobody fills yet, a helper that already exists). Note anything in the current code that would break.`,
  { label: 'scope', schema: SCOPE })
if (!scope) throw new Error('Scope agent failed')
const folder = `${SCRATCH}\\step${scope.step.replace(/\./g, '')}`
log(`Step ${scope.step}: ${scope.title} (${scope.files.length} files)`)

phase('Build')
const build = await agent(`${RULES}

Build Step ${scope.step} (${scope.title}) in the scratch copy ${folder}.
1. Make the copy fresh: delete the folder if it exists, then copy the repository's tracked SourceCode files into it (bash):
   mkdir -p "<folder>" && cd "${SRC}" && git ls-files . | tar -cf - -T - | tar -xf - -C "<folder>"
   Anything untracked the step needs (a downloaded resource, say) goes into the copy only.
2. Implement the step in the copy, following this scope:
${JSON.stringify(scope, null, 2)}
3. Run pytest in the copy and fix the code until it is green. Report the final summary line.`,
  { label: 'build', schema: BUILD })
if (!build) throw new Error('Build agent failed')
log(`Built: ${build.pytest}`)

phase('Verify')
const files = build.changed.join(', ')
const [review, gui] = await parallel([
  () => agent(`${RULES}

Review Step ${scope.step} (${scope.title}). Changed files, relative to SourceCode: ${files}.
For each, compare "${SRC}\\<path>" with "${folder}\\<path>" (diff --strip-trailing-cr; a new file has no repository side).
Read the connected code too, not only the diff. Look for: correctness bugs, callers the change breaks, layer violations,
an admin action without require_admin, blocking work on the UI thread, widgets used after they are destroyed, branchy logic
without a test, and code the step does not need. Do not edit anything. Report only real problems, each with a concrete
failure scenario; an empty list is a fine answer.`,
    { label: 'review', phase: 'Verify', schema: REVIEW }),
  () => agent(`${RULES}

Check Step ${scope.step} (${scope.title}) in the real window. Checkpoint items: ${JSON.stringify(scope.checkpoint)}
Write a driver script in "${SCRATCH}" (not inside the copy) and run it with PYTHONPATH set to "${folder}". What works here:
- Before importing netmonitor.gui.app: point config.DB_PATH at a throwaway file and config.OUTPUT_DIR at a folder in
  "${SCRATCH}", and set config.AUTH_ITERATIONS = 1000. Seed data with store.save_scan / store.save_ping, and set
  services._network_id = lambda info, macs=None: "192.168.1.0/24 via aa" when real network data is not needed.
- app = App(); app.attributes("-topmost", True); drive it with a pump(until, timeout) loop of app.update() and
  time.sleep(0.02). Sign in through app.login: on the first run fill username, password and confirm, then login.submit().
- Tk refuses event_generate("<Double-1>"): send two <ButtonPress-1>/<ButtonRelease-1> pairs at the row's tree.bbox instead.
- Wait for a view's first load to finish before pressing Scan, or the load re-enables the button mid-scan.
- Screenshot with PIL.ImageGrab over the widget's winfo_rootx/rooty box, and look at each screenshot.
- Check both an Admin and a User (services.add_user while the admin is signed in), and finish with app.close().
Report each check as passed or failed with what you saw, the screenshot paths, and what you could not check.`,
    { label: 'gui-check', phase: 'Verify', schema: GUI }),
])
const findings = review ? review.findings : []
const failed = gui ? gui.checks.filter(c => !c.passed) : []
if (!review) log('Review agent failed; the change is unreviewed')
if (!gui) log('GUI agent failed; the window is unchecked')

let fixes = null
if (findings.length || failed.length) {
  phase('Fix')
  log(`${findings.length} review findings, ${failed.length} failed window checks`)
  fixes = await agent(`${RULES}

Fix these problems with Step ${scope.step} in the scratch copy "${folder}" only, then run pytest there until green.
Review findings: ${JSON.stringify(findings, null, 2)}
Failed window checks: ${JSON.stringify(failed, null, 2)}
If a finding is not a real problem, leave the code and say why. Keep every fix as small as the rules ask.`,
    { label: 'fix', schema: FIX })
  if (fixes && fixes.fixed.length) log('Fixes were not re-checked in the window')
}

return {
  step: scope.step, title: scope.title, folder,
  changed: build.changed,
  pytest: fixes ? fixes.pytest : build.pytest,
  checkpoint: scope.checkpoint,
  deviations: [...new Set([...scope.deviations, ...build.deviations])],
  shortcuts: build.shortcuts,
  review: findings, fixes,
  gui: gui || 'GUI check did not run',
}
