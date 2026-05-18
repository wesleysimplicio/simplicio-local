#!/usr/bin/env node
/**
 * LLM Project Mapper - CLI scaffolder.
 *
 * Run inside any project to install the starter pack:
 *   npx @wesleysimplicio/llm-project-mapper
 *
 * Behavior (mirror of bootstrap.sh / bootstrap.ps1):
 *   1. Auto-detects PRODUCT_NAME from manifests, STACK, and whether the repo
 *      follows the projects/ monorepo convention.
 *   2. Asks only two operational questions:
 *        - Append recommended ignore entries to .gitignore? (y/N)
 *        - Which CLI/LLM should run INIT.md?
 *      It never asks about team, domain, vision, personas, or product purpose.
 *   3. Substitutes <PRODUCT_NAME>/<STACK> only inside starter-managed paths.
 *   4. Never overwrites pre-existing user instruction files.
 *   5. Hands off to the chosen CLI to execute INIT.md.
 *
 * Pure Node.js. No bash dependency. Works on macOS, Linux, and Windows.
 */

'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const readline = require('node:readline');
const { spawn, spawnSync } = require('node:child_process');

const PACKAGE_ROOT = path.resolve(__dirname, '..');
const CWD = process.cwd();
const PKG = require(path.join(PACKAGE_ROOT, 'package.json'));

const TEMPLATE_PATHS = [
  'AGENTS.md',
  'CLAUDE.md',
  'INIT.md',
  '_BOOTSTRAP.md',
  '.agents',
  '.claude',
  '.codex',
  '.github',
  '.skills',
  '.specs',
  'bootstrap.sh',
  'bootstrap.ps1',
  'playwright.config.ts',
  'tests',
];

const PROTECTED_INSTRUCTION_FILES = [
  'AGENTS.md',
  'CLAUDE.md',
  'INIT.md',
  '.github/copilot-instructions.md',
];

const STARTER_DIRS = ['.specs', '.agents', '.skills', '.claude', '.codex'];
const STARTER_GITHUB_PATTERNS = [
  '.github/copilot-instructions.md',
  '.github/copilot',
  '.github/PULL_REQUEST_TEMPLATE.md',
  '.github/ISSUE_TEMPLATE',
  '.github/workflows/ci.yml',
  '.github/workflows/dod.yml',
];
const STARTER_ROOT_FILES = [
  'AGENTS.md', 'CLAUDE.md', 'INIT.md', '_BOOTSTRAP.md',
  'README.md', 'README.pt-BR.md',
  'playwright.config.ts',
];

const TEXT_EXTS = new Set(['.md', '.json', '.toml', '.yml', '.yaml', '.ts']);
const WALK_SKIP_DIRS = new Set([
  'node_modules', '.git', 'dist', 'build', 'out',
  '.next', '.nuxt', 'coverage', 'playwright-report', 'test-results',
]);

const RECOMMENDED_IGNORES = `# === Agentic Starter (auto-managed) - do not remove this header ===
# Local agent state and ephemeral artifacts created by the starter.
.starter-meta.json
.codex/local
.codex/history
.claude/sessions
.claude/cache

# Test artifacts (Playwright + coverage)
test-results/
playwright-report/
playwright/.cache/
coverage/
.nyc_output/

# Env vars
.env
.env.*
!.env.example

# Editor / OS
.DS_Store
Thumbs.db
*.swp
*.swo

# Build / dist (most common)
node_modules/
dist/
build/
out/
.next/
.nuxt/
.turbo/
.vercel/
*.tsbuildinfo

# Logs
*.log
npm-debug.log*
yarn-debug.log*
pnpm-debug.log*

# Tarballs
*.tgz
*.tar.gz
`;

const GITATTRIBUTES_CONTENT = `# Cross-platform line endings.
* text=auto eol=lf

# Shell scripts MUST be LF.
*.sh        text eol=lf
*.bash      text eol=lf

# Windows scripts MUST be CRLF.
*.ps1       text eol=crlf
*.psm1      text eol=crlf
*.psd1      text eol=crlf
*.bat       text eol=crlf
*.cmd       text eol=crlf

# Common config / source.
*.md        text
*.json      text
*.jsonc     text
*.yml       text
*.yaml      text
*.toml      text
*.xml       text
*.html      text
*.css       text
*.scss      text
*.js        text
*.jsx       text
*.ts        text
*.tsx       text
*.mjs       text
*.cjs       text
*.py        text
*.cs        text
*.csproj    text
*.sln       text eol=crlf
*.go        text
*.rs        text
*.java      text
*.kt        text
*.kts       text
*.gradle    text

# Binaries: never normalize.
*.png       binary
*.jpg       binary
*.jpeg      binary
*.gif       binary
*.ico       binary
*.pdf       binary
*.zip       binary
*.gz        binary
*.tar       binary
*.7z        binary
*.exe       binary
*.dll       binary
*.so        binary
*.dylib     binary
*.woff      binary
*.woff2     binary
*.ttf       binary
*.eot       binary
*.mp3       binary
*.mp4       binary
*.mov       binary

# Lockfiles: text but no noisy diff.
package-lock.json    text -diff
pnpm-lock.yaml       text -diff
yarn.lock            text -diff
poetry.lock          text -diff
Cargo.lock           text -diff
`;

const CLI_OPTS = [
  { key: 'claude', label: 'Claude Code', cmd: 'claude' },
  { key: 'codex', label: 'Codex CLI', cmd: 'codex' },
  { key: 'cursor', label: 'Cursor Agent (cursor-agent)', cmd: 'cursor-agent' },
  { key: 'vscode', label: 'VS Code Agent Mode (paste into Chat)', cmd: 'code' },
  { key: 'windsurf', label: 'Windsurf / Cascade (Codeium)', cmd: 'windsurf' },
  { key: 'kiro', label: 'Kiro (AWS, paste into Chat)', cmd: 'kiro' },
  { key: 'copilot', label: 'GitHub Copilot CLI (chat - no agent loop)', cmd: 'gh' },
  { key: 'deepseek', label: 'Deepseek (via aider --model deepseek/deepseek-coder)', cmd: 'aider' },
  { key: 'kimi', label: 'Kimi K2.6 (via aider --model openrouter/moonshotai/kimi-k2)', cmd: 'aider' },
  { key: 'minimax', label: 'MiniMax M2.7 (via aider --model openrouter/minimax/minimax-text-01)', cmd: 'aider' },
  { key: 'glm', label: 'GLM 5.1 (via aider --model openrouter/z-ai/glm-4.5)', cmd: 'aider' },
  { key: 'hermes', label: 'Hermes Agent (Nous Research)', cmd: 'hermes' },
  { key: 'openclaw', label: 'OpenClaw', cmd: 'openclaw' },
  { key: 'aider', label: 'Aider (pick model interactively)', cmd: 'aider' },
  { key: 'other', label: 'Other / manual (copy prompt to clipboard)', cmd: '' },
  { key: 'skip', label: 'Skip - I will run INIT.md later', cmd: '' },
];

const INIT_PROMPT = 'Read INIT.md and execute it. Do NOT modify any user source files (.razor, .cs, .ts, .py, .go, .rs, package.json, etc). Only write inside .specs/, .agents/, .skills/, .claude/, .codex/, .github/copilot*, .github/workflows/dod.yml plus root AGENTS.md/CLAUDE.md/INIT.md/README*.md. If AGENTS.md/CLAUDE.md/copilot-instructions.md already existed before bootstrap (see .starter-meta.json), READ them and IMPROVE in place - preserve their essence. DO NOT ask the human about team, domain, vision, personas, or product purpose: infer ALL of them by reading the codebase (README, package.json/angular.json/*.csproj/pyproject.toml/etc, entry points, routes, tests, env.example). Default persona is "developer"; additional personas must be derived from code (auth roles, route guards, UI flows, customer-facing copy). Honor projects/ convention: if .starter-meta.json.project_mode == "monorepo", iterate over .starter-meta.json.projects[] and produce per-project .specs/. Use parallel multi-agents.';

const argv = process.argv.slice(2);
const opts = {
  yes: false,
  force: false,
  dryRun: false,
  silent: false,
  skipMeta: false,
  cli: '',
  appendGitignore: '',
  json: false,
  probe: false,
  mode: '',
  showHelp: false,
  showVersion: false,
};

for (let i = 0; i < argv.length; i++) {
  const arg = argv[i];
  switch (arg) {
    case '-y':
    case '--yes':
      opts.yes = true;
      break;
    case '-f':
    case '--force':
      opts.force = true;
      break;
    case '--dry-run':
      opts.dryRun = true;
      break;
    case '--silent':
      opts.silent = true;
      break;
    case '--skip-meta':
      opts.skipMeta = true;
      break;
    case '--cli':
      opts.cli = argv[++i];
      break;
    case '--append-gitignore':
      opts.appendGitignore = argv[++i];
      break;
    case '--json':
      opts.json = true;
      break;
    case '--probe':
      opts.probe = true;
      break;
    case '--mode':
      opts.mode = argv[++i];
      if (!opts.mode) {
        console.error('Missing value for --mode.');
        process.exit(2);
      }
      break;
    case '-v':
    case '--version':
      opts.showVersion = true;
      break;
    case '-h':
    case '--help':
      opts.showHelp = true;
      break;
    default:
      console.error(`Unknown flag: ${arg}`);
      console.error('Run with --help for usage.');
      process.exit(2);
  }
}

const kRuntimeModes = [
  'FULL',
  'BALANCED_PLUS',
  'DEGRADED',
  'ULTRA_LOW',
  'MICRO',
  'MICRO_PLUS',
  'NANO',
];

function normalizeMemoryGiB(totalBytes) {
  return Math.round(totalBytes / (1024 ** 3));
}

function selectRuntimeMode(totalMemoryGiB) {
  if (totalMemoryGiB >= 128) return 'FULL';
  if (totalMemoryGiB >= 96) return 'BALANCED_PLUS';
  if (totalMemoryGiB >= 64) return 'DEGRADED';
  if (totalMemoryGiB >= 48) return 'ULTRA_LOW';
  if (totalMemoryGiB >= 32) return 'MICRO';
  if (totalMemoryGiB >= 24) return 'MICRO_PLUS';
  return 'NANO';
}

function detectAneEligibility(cpuModel, platform) {
  if (platform !== 'darwin') return false;
  return /\bM5\b/i.test(cpuModel);
}

function buildProbe(modeArg) {
  const cpuInfo = os.cpus();
  const cpuModel = cpuInfo[0] ? cpuInfo[0].model : 'unknown';
  const totalMemoryBytes = os.totalmem();
  const totalMemoryGiB = normalizeMemoryGiB(totalMemoryBytes);
  const selectedMode = modeArg === 'auto' || !modeArg
    ? selectRuntimeMode(totalMemoryGiB)
    : modeArg.toUpperCase();
  const platform = process.platform;
  const arch = process.arch;
  const appleSilicon = platform === 'darwin' && arch === 'arm64';
  const probe = {
    cli: 'us4-cli',
    version: PKG.version,
    probe: {
      platform,
      arch,
      cpuModel,
      logicalCores: cpuInfo.length,
      totalMemoryBytes,
      totalMemoryGiB,
      appleSilicon,
      aneEligible: detectAneEligibility(cpuModel, platform),
    },
    mode: {
      requested: modeArg || 'auto',
      selected: selectedMode,
      taxonomy: kRuntimeModes,
      source: 'memory-tier',
    },
  };

  return probe;
}

function printRuntimeText(probe, includeProbeDetails) {
  const lines = [
    `us4-cli ${probe.version}`,
    `mode: ${probe.mode.selected} (${probe.mode.source})`,
  ];

  if (includeProbeDetails) {
    lines.push(`platform: ${probe.probe.platform}/${probe.probe.arch}`);
    lines.push(`cpu: ${probe.probe.cpuModel}`);
    lines.push(`logical cores: ${probe.probe.logicalCores}`);
    lines.push(`memory: ${probe.probe.totalMemoryGiB} GiB`);
    lines.push(`apple silicon: ${probe.probe.appleSilicon ? 'yes' : 'no'}`);
    lines.push(`ane eligible: ${probe.probe.aneEligible ? 'yes' : 'no'}`);
  }

  console.log(lines.join('\n'));
}

function handleRuntimeFlags() {
  if (opts.mode && opts.mode !== 'auto') {
    console.error(`Unsupported mode selector: ${opts.mode}. Only --mode auto is available in Sprint 01.`);
    process.exit(2);
  }

  if (opts.showVersion && !opts.probe && !opts.mode) {
    if (opts.json) {
      console.log(JSON.stringify({ cli: 'us4-cli', version: PKG.version }, null, 2));
      return true;
    }
    console.log(PKG.version);
    return true;
  }

  if (!opts.probe && !opts.mode) {
    if (opts.json) {
      console.error('--json requires --version, --probe, or --mode auto.');
      process.exit(2);
    }
    return false;
  }

  const probe = buildProbe(opts.mode || 'auto');
  if (opts.json) {
    console.log(JSON.stringify(probe, null, 2));
  } else {
    printRuntimeText(probe, opts.probe);
  }
  return true;
}

function printHelp() {
  console.log(`llm-project-mapper v${PKG.version}

Scaffold the Agentic Starter pack into the current directory.

USAGE
  npx @wesleysimplicio/llm-project-mapper [options]

OPTIONS
  --probe                     Print Sprint 01 hardware probe summary
  --mode auto                 Select runtime mode from the current memory tier
  --json                      Emit JSON for --version, --probe, or --mode auto
  -y, --yes                   Non-interactive (defaults: no gitignore append, skip CLI handoff)
  -f, --force                 Overwrite starter template files (NEVER touches user
                              instruction files: AGENTS.md, CLAUDE.md, INIT.md,
                              .github/copilot-instructions.md, .gitignore)
  --dry-run                   Print actions without writing files
  --skip-meta                 Do not write .starter-meta.json
  --cli <key>                 Pick CLI for INIT.md handoff (claude|codex|cursor|vscode|
                              windsurf|kiro|copilot|deepseek|kimi|minimax|glm|
                              hermes|openclaw|aider|other|skip)
  --append-gitignore <yes|no> Append recommended ignores to .gitignore (or create it)
  --silent                    Minimal output
  -v, --version               Print version
  -h, --help                  Show this help

EXAMPLES
  node bin/cli.js --version --json
  node bin/cli.js --probe
  node bin/cli.js --probe --mode auto --json
  npx @wesleysimplicio/llm-project-mapper
  npx @wesleysimplicio/llm-project-mapper --yes
  npx @wesleysimplicio/llm-project-mapper --yes --cli claude --append-gitignore yes

DOCS
  https://github.com/wesleysimplicio/llm-project-mapper
`);
}

if (opts.showHelp) {
  printHelp();
  process.exit(0);
}

if (handleRuntimeFlags()) {
  process.exit(0);
}

const log = (...args) => { if (!opts.silent) console.log(...args); };
const err = (...args) => console.error(...args);

function readSafe(file) {
  try {
    return fs.readFileSync(file, 'utf8');
  } catch {
    return '';
  }
}

function existsIn(baseDir, rel) {
  return fs.existsSync(path.join(baseDir, rel));
}

function listDir(baseDir) {
  try {
    return fs.readdirSync(baseDir);
  } catch {
    return [];
  }
}

function commandExists(cmd) {
  if (!cmd) return false;
  const which = process.platform === 'win32' ? 'where' : 'which';
  const result = spawnSync(which, [cmd], { stdio: 'ignore' });
  return result.status === 0;
}

function readJsonField(file, field) {
  const content = readSafe(file);
  const match = content.match(new RegExp(`"${field}"\\s*:\\s*"([^"]+)"`));
  return match ? match[1] : '';
}

function readTomlField(file, field) {
  const content = readSafe(file);
  const match = content.match(new RegExp(`^\\s*${field}\\s*=\\s*"([^"]+)"`, 'm'));
  return match ? match[1] : '';
}

function readYamlField(file, field) {
  const content = readSafe(file);
  const match = content.match(new RegExp(`^\\s*${field}\\s*:\\s*"?([^"\\s#]+)"?`, 'm'));
  return match ? match[1] : '';
}

function detectStack(baseDir = CWD) {
  const files = listDir(baseDir);
  if (existsIn(baseDir, 'angular.json')) return 'angular';
  if (existsIn(baseDir, 'package.json')) {
    const pkg = readSafe(path.join(baseDir, 'package.json'));
    if (/"next"\s*:/.test(pkg)) return 'next-ts';
    if (/"@angular\/core"\s*:/.test(pkg)) return 'angular';
    if (/"react"\s*:/.test(pkg)) return 'react-ts';
    if (/"vue"\s*:/.test(pkg)) return 'vue-ts';
    if (/"@nestjs\/core"|"nestjs"\s*:/.test(pkg)) return 'nestjs';
    if (/"express"\s*:/.test(pkg)) return 'node-express';
    return 'node-ts';
  }
  if (files.some((file) => file.endsWith('.csproj') || file.endsWith('.sln'))) return 'dotnet';
  if (existsIn(baseDir, 'pyproject.toml') || existsIn(baseDir, 'requirements.txt')) {
    const py = readSafe(path.join(baseDir, 'pyproject.toml')) + readSafe(path.join(baseDir, 'requirements.txt'));
    if (/django/i.test(py)) return 'python-django';
    if (/fastapi/i.test(py)) return 'python-fastapi';
    if (/flask/i.test(py)) return 'python-flask';
    return 'python';
  }
  if (existsIn(baseDir, 'go.mod')) return 'go';
  if (existsIn(baseDir, 'Cargo.toml')) return 'rust';
  if (existsIn(baseDir, 'pubspec.yaml')) return 'flutter';
  if (existsIn(baseDir, 'composer.json')) {
    return /laravel\/framework/.test(readSafe(path.join(baseDir, 'composer.json'))) ? 'laravel' : 'php';
  }
  if (existsIn(baseDir, 'Gemfile')) return 'ruby';
  if (existsIn(baseDir, 'mix.exs')) return 'elixir';
  if (existsIn(baseDir, 'build.gradle.kts')) return 'kotlin-gradle';
  if (existsIn(baseDir, 'build.gradle')) return 'java-gradle';
  if (existsIn(baseDir, 'pom.xml')) return 'java-maven';
  return 'unknown';
}

function detectProductName(baseDir = CWD) {
  const files = listDir(baseDir);

  const packageName = readJsonField(path.join(baseDir, 'package.json'), 'name');
  if (packageName) return packageName;

  const angular = readSafe(path.join(baseDir, 'angular.json'));
  if (angular) {
    const match = angular.match(/"projects"\s*:\s*\{\s*"([A-Za-z0-9_-]+)"/);
    if (match) return match[1];
  }

  const csproj = files.find((file) => file.endsWith('.csproj'));
  if (csproj) return path.basename(csproj, '.csproj');

  const pyName = readTomlField(path.join(baseDir, 'pyproject.toml'), 'name');
  if (pyName) return pyName;

  const cargoName = readTomlField(path.join(baseDir, 'Cargo.toml'), 'name');
  if (cargoName) return cargoName;

  const pubspecName = readYamlField(path.join(baseDir, 'pubspec.yaml'), 'name');
  if (pubspecName) return pubspecName;

  const composerName = readJsonField(path.join(baseDir, 'composer.json'), 'name');
  if (composerName) return composerName.split('/').pop();

  const goMod = readSafe(path.join(baseDir, 'go.mod'));
  const goMatch = goMod.match(/^module\s+(.+)$/m);
  if (goMatch) return goMatch[1].trim().split('/').pop();

  return path.basename(baseDir);
}

function detectProjectMode() {
  const projectsDir = path.join(CWD, 'projects');
  if (!fs.existsSync(projectsDir) || !fs.statSync(projectsDir).isDirectory()) return 'root';
  const projects = fs.readdirSync(projectsDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && !entry.name.startsWith('.'));
  return projects.length > 0 ? 'monorepo' : 'root';
}

function detectProjects() {
  const projectsDir = path.join(CWD, 'projects');
  if (!fs.existsSync(projectsDir) || !fs.statSync(projectsDir).isDirectory()) return [];
  return fs.readdirSync(projectsDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && !entry.name.startsWith('.'))
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((entry) => {
      const fullPath = path.join(projectsDir, entry.name);
      return {
        name: detectProductName(fullPath),
        path: path.join('projects', entry.name).replace(/\\/g, '/'),
        stack: detectStack(fullPath),
      };
    });
}

function detectExistingInstructionFiles() {
  const found = [];
  for (const rel of PROTECTED_INSTRUCTION_FILES) {
    const abs = path.join(CWD, rel);
    if (!fs.existsSync(abs)) continue;
    const content = readSafe(abs);
    if (/Agentic Starter|<PRODUCT_NAME>|<STACK>/.test(content)) continue;
    found.push(rel);
  }
  return found;
}

function copyTemplate(existingProtected) {
  const protectedSet = new Set(existingProtected);
  let copied = 0;
  let skipped = 0;
  let missing = 0;

  for (const rel of TEMPLATE_PATHS) {
    const src = path.join(PACKAGE_ROOT, rel);
    const dest = path.join(CWD, rel);

    if (!fs.existsSync(src)) {
      missing++;
      continue;
    }

    if (protectedSet.has(rel)) {
      log(`  preserve (user): ${rel}`);
      skipped++;
      continue;
    }

    if (fs.existsSync(dest) && !opts.force) {
      log(`  skip  (exists): ${rel}`);
      skipped++;
      continue;
    }

    if (opts.dryRun) {
      log(`  copy  (dry):    ${rel}`);
      copied++;
      continue;
    }

    try {
      fs.cpSync(src, dest, { recursive: true, force: true });
      log(`  copy:           ${rel}`);
      copied++;
    } catch (error) {
      err(`  fail  ${rel}: ${error.message}`);
    }
  }

  log(`\n-> ${copied} copied, ${skipped} skipped${opts.force ? '' : ' (use --force to overwrite starter files)'}, ${missing} missing in package.\n`);
}

async function handleGitignore(rl) {
  let choice = opts.appendGitignore;
  if (!choice && !opts.yes) {
    log('==========================================');
    log('  .gitignore');
    log('==========================================');
    if (existsIn(CWD, '.gitignore')) {
      log('An existing .gitignore was found.');
      log('I can APPEND recommended entries (your existing content is NEVER modified).');
    } else {
      log('No .gitignore found. I can CREATE one with recommended entries.');
    }
    const response = await ask(rl, 'Proceed?', 'n');
    choice = /^[ys]/i.test(response) ? 'yes' : 'no';
    log('');
  }
  choice = choice || 'no';

  if (choice !== 'yes') {
    log('-> .gitignore left untouched.\n');
    return;
  }

  const gitignore = path.join(CWD, '.gitignore');
  if (fs.existsSync(gitignore)) {
    const existing = readSafe(gitignore);
    if (existing.includes('Agentic Starter (auto-managed)')) {
      log('-> Recommended entries already present in .gitignore. Nothing to do.\n');
    } else if (opts.dryRun) {
      log('  append (dry):   .gitignore\n');
    } else {
      fs.appendFileSync(gitignore, '\n' + RECOMMENDED_IGNORES);
      log('-> Recommended entries APPENDED to .gitignore (original content preserved).\n');
    }
  } else if (opts.dryRun) {
    log('  create (dry):   .gitignore\n');
  } else {
    fs.writeFileSync(gitignore, RECOMMENDED_IGNORES);
    log('-> .gitignore CREATED.\n');
  }

  const gitattributes = path.join(CWD, '.gitattributes');
  if (!fs.existsSync(gitattributes)) {
    if (opts.dryRun) {
      log('  create (dry):   .gitattributes');
    } else {
      fs.writeFileSync(gitattributes, GITATTRIBUTES_CONTENT);
      log('-> .gitattributes CREATED.');
    }
  } else {
    log('-> .gitattributes left untouched (already exists).');
  }
  log('');
}

function looksBinary(buffer) {
  const head = buffer.length > 8192 ? buffer.subarray(0, 8192) : buffer;
  return head.includes(0);
}

function substituteInFile(file, productName, stack) {
  let content;
  try {
    const buffer = fs.readFileSync(file);
    if (buffer.length === 0 || looksBinary(buffer)) return false;
    content = buffer.toString('utf8');
  } catch {
    return false;
  }

  if (!/<PRODUCT_NAME>|<STACK>/.test(content)) return false;
  const next = content
    .replace(/<PRODUCT_NAME>/g, productName)
    .replace(/<STACK>/g, stack);

  if (next === content) return false;
  if (!opts.dryRun) fs.writeFileSync(file, next);
  return true;
}

function walk(dir, callback) {
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }

  for (const entry of entries) {
    if (WALK_SKIP_DIRS.has(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, callback);
    else if (entry.isFile()) callback(full);
  }
}

function substitute(productName, stack) {
  let touched = 0;
  const stamp = (file) => {
    if (substituteInFile(file, productName, stack)) touched++;
  };

  for (const dir of STARTER_DIRS) {
    const abs = path.join(CWD, dir);
    if (!fs.existsSync(abs)) continue;
    walk(abs, (file) => {
      if (TEXT_EXTS.has(path.extname(file))) stamp(file);
    });
  }

  for (const rel of STARTER_GITHUB_PATTERNS) {
    const abs = path.join(CWD, rel);
    if (!fs.existsSync(abs)) continue;
    const stat = fs.statSync(abs);
    if (stat.isDirectory()) walk(abs, stamp);
    else if (stat.isFile()) stamp(abs);
  }

  for (const rel of STARTER_ROOT_FILES) {
    const abs = path.join(CWD, rel);
    if (fs.existsSync(abs)) stamp(abs);
  }

  log(`-> ${touched} files updated (only starter-managed paths)${opts.dryRun ? ' (dry-run)' : ''}.\n`);
}

function writeMeta(productName, stack, projectMode, projects, existingInstructionFiles) {
  if (opts.skipMeta) return;
  const meta = {
    product_name: productName,
    stack,
    project_mode: projectMode,
    projects,
    bootstrapped_at: new Date().toISOString(),
    starter_version: PKG.version,
    cli: '@wesleysimplicio/llm-project-mapper',
    existing_instruction_files: existingInstructionFiles,
    init_must_ask: [],
    init_must_infer: ['team', 'domain', 'vision_oneliner', 'personas_beyond_dev'],
    default_persona: 'developer',
    init_must_merge: existingInstructionFiles,
    read_only_globs: [
      '**/*.razor', '**/*.cs', '**/*.csproj', '**/*.sln',
      'package.json', 'pnpm-lock.yaml', 'yarn.lock', 'package-lock.json',
      '**/*.py', '**/*.go', '**/*.rs', '**/*.java', '**/*.kt', '**/*.dart',
      '**/*.php', '**/*.rb',
    ],
  };
  const dest = path.join(CWD, '.starter-meta.json');
  if (opts.dryRun) {
    log('  write (dry):    .starter-meta.json');
    return;
  }
  fs.writeFileSync(dest, JSON.stringify(meta, null, 2) + '\n');
  log('-> .starter-meta.json saved.');
}

function ask(rl, question, defaultValue) {
  return new Promise((resolve) => {
    rl.question(`${question} [${defaultValue}]: `, (answer) => resolve((answer || '').trim() || defaultValue));
  });
}

async function chooseCli(rl) {
  if (opts.cli) return opts.cli;
  if (opts.yes) return 'skip';

  log('==========================================');
  log('  Choose the CLI/LLM to run INIT.md');
  log('==========================================\n');
  CLI_OPTS.forEach((option, index) => {
    const mark = commandExists(option.cmd) ? '  [installed]' : '';
    log(`  [${String(index + 1).padStart(2, ' ')}] ${option.label}${mark}`);
  });
  log('');
  const response = await ask(rl, 'Number', String(CLI_OPTS.length));
  let index = parseInt(response, 10);
  if (!Number.isFinite(index) || index < 1 || index > CLI_OPTS.length) index = CLI_OPTS.length;
  return CLI_OPTS[index - 1].key;
}

function copyToClipboard(text) {
  const candidates = process.platform === 'darwin'
    ? [['pbcopy', []]]
    : process.platform === 'win32'
      ? [['clip', []]]
      : [['xclip', ['-selection', 'clipboard']], ['wl-copy', []]];
  for (const [cmd, args] of candidates) {
    try {
      const result = spawnSync(cmd, args, { input: text, stdio: ['pipe', 'ignore', 'ignore'] });
      if (result.status === 0) return true;
    } catch {
      // Try the next clipboard command.
    }
  }
  return false;
}

function execHandoff(cmd, args) {
  const child = spawn(cmd, args, { stdio: 'inherit' });
  child.on('exit', (code) => process.exit(code ?? 0));
  child.on('error', (error) => {
    err(`Failed to launch ${cmd}: ${error.message}`);
    process.exit(1);
  });
}

function requireCmd(cmd, hint) {
  if (!commandExists(cmd)) {
    err(`${cmd} not installed: ${hint}`);
    process.exit(1);
  }
}

function handoff(cliChoice) {
  log('');
  log('==========================================');
  log(`  Handing off to: ${cliChoice}`);
  log('==========================================\n');

  switch (cliChoice) {
    case 'claude':
      requireCmd('claude', 'https://docs.claude.com/claude-code');
      return execHandoff('claude', [INIT_PROMPT]);
    case 'codex':
      requireCmd('codex', 'https://github.com/openai/codex');
      return execHandoff('codex', ['exec', INIT_PROMPT]);
    case 'cursor':
      requireCmd('cursor-agent', 'Cursor 3.0+ required');
      return execHandoff('cursor-agent', [INIT_PROMPT]);
    case 'vscode':
      if (copyToClipboard(INIT_PROMPT)) log('Prompt copied to clipboard.');
      else log('(clipboard unavailable - copy manually below)');
      log('');
      log('VS Code Agent Mode runs in-IDE.');
      log('1) Open this folder in VS Code.');
      log('2) Open Chat and switch to Agent mode.');
      log('3) Paste the prompt below:\n');
      log(`  ${INIT_PROMPT}\n`);
      if (commandExists('code')) spawnSync('code', ['.'], { stdio: 'ignore' });
      return;
    case 'windsurf':
      if (copyToClipboard(INIT_PROMPT)) log('Prompt copied to clipboard.');
      else log('(clipboard unavailable - copy manually below)');
      log('');
      log('Windsurf Cascade runs in-IDE.');
      log('1) Open this folder in Windsurf.');
      log('2) Open Cascade in Write mode.');
      log('3) Paste the prompt below:\n');
      log(`  ${INIT_PROMPT}\n`);
      if (commandExists('windsurf')) spawnSync('windsurf', ['.'], { stdio: 'ignore' });
      return;
    case 'kiro':
      if (copyToClipboard(INIT_PROMPT)) log('Prompt copied to clipboard.');
      else log('(clipboard unavailable - copy manually below)');
      log('');
      log('Kiro runs in-IDE.');
      log('1) Open this folder in Kiro.');
      log('2) Open Chat in Agent mode.');
      log('3) Paste the prompt below:\n');
      log(`  ${INIT_PROMPT}\n`);
      if (commandExists('kiro')) spawnSync('kiro', ['.'], { stdio: 'ignore' });
      return;
    case 'copilot':
      requireCmd('gh', 'https://cli.github.com');
      if (copyToClipboard(INIT_PROMPT)) log('Prompt copied to clipboard.');
      else log('(clipboard unavailable - copy manually below)');
      log('');
      log('GitHub Copilot CLI does not run an autonomous agent loop.');
      log('Open Copilot Chat (VS Code / IDE) and paste the prompt:\n');
      log(`  ${INIT_PROMPT}\n`);
      return;
    case 'deepseek':
      requireCmd('aider', 'pipx install aider-chat');
      return execHandoff('aider', ['--model', 'deepseek/deepseek-coder', '--message', INIT_PROMPT]);
    case 'kimi':
      requireCmd('aider', 'pipx install aider-chat');
      return execHandoff('aider', ['--model', 'openrouter/moonshotai/kimi-k2', '--message', INIT_PROMPT]);
    case 'minimax':
      requireCmd('aider', 'pipx install aider-chat');
      return execHandoff('aider', ['--model', 'openrouter/minimax/minimax-text-01', '--message', INIT_PROMPT]);
    case 'glm':
      requireCmd('aider', 'pipx install aider-chat');
      return execHandoff('aider', ['--model', 'openrouter/z-ai/glm-4.5', '--message', INIT_PROMPT]);
    case 'hermes':
      requireCmd('hermes', 'https://github.com/NousResearch/hermes-agent');
      copyToClipboard(INIT_PROMPT);
      log('(prompt copied to clipboard as fallback)');
      return execHandoff('hermes', [INIT_PROMPT]);
    case 'openclaw':
      requireCmd('openclaw', 'npm install -g openclaw@latest');
      copyToClipboard(INIT_PROMPT);
      log('(prompt copied to clipboard as fallback)');
      return execHandoff('openclaw', [INIT_PROMPT]);
    case 'aider':
      requireCmd('aider', 'pipx install aider-chat');
      return execHandoff('aider', ['--message', INIT_PROMPT]);
    case 'other':
      if (copyToClipboard(INIT_PROMPT)) log('Prompt copied to clipboard. Paste it into your CLI/agent of choice.');
      else log('(clipboard unavailable - copy the prompt below manually)');
      log('\nPrompt:');
      log(`  ${INIT_PROMPT}\n`);
      return;
    case 'skip':
    default:
      log(`Skipped CLI handoff. To run INIT.md later, open your agent and paste:\n\n  ${INIT_PROMPT}\n`);
      log('Recommended next steps:');
      log('  1) Open an agent in this folder.');
      log('  2) Paste the prompt above.');
      log('  3) Review .specs/product/VISION.md, DOMAIN.md, architecture/DESIGN.md.');
      log('  4) git add -A && git commit -m "chore: bootstrap agentic starter"\n');
      log('Docs: https://github.com/wesleysimplicio/llm-project-mapper');
      return;
  }
}

async function main() {
  if (path.resolve(CWD) === path.resolve(PACKAGE_ROOT)) {
    err('Refusing to scaffold into the package source directory.');
    err('Run this command from inside the project where you want the starter.');
    process.exit(2);
  }

  const projectMode = detectProjectMode();
  const projects = detectProjects();
  const productName = projectMode === 'monorepo' ? path.basename(CWD) : detectProductName();
  const stack = projectMode === 'monorepo' ? 'monorepo' : detectStack();

  log('==========================================');
  log('  Agentic Starter - Bootstrap (npx)');
  log(`  v${PKG.version}`);
  log('==========================================\n');
  log('Auto-detected (agent will infer team/domain/personas/vision from code):');
  log(`  PROJECT_MODE: ${projectMode}`);
  log(`  PRODUCT_NAME: ${productName}`);
  log(`  STACK:        ${stack}`);
  if (projectMode === 'monorepo') {
    log(`  PROJECTS:     ${JSON.stringify(projects)}`);
  }
  log(`  MODE:         ${opts.dryRun ? 'dry-run' : 'write'}${opts.force ? ' (force)' : ''}\n`);

  const existingInstructionFiles = detectExistingInstructionFiles();
  if (existingInstructionFiles.length > 0) {
    log('Detected pre-existing instruction files (will be preserved):');
    for (const file of existingInstructionFiles) log(`  - ${file}`);
    log('  -> INIT.md will READ them and IMPROVE in place (essence preserved).\n');
  }

  copyTemplate(existingInstructionFiles);

  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  try {
    await handleGitignore(rl);
    substitute(productName, stack);
    writeMeta(productName, stack, projectMode, projects, existingInstructionFiles);
    log('');

    const cliChoice = await chooseCli(rl);
    rl.close();
    handoff(cliChoice);
  } finally {
    try {
      rl.close();
    } catch {
      // Already closed.
    }
  }
}

main().catch((error) => {
  err('Error:', error && error.stack || error);
  process.exit(1);
});
