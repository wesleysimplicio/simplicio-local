'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '..');
const cli = path.join(root, 'bin', 'cli.js');
const packageJson = require(path.join(root, 'package.json'));

function runCli(args, cwd, options = {}) {
  return spawnSync(process.execPath, [cli, ...args], {
    cwd,
    encoding: 'utf8',
    env: { ...process.env, NO_COLOR: '1', ...(options.env || {}) },
  });
}

function makeTempProject(name = 'agentic-target') {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), `${name}-`));
  fs.writeFileSync(
    path.join(dir, 'package.json'),
    JSON.stringify({
      name,
      version: '1.0.0',
      dependencies: { next: '14.0.0', react: '18.0.0' },
    }, null, 2),
  );
  return dir;
}

test('prints help and version', () => {
  const help = runCli(['--help'], root);
  assert.equal(help.status, 0, help.stderr);
  assert.match(help.stdout, /llm-project-mapper/);
  assert.match(help.stdout, /--append-gitignore/);
  assert.match(help.stdout, /windsurf\|kiro\|copilot/);

  const version = runCli(['--version'], root);
  assert.equal(version.status, 0, version.stderr);
  assert.equal(version.stdout.trim(), packageJson.version);
});

test('refuses to scaffold into the package source directory', () => {
  const result = runCli(['--yes', '--cli', 'skip'], root);
  assert.equal(result.status, 2);
  assert.match(result.stderr, /Refusing to scaffold/);
});

test('rejects unknown flags', () => {
  const target = makeTempProject('bad-flag-target');
  const result = runCli(['--wat'], target);
  assert.equal(result.status, 2);
  assert.match(result.stderr, /Unknown flag/);
});

test('dry-run does not write starter files into target project', () => {
  const target = makeTempProject('dry-target');
  const result = runCli([
    '--dry-run',
    '--yes',
    '--cli',
    'skip',
    '--append-gitignore',
    'no',
  ], target);

  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /dry-run/);
  assert.equal(fs.existsSync(path.join(target, 'AGENTS.md')), false);
  assert.equal(fs.existsSync(path.join(target, '.starter-meta.json')), false);
});

test('detects common project stacks during dry-run', () => {
  const cases = [
    ['next-ts', { 'package.json': { dependencies: { next: '14.0.0' } } }],
    ['react-ts', { 'package.json': { dependencies: { react: '18.0.0' } } }],
    ['vue-ts', { 'package.json': { dependencies: { vue: '3.0.0' } } }],
    ['nestjs', { 'package.json': { dependencies: { '@nestjs/core': '10.0.0' } } }],
    ['node-express', { 'package.json': { dependencies: { express: '4.0.0' } } }],
    ['dotnet', { 'app.csproj': '<Project />' }],
    ['python-django', { 'pyproject.toml': 'django = "*"' }],
    ['python-fastapi', { 'requirements.txt': 'fastapi\n' }],
    ['python-flask', { 'requirements.txt': 'flask\n' }],
    ['python', { 'requirements.txt': 'pytest\n' }],
    ['go', { 'go.mod': 'module example.com/app\n' }],
    ['rust', { 'Cargo.toml': '[package]\nname = "demo"\n' }],
    ['flutter', { 'pubspec.yaml': 'name: demo\n' }],
    ['laravel', { 'composer.json': { require: { 'laravel/framework': '^11.0' } } }],
    ['php', { 'composer.json': { require: { 'monolog/monolog': '^3.0' } } }],
    ['ruby', { Gemfile: 'source "https://rubygems.org"\n' }],
    ['elixir', { 'mix.exs': 'defmodule Demo.MixProject do end\n' }],
    ['kotlin-gradle', { 'build.gradle.kts': 'plugins {}\n' }],
    ['java-gradle', { 'build.gradle': 'plugins {}\n' }],
    ['java-maven', { 'pom.xml': '<project />\n' }],
    ['unknown', {}],
  ];

  for (const [expected, files] of cases) {
    const target = fs.mkdtempSync(path.join(os.tmpdir(), `stack-${expected}-`));
    for (const [file, value] of Object.entries(files)) {
      const content = typeof value === 'string'
        ? value
        : JSON.stringify({ name: 'demo', version: '1.0.0', ...value }, null, 2);
      fs.writeFileSync(path.join(target, file), content);
    }

    const result = runCli([
      '--dry-run',
      '--yes',
      '--cli',
      'skip',
      '--append-gitignore',
      'no',
    ], target);

    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, new RegExp(`STACK:\\s+${expected}`));
  }
});

test('writes starter files, metadata, and ignores into target project', () => {
  const target = makeTempProject('write-target');
  const result = runCli([
    '--yes',
    '--cli',
    'skip',
    '--append-gitignore',
    'yes',
    '--silent',
  ], target);

  assert.equal(result.status, 0, result.stderr);
  assert.equal(fs.existsSync(path.join(target, 'AGENTS.md')), true);
  assert.equal(fs.existsSync(path.join(target, 'INIT.md')), true);
  assert.equal(fs.existsSync(path.join(target, '_BOOTSTRAP.md')), true);
  assert.equal(fs.existsSync(path.join(target, '.codex', 'config.toml')), true);
  assert.equal(fs.existsSync(path.join(target, 'tests')), true);

  const meta = JSON.parse(fs.readFileSync(path.join(target, '.starter-meta.json'), 'utf8'));
  assert.equal(meta.product_name, 'write-target');
  assert.equal(meta.stack, 'next-ts');
  assert.equal(meta.cli, '@wesleysimplicio/llm-project-mapper');
  assert.equal(meta.project_mode, 'root');
  assert.deepEqual(meta.projects, []);
  assert.deepEqual(meta.init_must_ask, []);
  assert.equal(meta.default_persona, 'developer');

  const gitignore = fs.readFileSync(path.join(target, '.gitignore'), 'utf8');
  assert.match(gitignore, /Agentic Starter/);
});

test('detects monorepo mode and project manifests inside projects/', () => {
  const target = fs.mkdtempSync(path.join(os.tmpdir(), 'monorepo-target-'));
  fs.mkdirSync(path.join(target, 'projects'));
  fs.mkdirSync(path.join(target, 'projects', 'web'));
  fs.mkdirSync(path.join(target, 'projects', 'api'));
  fs.writeFileSync(
    path.join(target, 'projects', 'web', 'package.json'),
    JSON.stringify({ name: 'web-app', version: '1.0.0', dependencies: { next: '14.0.0' } }, null, 2),
  );
  fs.writeFileSync(path.join(target, 'projects', 'api', 'go.mod'), 'module example.com/runtime/api\n');

  const result = runCli([
    '--yes',
    '--cli',
    'skip',
    '--append-gitignore',
    'no',
    '--silent',
  ], target);

  assert.equal(result.status, 0, result.stderr);
  const meta = JSON.parse(fs.readFileSync(path.join(target, '.starter-meta.json'), 'utf8'));
  assert.equal(meta.project_mode, 'monorepo');
  assert.equal(meta.stack, 'monorepo');
  assert.deepEqual(meta.projects, [
    { name: 'api', path: 'projects/api', stack: 'go' },
    { name: 'web-app', path: 'projects/web', stack: 'next-ts' },
  ]);
});

test('supports skip-meta and repeated gitignore appends', () => {
  const target = makeTempProject('skip-meta-target');
  fs.writeFileSync(
    path.join(target, '.gitignore'),
    '# === Agentic Starter (auto-managed) - do not remove this header ===\n',
  );
  fs.writeFileSync(path.join(target, '.gitattributes'), '* text=auto\n');

  const result = runCli([
    '--yes',
    '--cli',
    'skip',
    '--append-gitignore',
    'yes',
    '--skip-meta',
    '--silent',
  ], target);

  assert.equal(result.status, 0, result.stderr);
  assert.equal(fs.existsSync(path.join(target, '.starter-meta.json')), false);
  assert.equal(fs.readFileSync(path.join(target, '.gitattributes'), 'utf8'), '* text=auto\n');
});

test('preserves existing instruction files and records merge metadata', () => {
  const target = makeTempProject('protected-target');
  const originalAgents = '# Existing rules\n\nKeep this exact text.\n';
  fs.writeFileSync(path.join(target, 'AGENTS.md'), originalAgents);

  const result = runCli([
    '--yes',
    '--cli',
    'skip',
    '--append-gitignore',
    'no',
    '--silent',
  ], target);

  assert.equal(result.status, 0, result.stderr);
  assert.equal(fs.readFileSync(path.join(target, 'AGENTS.md'), 'utf8'), originalAgents);

  const meta = JSON.parse(fs.readFileSync(path.join(target, '.starter-meta.json'), 'utf8'));
  assert.deepEqual(meta.existing_instruction_files, ['AGENTS.md']);
  assert.deepEqual(meta.init_must_merge, ['AGENTS.md']);
});

test('can overwrite starter-managed files with force', () => {
  const target = makeTempProject('force-target');
  fs.writeFileSync(path.join(target, 'playwright.config.ts'), '// old config\n');

  const result = runCli([
    '--yes',
    '--force',
    '--cli',
    'skip',
    '--append-gitignore',
    'no',
    '--silent',
  ], target);

  assert.equal(result.status, 0, result.stderr);
  assert.notEqual(fs.readFileSync(path.join(target, 'playwright.config.ts'), 'utf8'), '// old config\n');
});

test('manual handoff prints prompt when clipboard is unavailable', () => {
  const target = makeTempProject('manual-handoff-target');
  const result = runCli([
    '--dry-run',
    '--yes',
    '--cli',
    'other',
    '--append-gitignore',
    'no',
  ], target, { env: { PATH: '' } });

  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /clipboard unavailable/);
  assert.match(result.stdout, /Read INIT.md and execute it/);
  assert.match(result.stdout, /DO NOT ask the human about team, domain, vision, personas/);
});

test('installed CLI choices fail fast when command is unavailable', () => {
  const target = makeTempProject('missing-cli-target');
  const result = runCli([
    '--dry-run',
    '--yes',
    '--cli',
    'codex',
    '--append-gitignore',
    'no',
  ], target, { env: { PATH: '' } });

  assert.equal(result.status, 1);
  assert.match(result.stderr, /codex not installed/);
});

test('ide handoff options print local guidance without crashing', () => {
  const target = makeTempProject('ide-handoff-target');
  for (const cliKey of ['vscode', 'windsurf', 'kiro']) {
    const result = runCli([
      '--dry-run',
      '--yes',
      '--cli',
      cliKey,
      '--append-gitignore',
      'no',
    ], target, { env: { PATH: '' } });

    assert.equal(result.status, 0, `${cliKey}: ${result.stderr}`);
    assert.match(result.stdout, /runs in-IDE|Open this folder/);
  }
});
