const state = {
  running: false,
  runCount: 0,
  lastRun: null,
};

const taskInput = document.querySelector('#task');
const runButton = document.querySelector('#run');
const resetButton = document.querySelector('#reset');
const plannerSelect = document.querySelector('#planner');
const flow = document.querySelector('#flow');
const activity = document.querySelector('#activity');
const report = document.querySelector('#report');
const reportStatus = document.querySelector('#report-status');
const reportTask = document.querySelector('#report-task');
const reportCalls = document.querySelector('#report-calls');
const reportTime = document.querySelector('#report-time');
const output = document.querySelector('#output');
const validationOutput = document.querySelector('#validation-output');

const flowSteps = [
  ['analyze', 'Repository analysis'],
  ['plan', 'Tool planning'],
  ['execute', 'Bounded execution'],
  ['validate', 'Test & recovery'],
  ['review', 'Diff & final report'],
];

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[char]));
}

function renderFlow(active = '', completed = false) {
  flow.innerHTML = flowSteps.map(([key, label], index) => {
    const done = completed || flowSteps.findIndex(([name]) => name === active) > index;
    const current = key === active && !completed;
    const stateClass = done ? 'done' : current ? 'current' : '';
    const icon = done ? '✓' : current ? '•' : String(index + 1).padStart(2, '0');
    return `<div class="flow-step ${stateClass}">
      <span class="flow-icon">${icon}</span><span>${label}</span><span class="flow-state">${done ? 'DONE' : current ? 'RUNNING' : 'WAITING'}</span>
    </div>`;
  }).join('');
}

function addActivity(label, detail, kind = 'info') {
  const item = document.createElement('div');
  item.className = 'activity-item';
  item.innerHTML = `<span class="activity-dot ${kind}"></span><div><strong>${escapeHtml(label)}</strong><small>${escapeHtml(detail)}</small></div>`;
  activity.prepend(item);
  while (activity.children.length > 6) activity.lastElementChild.remove();
}

function setMetric(value, key) {
  const element = document.querySelector(`[data-metric="${key}"]`);
  if (element) element.textContent = value;
}

async function runDemo() {
  if (state.running) return;
  state.running = true;
  runButton.disabled = true;
  runButton.innerHTML = '<span class="spinner"></span> Forge is working';
  report.classList.add('visible');

  const task = taskInput.value.trim() || 'Inspect the repository, run its tests, and report the result.';
  const planner = plannerSelect.value;
  const started = performance.now();
  const stages = [
    ['analyze', 'Repository analyzed', 'Repository inventory and validation entry points discovered'],
    ['plan', 'Execution plan generated', planner === 'offline' ? 'Deterministic bounded planner' : 'Model planner · tool policy enforced'],
    ['execute', 'Tools executed', 'Typed tools · approval-gated mutations'],
    ['validate', 'Validation completed', 'Test execution · bounded recovery path'],
    ['review', 'Run persisted', 'Final report written to .forge/runs'],
  ];

  addActivity('Run started', task, 'running');
  for (const [key, label, detail] of stages) {
    renderFlow(key);
    await new Promise((resolve) => setTimeout(resolve, 330));
    addActivity(label, detail, key === 'validate' ? 'success' : 'info');
  }

  renderFlow('', true);
  const elapsed = Math.max(1, Math.round(performance.now() - started));
  state.runCount += 1;
  state.lastRun = { task, planner, elapsed };

  reportStatus.textContent = 'SUCCEEDED';
  reportStatus.className = 'pill success';
  reportTask.textContent = task;
  reportCalls.textContent = '4 baseline + bounded plan';
  reportTime.textContent = `${elapsed} ms demo trace`;

  const payload = {
    status: 'succeeded',
    planner,
    workflow: ['inspect', 'plan', 'execute', 'validate', 'review'],
    tool_policy: 'typed tools only',
    write_gate: 'approval required',
    workspace_boundary: 'enforced',
    credential_filtering: 'enabled',
    sandbox: 'available for authorized mutation runs',
  };
  output.textContent = JSON.stringify(payload, null, 2);
  validationOutput.textContent = [
    '✓ Workflow completed',
    '✓ Validation stage reached',
    '✓ Approval policy enforced',
    '✓ Workspace boundary enforced',
    '✓ Credentials filtered from child processes',
    '✓ Persistent execution report produced',
  ].join('\n');

  setMetric('READY', 'runtime-status');
  setMetric(String(state.runCount), 'runs');
  setMetric('PASS', 'validation');

  runButton.disabled = false;
  runButton.textContent = 'Run Forge workflow';
  state.running = false;
}

function resetDemo() {
  if (state.running) return;
  taskInput.value = 'Inspect the repository, run its tests, and report the result.';
  plannerSelect.value = 'offline';
  report.classList.remove('visible');
  reportStatus.textContent = 'READY';
  reportStatus.className = 'pill';
  reportTask.textContent = '—';
  reportCalls.textContent = '—';
  reportTime.textContent = '—';
  output.textContent = 'No run yet.';
  validationOutput.textContent = 'No validation evidence yet.';
  activity.innerHTML = '<div class="activity-empty">Run Forge to see the execution trace.</div>';
  renderFlow();
}

runButton.addEventListener('click', runDemo);
resetButton.addEventListener('click', resetDemo);
renderFlow();
