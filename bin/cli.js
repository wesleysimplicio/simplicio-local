#!/usr/bin/env node
/**
 * Agentic Starter - CLI scaffolder.
 *
 * Run inside any project to install the starter pack:
 *   npx @wesleysimplicio/agentic-starter
 *
 * Behavior (mirror of bootstrap.sh / bootstrap.ps1):
 *   1. Auto-detects PRODUCT_NAME (cwd basename), DOMAIN ("generico"),
 *      TEAM ("Plataforma"), STACK (Node/.NET/Python/Go/Rust/Flutter/PHP/...).
 *      INIT.md refines TEAM/DOMAIN with the human afterwards.
 *   2. Asks only TWO questions:
 *        - Append recommended ignore entries to .gitignore? (y/N)
 *        - Which CLI/LLM should run INIT.md?
 *   3. Substitutes <PRODUCT_NAME>/<TEAM>/<DOMAIN>/<STACK> ONLY inside
 *      starter-managed paths AND only when the file actually contains
 *      a placeholder (protects user .razor/.cs/.ts/.py/package.json).
 *   4. NEVER overwrites pre-existing user files. Existing instruction
 *      files (AGENTS.md/CLAUDE.md/INIT.md/copilot-instructions.md) are
 *      preserved AND flagged in .starter-meta.json so INIT.md can read
 *      them and improve in place (essence preserved).
 *   5. .gitignore: never overwritten. Appended on opt-in, created if missing.
 *   6. Hands off to the chosen CLI to execute INIT.md.
 *
 * Pure Node.js. No bash dependency. Works on macOS, Linux, and Windows.
 */

'use strict';

const fs = require('node:fs');
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

const RECOMMENDED_IGNORES = `# === Agentic Starter (auto-managed) — do not remove this header ===
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
  { key: 'claude',   label: 'Claude Code',                                                       cmd: 'claude' },
  { key: 'codex',    label: 'Codex CLI',                                                         cmd: 'codex' },
  { key: 'copilot',  label: 'GitHub Copilot CLI (chat — no agent loop)',                         cmd: 'gh' },
  { key: 'cursor',   label: 'Cursor Agent (cursor-agent)',                                       cmd: 'cursor-agent' },
  { key: 'deepseek', label: 'Deepseek (via aider --model deepseek/deepseek-coder)',              cmd: 'aider' },
  { key: 'kimi',     label: 'Kimi K2.6 (via aider --model openrouter/moonshotai/kimi-k2)',       cmd: 'aider' },
  { key: 'minimax',  label: 'MiniMax M2.7 (via aider --model openrouter/minimax/minimax-text-01)', cmd: 'aider' },
  { key: 'glm',      label: 'GLM 5.1 (via aider --model openrouter/z-ai/glm-4.5)',               cmd: 'aider' },
  { key: 'hermes',   label: 'Hermes Agent (Nous Research)',                                      cmd: 'hermes' },
  { key: 'openclaw', label: 'OpenClaw',                                                          cmd: 'openclaw' },
  { key: 'aider',    label: 'Aider (pick model interactively)',                                  cmd: 'aider' },
  { key: 'other',    label: 'Other / manual (copy prompt to clipboard)',                         cmd: '' },
  { key: 'skip',     label: 'Skip — I will run INIT.md later',                                   cmd: '' },
];

const INIT_PROMPT = 'Read INIT.md and execute it. Do NOT modify any user source files (.razor, .cs, .ts, .py, .go, .rs, package.json, etc). Only write inside .specs/, .agents/, .skills/, .claude/, .codex/, .github/copilot*, .github/workflows/dod.yml plus root AGENTS.md/CLAUDE.md/INIT.md/README*.md. If AGENTS.md/CLAUDE.md/copilot-instructions.md already existed before bootstrap (see .starter-meta.json), READ them and IMPROVE in place — preserve their essence. Ask the human only the questions listed in .starter-meta.json -> init_must_ask (team, domain, vision oneliner, personas). Use parallel multi-agents.';

const argv = process.argv.slice(2);
const opts = {
  yes: false,
  force: false,
  dryRun: false,
  silent: false,
  skipMeta: false,
  cli: '',
  appendGitignore: '',
};

for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  switch (a) {
    case '-y':
    case '--yes':              opts.yes = true; break;
    case '-f':
    case '--force':            opts.force = true; break;
    case '--dry-run':          opts.dryRun = true; break;
    case '--silent':           opts.silent = true; break;
    case '--skip-meta':        opts.skipMeta = true; break;
    case '--cli':              opts.cli = argv[++i]; break;
    case '--append-gitignore': opts.appendGitignore = argv[++i]; break;
    case '-v':
    case '--version':
      console.log(PKG.version);
      process.exit(0);
    case '-h':
    case '--help':
      printHelp();
      process.exit(0);
    default:
      console.error(`Unknown flag: ${a}`);
      console.error('Run with --help for usage.');
      process.exit(2);
  }
}

function printHelp() {
  console.log(`agentic-starter v${PKG.version}

Scaffold the Agentic Starter pack into the current directory.

USAGE
  npx @wesleysimplicio/agentic-starter [options]

OPTIONS
  -y, --yes                   Non-interactive (defaults: no gitignore append, skip CLI handoff)
  -f, --force                 Overwrite starter template files (NEVER touches user
                              instruction files: AGENTS.md, CLAUDE.md, INIT.md,
                              .github/copilot-instructions.md, .gitignore)
  --dry-run                   Print actions without writing files
  --skip-meta                 Do not write .starter-meta.json
  --cli <key>                 Pick CLI for INIT.md handoff (claude|codex|copilot|cursor|
                              deepseek|kimi|minimax|glm|hermes|openclaw|aider|other|skip)
  --append-gitignore <yes|no> Append recommended ignores to .gitignore (or create it)
  --silent                    Minimal output
  -v, --version               Print version
  -h, --help                  Show this help

EXAMPLES
  npx @wesleysimplicio/agentic-starter
  npx @wesleysimplicio/agentic-starter --yes
  npx @wesleysimplicio/agentic-starter --yes --cli claude --append-gitignore yes

DOCS
  https://github.com/wesleysimplicio/agentic-starter
`);
}

const log = (...a) => { if (!opts.silent) console.log(...a); };
const err = (...a) => console.error(...a);

function readSafe(p) { try { return fs.readFileSync(p, 'utf8'); } catch { return ''; } }
function existsHere(rel) { return fs.existsSync(path.join(CWD, rel)); }
function listCwd() { try { return fs.readdirSync(CWD); } catch { return []; } }
function commandExists(cmd) {
  if (!cmd) return false;
  const which = process.platform === 'win32' ? 'where' : 'which';
  const r = spawnSync(which, [cmd], { stdio: 'ignore' });
  return r.status === 0;
}

function detectStack() {
  if (existsHere('package.json')) {
    const pj = readSafe(path.join(CWD, 'package.json'));
    if (/"next"\s*:/.test(pj))                    return 'next-ts';
    if (/"react"\s*:/.test(pj))                   return 'react-ts';
    if (/"vue"\s*:/.test(pj))                     return 'vue-ts';
    if (/"@nestjs\/core"|"nestjs"\s*:/.test(pj))  return 'nestjs';
    if (/"express"\s*:/.test(pj))                 return 'node-express';
    return 'node-ts';
  }
  const files = listCwd();
  if (files.some(f => f.endsWith('.csproj') || f.endsWith('.sln'))) return 'dotnet';
  if (existsHere('pyproject.toml') || existsHere('requirements.txt')) {
    const py = readSafe(path.join(CWD, 'pyproject.toml')) + readSafe(path.join(CWD, 'requirements.txt'));
    if (/django/i.test(py))   return 'python-django';
    if (/fastapi/i.test(py))  return 'python-fastapi';
    if (/flask/i.test(py))    return 'python-flask';
    return 'python';
  }
  if (existsHere('go.mod'))         return 'go';
  if (existsHere('Cargo.toml'))     return 'rust';
  if (existsHere('pubspec.yaml'))   return 'flutter';
  if (existsHere('composer.json')) {
    return /laravel\/framework/.test(readSafe(path.join(CWD, 'composer.json'))) ? 'laravel' : 'php';
  }
  if (existsHere('Gemfile'))           return 'ruby';
  if (existsHere('mix.exs'))           return 'elixir';
  if (existsHere('build.gradle.kts'))  return 'kotlin-gradle';
  if (existsHere('build.gradle'))      return 'java-gradle';
  if (existsHere('pom.xml'))           return 'java-maven';
  return 'unknown';
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
  let copied = 0, skipped = 0, missing = 0;

  for (const rel of TEMPLATE_PATHS) {
    const src = path.join(PACKAGE_ROOT, rel);
    const dest = path.join(CWD, rel);

    if (!fs.existsSync(src)) { missing++; continue; }

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
    } catch (e) {
      err(`  fail  ${rel}: ${e.message}`);
    }
  }

  log(`\n→ ${copied} copied, ${skipped} skipped${opts.force ? '' : ' (use --force to overwrite starter files)'}, ${missing} missing in package.\n`);
}

async function handleGitignore(rl) {
  let choice = opts.appendGitignore;
  if (!choice && !opts.yes) {
    log('==========================================');
    log('  .gitignore');
    log('==========================================');
    if (existsHere('.gitignore')) {
      log('An existing .gitignore was found.');
      log('I can APPEND recommended entries (your existing content is NEVER modified).');
    } else {
      log('No .gitignore found. I can CREATE one with recommended entries.');
    }
    const resp = await ask(rl, 'Proceed?', 'n');
    choice = /^[ys]/i.test(resp) ? 'yes' : 'no';
    log('');
  }
  choice = choice || 'no';

  if (choice !== 'yes') {
    log('→ .gitignore left untouched.\n');
    return;
  }

  const gi = path.join(CWD, '.gitignore');
  if (fs.existsSync(gi)) {
    const existing = readSafe(gi);
    if (existing.includes('Agentic Starter (auto-managed)')) {
      log('→ Recommended entries already present in .gitignore. Nothing to do.\n');
    } else if (opts.dryRun) {
      log('  append (dry):   .gitignore\n');
    } else {
      fs.appendFileSync(gi, '\n' + RECOMMENDED_IGNORES);
      log('→ Recommended entries APPENDED to .gitignore (original content preserved).\n');
    }
  } else if (opts.dryRun) {
    log('  create (dry):   .gitignore\n');
  } else {
    fs.writeFileSync(gi, RECOMMENDED_IGNORES);
    log('→ .gitignore CREATED.\n');
  }

  const ga = path.join(CWD, '.gitattributes');
  if (!fs.existsSync(ga)) {
    if (opts.dryRun) {
      log('  create (dry):   .gitattributes');
    } else {
      fs.writeFileSync(ga, GITATTRIBUTES_CONTENT);
      log('→ .gitattributes CREATED.');
    }
  } else {
    log('→ .gitattributes left untouched (already exists).');
  }
  log('');
}

function looksBinary(buf) {
  const head = buf.length > 8192 ? buf.subarray(0, 8192) : buf;
  return head.includes(0);
}

function substituteInFile(file, productName, team, domain, stack) {
  let content;
  try {
    const buf = fs.readFileSync(file);
    if (buf.length === 0) return false;
    if (looksBinary(buf)) return false;
    content = buf.toString('utf8');
  } catch { return false; }

  if (!/<PRODUCT_NAME>|<TEAM>|<DOMAIN>|<STACK>/.test(content)) return false;

  const next = content
    .replace(/<PRODUCT_NAME>/g, productName)
    .replace(/<TEAM>/g, team)
    .replace(/<DOMAIN>/g, domain)
    .replace(/<STACK>/g, stack);

  if (next === content) return false;
  if (!opts.dryRun) fs.writeFileSync(file, next);
  return true;
}

function walk(dir, cb) {
  let entries;
  try { entries = fs.readdirSync(dir, { withFileTypes: true }); }
  catch { return; }
  for (const entry of entries) {
    if (WALK_SKIP_DIRS.has(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, cb);
    else if (entry.isFile()) cb(full);
  }
}

function substitute(productName, team, domain, stack) {
  let touched = 0;
  const stamp = (file) => {
    if (substituteInFile(file, productName, team, domain, stack)) touched++;
  };

  for (const dir of STARTER_DIRS) {
    const abs = path.join(CWD, dir);
    if (!fs.existsSync(abs)) continue;
    walk(abs, (file) => {
      if (TEXT_EXTS.has(path.extname(file))) stamp(file);
    });
  }

  for (const p of STARTER_GITHUB_PATTERNS) {
    const abs = path.join(CWD, p);
    if (!fs.existsSync(abs)) continue;
    const stat = fs.statSync(abs);
    if (stat.isDirectory()) walk(abs, stamp);
    else if (stat.isFile()) stamp(abs);
  }

  for (const f of STARTER_ROOT_FILES) {
    const abs = path.join(CWD, f);
    if (fs.existsSync(abs)) stamp(abs);
  }

  log(`→ ${touched} files updated (only starter-managed paths)${opts.dryRun ? ' (dry-run)' : ''}.\n`);
}

function writeMeta(productName, team, domain, stack, existingInstructionFiles) {
  if (opts.skipMeta) return;
  const meta = {
    product_name: productName,
    team: team,
    domain: domain,
    stack: stack,
    bootstrapped_at: new Date().toISOString(),
    starter_version: PKG.version,
    cli: '@wesleysimplicio/agentic-starter',
    existing_instruction_files: existingInstructionFiles,
    init_must_ask: ['team', 'domain', 'vision_oneliner', 'primary_personas'],
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
  log('→ .starter-meta.json saved.');
}

function ask(rl, q, def) {
  return new Promise(resolve => {
    rl.question(`${q} [${def}]: `, ans => resolve((ans || '').trim() || def));
  });
}

async function chooseCli(rl) {
  if (opts.cli) return opts.cli;
  if (opts.yes) return 'skip';

  log('==========================================');
  log('  Choose the CLI/LLM to run INIT.md');
  log('==========================================\n');
  CLI_OPTS.forEach((o, i) => {
    const mark = commandExists(o.cmd) ? '  [installed]' : '';
    log(`  [${String(i + 1).padStart(2, ' ')}] ${o.label}${mark}`);
  });
  log('');
  const resp = await ask(rl, 'Number', String(CLI_OPTS.length));
  let idx = parseInt(resp, 10);
  if (!Number.isFinite(idx) || idx < 1 || idx > CLI_OPTS.length) idx = CLI_OPTS.length;
  return CLI_OPTS[idx - 1].key;
}

function copyToClipboard(text) {
  const candidates = process.platform === 'darwin'
    ? [['pbcopy', []]]
    : process.platform === 'win32'
      ? [['clip', []]]
      : [['xclip', ['-selection', 'clipboard']], ['wl-copy', []]];
  for (const [cmd, args] of candidates) {
    try {
      const r = spawnSync(cmd, args, { input: text, stdio: ['pipe', 'ignore', 'ignore'] });
      if (r.status === 0) return true;
    } catch { /* try next */ }
  }
  return false;
}

function execHandoff(cmd, args) {
  const child = spawn(cmd, args, { stdio: 'inherit' });
  child.on('exit', (code) => process.exit(code ?? 0));
  child.on('error', (e) => {
    err(`Failed to launch ${cmd}: ${e.message}`);
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
    case 'copilot':
      requireCmd('gh', 'https://cli.github.com');
      if (copyToClipboard(INIT_PROMPT)) log('Prompt copied to clipboard.');
      else log('(clipboard unavailable - copy manually below)');
      log('');
      log('GitHub Copilot CLI does not run an autonomous agent loop.');
      log('Open Copilot Chat (VS Code / IDE) and paste the prompt:\n');
      log(`  ${INIT_PROMPT}\n`);
      return;
    case 'cursor':
      requireCmd('cursor-agent', 'Cursor 3.0+ required');
      return execHandoff('cursor-agent', [INIT_PROMPT]);
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
      if (copyToClipboard(INIT_PROMPT)) {
        log('Prompt copied to clipboard. Paste it into your CLI/agent of choice.');
      } else {
        log('(clipboard unavailable - copy the prompt below manually)');
      }
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
      log('Docs: https://github.com/wesleysimplicio/agentic-starter');
      return;
  }
}

async function main() {
  if (path.resolve(CWD) === path.resolve(PACKAGE_ROOT)) {
    err('Refusing to scaffold into the package source directory.');
    err('Run this command from inside the project where you want the starter.');
    process.exit(2);
  }

  const productName = path.basename(CWD);
  const team        = 'Plataforma';
  const domain      = 'generico';
  const stack       = detectStack();

  log('==========================================');
  log('  Agentic Starter - Bootstrap (npx)');
  log(`  v${PKG.version}`);
  log('==========================================\n');
  log('Auto-detected (INIT.md will refine TEAM/DOMAIN with you):');
  log(`  PRODUCT_NAME: ${productName}`);
  log(`  TEAM:         ${team}`);
  log(`  DOMAIN:       ${domain}`);
  log(`  STACK:        ${stack}`);
  log(`  MODE:         ${opts.dryRun ? 'dry-run' : 'write'}${opts.force ? ' (force)' : ''}\n`);

  const existingInstructionFiles = detectExistingInstructionFiles();
  if (existingInstructionFiles.length > 0) {
    log('Detected pre-existing instruction files (will be preserved):');
    for (const f of existingInstructionFiles) log(`  - ${f}`);
    log('  -> INIT.md will READ them and IMPROVE in place (essence preserved).\n');
  }

  copyTemplate(existingInstructionFiles);

  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  try {
    await handleGitignore(rl);
    substitute(productName, team, domain, stack);
    writeMeta(productName, team, domain, stack, existingInstructionFiles);
    log('');

    const cliChoice = await chooseCli(rl);
    rl.close();
    handoff(cliChoice);
  } finally {
    try { rl.close(); } catch { /* already closed */ }
  }
}

main().catch(e => {
  err('Error:', e && e.stack || e);
  process.exit(1);
});
