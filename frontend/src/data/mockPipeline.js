export const PIPELINE_STEPS = [
  {
    id: 'clone_repo',
    name: 'Cloning Repository',
    description: 'Fetching target repository and setting up the isolated workspace environment.',
    logs: [
      'Initializing git clone for repository {REPO}...',
      'Cloning into \'/tmp/4o4pr-workspace\'...',
      'remote: Enumerating objects: 247, done.',
      'remote: Counting objects: 100% (247/247), done.',
      'remote: Compressing objects: 100% (132/132), done.',
      'remote: Total 247 (delta 112), reused 218 (delta 85), pack-reused 0',
      'Receiving objects: 100% (247/247), 184.20 KiB | 2.45 MiB/s, done.',
      'Resolving deltas: 100% (112/112), done.',
      'Checking out files: 100% (89/89), done.',
      'Repository cloned successfully.'
    ]
  },
  {
    id: 'detect_bug',
    name: 'Detecting & Reproducing Bug',
    description: 'Analyzing code structure, extracting issue description, and executing reproduction tests.',
    logs: [
      'Locating issue details: {BUG}...',
      'Searching codebase for matching components...',
      'Found failing context in tests/test_core.py.',
      'Setting up python virtualenv...',
      'Installing dependencies from pyproject.toml...',
      'Running command: pytest tests/test_core.py',
      '============================= test session starts =============================',
      'platform win32 -- Python 3.10.8, pytest-7.2.1, pluggy-1.0.0',
      'rootdir: F:\\4o4PR\\workspace',
      'collected 3 items',
      '',
      'tests/test_core.py ..F                                                   [100%]',
      '',
      '================================== FAILURES ===================================',
      '___________________________ test_unauthenticated_access ___________________________',
      '',
      '    def test_unauthenticated_access():',
      '        client = Client()',
      '>       response = client.get("/api/v1/resource")',
      'E       AssertionError: assert 200 == 401',
      'E        +  where 200 = <Response [200 OK]>.status_code',
      '',
      'tests/test_core.py:45: AssertionError',
      '=========================== 1 failed, 2 passed in 0.65s ===========================',
      'Bug successfully reproduced. Status: CONFIRMED.'
    ]
  },
  {
    id: 'generate_patch',
    name: 'Generating AI Repair Patch',
    description: 'Invoking Gemini models to analyze code failure and generate logical bug-fix patches.',
    logs: [
      'Sending prompt payload to Gemini LLM engine (gemini-2.5-pro)...',
      'Analyzing repository graph and AST for src/core/router.py...',
      'Reasoning about failure: Endpoint "/api/v1/resource" missing auth decorator.',
      'Identified error: Route handler lacks `@login_required` metadata check.',
      'Generating candidate patch #1...',
      'Applying candidate patch to memory layout...',
      'Patch generated successfully.',
      'Proposed diff:',
      '--------------------------------------------------',
      '@@ -24,4 +24,5 @@',
      ' @router.get("/api/v1/resource")',
      '+@login_required',
      ' def get_resource():',
      '     return {"status": "success", "data": "protected"}',
      '--------------------------------------------------'
    ]
  },
  {
    id: 'run_tests',
    name: 'Running Test Suite',
    description: 'Validating the patch against the repository test suite within a Docker sandbox.',
    logs: [
      'Spawning docker container (python:3.10-alpine)...',
      'Applying patch to src/core/router.py...',
      'Running command: pytest tests/',
      '============================= test session starts =============================',
      'platform linux -- Python 3.10.8, pytest-7.2.1, pluggy-1.0.0',
      'rootdir: /app',
      'collected 3 items',
      '',
      'tests/test_core.py ...                                                   [100%]',
      '',
      '============================= 3 passed in 1.42s =============================',
      'Test execution completed. All 3 tests PASSED.',
      'Patch validation status: SUCCESS.'
    ]
  },
  {
    id: 'create_pr',
    name: 'Creating Pull Request',
    description: 'Staging changes, committing files, pushing to GitHub, and opening a Pull Request.',
    logs: [
      'Staging files: git add src/core/router.py',
      'Committing patch: git commit -m "fix(core): restrict resource access to authenticated users"',
      'Pushing branch to GitHub: git push origin fix/core-resource-auth',
      'Target: {REPO}',
      'Opening Pull Request via GitHub API...',
      'Pull Request #73 created: "Fix authentication leak on resource route"',
      'GitHub PR URL: https://github.com/{REPO}/pull/73',
      'Pull Request creation successful.'
    ]
  },
  {
    id: 'complete',
    name: 'Pipeline Completed',
    description: 'Bug fixing pipeline has completed successfully. The PR is ready for review.',
    logs: [
      '========================================================================',
      '                    4O4PR AUTO-REPAIR COMPLETED SUCCESSFULLY',
      '========================================================================',
      'Total duration: 14.5 seconds.',
      'Patch: APPLIED & COMMITTED.',
      'PR Status: OPEN.',
      'Pull Request: https://github.com/{REPO}/pull/73',
      'Ready for human review and merge!'
    ]
  }
];

export const MOCK_REPOSITORIES = [
  'AnshPandey18/4o4PR',
  'django/django',
  'pallets/flask',
  'psf/requests',
  'encode/httpx',
  'fastapi/fastapi'
];

export const MOCK_REPO_STATS = {
  'AnshPandey18/4o4PR': {
    healthIndex: '98%',
    coverage: '94.2%',
    activeTests: '38',
    prSuccessRate: '92%',
    avgRepairTime: '15 seconds',
    activeBranch: 'main',
    status: 'Healthy'
  },
  'django/django': {
    healthIndex: '84%',
    coverage: '79.8%',
    activeTests: '1,420',
    prSuccessRate: '78%',
    avgRepairTime: '29 seconds',
    activeBranch: 'main',
    status: 'Warning'
  },
  'pallets/flask': {
    healthIndex: '93%',
    coverage: '88.5%',
    activeTests: '246',
    prSuccessRate: '87%',
    avgRepairTime: '18 seconds',
    activeBranch: 'main',
    status: 'Healthy'
  },
  'psf/requests': {
    healthIndex: '95%',
    coverage: '91.0%',
    activeTests: '182',
    prSuccessRate: '90%',
    avgRepairTime: '16 seconds',
    activeBranch: 'main',
    status: 'Healthy'
  },
  'encode/httpx': {
    healthIndex: '90%',
    coverage: '86.4%',
    activeTests: '312',
    prSuccessRate: '84%',
    avgRepairTime: '20 seconds',
    activeBranch: 'master',
    status: 'Healthy'
  },
  'fastapi/fastapi': {
    healthIndex: '96%',
    coverage: '92.7%',
    activeTests: '450',
    prSuccessRate: '94%',
    avgRepairTime: '14 seconds',
    activeBranch: 'master',
    status: 'Healthy'
  }
};

export const MOCK_BUGS = [
  { 
    id: 'bug-1', 
    title: 'Issue #404: pytest failure in auth module (test_jwt_validation)',
    severity: 'High',
    complexity: 'Moderate',
    eta: '15s',
    impact: 'Enforces JWT expiration check in login routes'
  },
  { 
    id: 'bug-2', 
    title: 'Issue #201: connection timeout in HTTP pool management',
    severity: 'Medium',
    complexity: 'Easy',
    eta: '10s',
    impact: 'Resolves connection leakage during concurrency peak'
  },
  { 
    id: 'bug-3', 
    title: 'Issue #89: memory leak in WebSocket connection pool',
    severity: 'High',
    complexity: 'Complex',
    eta: '25s',
    impact: 'Garbage collects unclosed sockets after keep-alive times out'
  },
  { 
    id: 'bug-4', 
    title: 'Issue #112: CORS header mismatch on endpoints',
    severity: 'Low',
    complexity: 'Easy',
    eta: '8s',
    impact: 'Allows subdomains access to static assets'
  },
  { 
    id: 'bug-5', 
    title: 'Issue #303: Database connection leak during async tests',
    severity: 'Medium',
    complexity: 'Moderate',
    eta: '18s',
    impact: 'Properly closes transaction loops on fixture teardown'
  }
];
