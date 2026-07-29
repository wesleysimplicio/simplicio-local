'use strict';

const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '..');
const cli = path.join(root, 'bin', 'us4-cli.js');
const packageJson = require(path.join(root, 'package.json'));

function runCli(args, options = {}) {
  return spawnSync(process.execPath, [cli, ...args], {
    cwd: root,
    encoding: 'utf8',
    env: { ...process.env, NO_COLOR: '1', ...(options.env || {}) },
  });
}

test('prints product help and version', () => {
  const help = runCli(['--help']);
  assert.equal(help.status, 0, help.stderr);
  assert.match(help.stdout, /us4-cli product wrapper/);
  assert.match(help.stdout, /doctor/);
  assert.match(help.stdout, /plan/);
  assert.match(help.stdout, /convert/);
  assert.match(help.stdout, /chat/);
  assert.match(help.stdout, /serve/);
  assert.match(help.stdout, /backend/);
  assert.match(help.stdout, /prototype/);

  const version = runCli(['--version']);
  assert.equal(version.status, 0, version.stderr);
  assert.equal(version.stdout.trim(), packageJson.version);
});

test('local inference status is read-only and exposes the stable pause reason', () => {
  const paused = runCli(['local-inference-status', '--json'], { env: { PATH: '' } });
  assert.equal(paused.status, 0, paused.stderr);
  assert.deepEqual(JSON.parse(paused.stdout), {
    local_inference: 'paused',
    reason: 'LOCAL_INFERENCE_PAUSED',
  });

  const admitted = runCli(['local-inference-status', '--json'], {
    env: {
      PATH: '',
      US4_LOCAL_INFERENCE: 'enabled',
      US4_RUNTIME_POLICY: 'admitted',
      US4_RUNTIME_LEASE: 'lease-test-only',
    },
  });
  assert.equal(admitted.status, 0, admitted.stderr);
  assert.deepEqual(JSON.parse(admitted.stdout), {
    local_inference: 'enabled',
    reason: 'runtime-policy-admitted',
  });
});

test('doctor fails clearly when python is unavailable', () => {
  const result = runCli(['doctor', '--help'], { env: { PATH: '' } });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Python 3 was not found/);
});

test('backend probe is read-only and versioned', () => {
  const result = runCli(['backend', 'probe', '--json']);
  assert.equal(result.status, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.protocol, 'simplicio.local-inference-backend/v1');
  assert.equal(report.read_only, true);
  assert.equal(report.model_payload_read, false);
  assert.equal(report.capabilities.tool_execution, 'forbidden');
});

test('prototype doctor preserves offline and no-effect policy', () => {
  const result = runCli(['prototype', 'doctor', '--json']);
  assert.equal(result.status, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.protocol, 'simplicio.prototype-worker/v1');
  assert.equal(report.offline, true);
  assert.equal(report.prompt_logging, false);
  assert.equal(report.effect_authority, 'none');
  assert.equal(report.receipt.protocol, 'simplicio.prototype-worker-receipt/v1');
  assert.equal(report.receipt.metrics_observed, false);
  assert.equal(report.receipt.metrics.latency_ms, null);
  assert.equal(report.receipt.metrics_unobserved_reason, 'doctor-does-not-run-inference');
});

test('prototype generate escalates without a Runtime inference lease', () => {
  const result = runCli([
    'prototype', 'generate', '--artifact-type', 'plan', '--json',
  ]);
  assert.equal(result.status, 78, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.status, 'escalate_remote');
  assert.equal(report.reason, 'runtime-inference-lease-required');
  assert.equal(report.receipt.status, 'escalated');
  assert.equal(report.receipt.failure_reason, 'runtime-inference-lease-required');
  assert.equal(report.receipt.metrics.tokens_per_second, null);
  assert.equal(report.receipt.metrics_unobserved_reason, 'runtime-inference-not-admitted');
});

test('chat fails clearly when npm is unavailable', () => {
  const result = runCli(['chat', '--build'], { env: { PATH: '' } });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /npm was not found/);
});

test('serve --native is paused before checking for a native binary', () => {
  const result = runCli(['serve', '--native'], { env: { PATH: '' } });
  assert.equal(result.status, 78);
  assert.match(result.stderr, /LOCAL_INFERENCE_PAUSED/);
});

test('local run and serve are paused before process, network, or model access', () => {
  for (const args of [['run', '--model', 'qwen-0.5b'], ['serve']]) {
    const result = runCli(args, { env: { PATH: '' } });
    assert.equal(result.status, 78, result.stderr);
    assert.match(result.stderr, /LOCAL_INFERENCE_PAUSED/);
    assert.match(result.stderr, /Runtime lease/);
  }
});

test('runtime admission is required as a complete policy and lease tuple', () => {
  const incomplete = runCli(['serve'], {
    env: { PATH: '', US4_LOCAL_INFERENCE: 'enabled', US4_RUNTIME_POLICY: 'admitted' },
  });
  assert.equal(incomplete.status, 78);
  assert.match(incomplete.stderr, /LOCAL_INFERENCE_PAUSED/);

  const admitted = runCli(['serve', '--native'], {
    env: {
      PATH: '',
      US4_LOCAL_INFERENCE: 'enabled',
      US4_RUNTIME_POLICY: 'admitted',
      US4_RUNTIME_LEASE: 'lease-test-only',
    },
  });
  assert.equal(admitted.status, 1);
  assert.doesNotMatch(admitted.stderr, /LOCAL_INFERENCE_PAUSED/);
  assert.match(admitted.stderr, /serve --native requires the built native binary/);
});

test('unknown commands are rejected', () => {
  const result = runCli(['produto']);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /unknown command/);
});


test('LiteRT dry-run is pinned, hash-verifiable, and has no write effect', () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'simplicio-litert-plan-'));
  try {
    const artifact = path.join(temp, 'fixture.bin');
    const bytes = Buffer.from('litert fixture\n');
    fs.writeFileSync(artifact, bytes);
    const sha256 = crypto.createHash('sha256').update(bytes).digest('hex');
    const manifest = {
      schema: 'simplicio.local-litert-package/v1',
      package: 'litert-lm-fixture',
      version: 'test.1',
      license: 'Apache-2.0',
      components: { litert_lm: 'test.1', litert: 'test.1' },
      artifacts: {
        'darwin-arm64': {
          name: 'fixture.bin',
          source: 'https://invalid.example.invalid/never-downloaded',
          size_bytes: bytes.length,
          sha256,
          executable: false,
        },
      },
    };
    const manifestPath = path.join(temp, 'manifest.json');
    const cache = path.join(temp, 'cache');
    fs.writeFileSync(manifestPath, JSON.stringify(manifest));
    const result = runCli([
      'backend', 'install', 'litert', '--dry-run', '--json',
      '--manifest', manifestPath, '--artifact', artifact,
      '--cache-dir', cache, '--platform', 'darwin-arm64',
    ]);
    assert.equal(result.status, 0, result.stderr);
    const report = JSON.parse(result.stdout);
    assert.equal(report.status, 'planned');
    assert.equal(report.writes, false);
    assert.equal(report.network, false);
    assert.equal(report.license, 'Apache-2.0');
    assert.equal(report.components.litert_lm, 'test.1');
    assert.equal(report.artifact.size_bytes, bytes.length);
    assert.equal(report.artifact.sha256, sha256);
    assert.match(report.manifest_sha256, /^[0-9a-f]{64}$/);
    assert.equal(fs.existsSync(cache), false);
  } finally {
    fs.rmSync(temp, { recursive: true, force: true });
  }
});

test('LiteRT yes install publishes atomically and records a receipt outside checkout', () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'simplicio-litert-install-'));
  try {
    const artifact = path.join(temp, 'fixture.bin');
    const bytes = Buffer.from('litert install fixture\n');
    fs.writeFileSync(artifact, bytes);
    const sha256 = crypto.createHash('sha256').update(bytes).digest('hex');
    const manifest = {
      schema: 'simplicio.local-litert-package/v1',
      package: 'litert-lm-fixture',
      version: 'test.1',
      license: 'Apache-2.0',
      components: { litert_lm: 'test.1', litert: 'test.1' },
      artifacts: {
        'darwin-arm64': {
          name: 'fixture.bin',
          source: 'https://invalid.example.invalid/never-downloaded',
          size_bytes: bytes.length,
          sha256,
          executable: false,
        },
      },
    };
    const manifestPath = path.join(temp, 'manifest.json');
    const cache = path.join(temp, 'cache');
    fs.writeFileSync(manifestPath, JSON.stringify(manifest));
    const result = runCli([
      'backend', 'install', 'litert', '--yes', '--json',
      '--manifest', manifestPath, '--artifact', artifact,
      '--cache-dir', cache, '--platform', 'darwin-arm64',
    ]);
    assert.equal(result.status, 0, result.stderr);
    const receipt = JSON.parse(result.stdout);
    assert.equal(receipt.status, 'completed');
    assert.equal(receipt.artifact.observed_sha256, sha256);
    assert.equal(receipt.artifact.observed_size_bytes, bytes.length);
    assert.equal(receipt.runtime_effect, 'package-cache-only');
    assert.equal(fs.readFileSync(receipt.destination, 'utf8'), bytes.toString());
    assert.equal(JSON.parse(fs.readFileSync(
      path.join(path.dirname(receipt.destination), 'install-receipt.json'), 'utf8',
    )).status, 'completed');
    assert.equal(path.resolve(receipt.destination).startsWith(path.resolve(root)), false);
  } finally {
    fs.rmSync(temp, { recursive: true, force: true });
  }
});

test('LiteRT install fails closed on hash mismatch and checkout cache', () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'simplicio-litert-fail-'));
  try {
    const artifact = path.join(temp, 'fixture.bin');
    const bytes = Buffer.from('tampered fixture\n');
    fs.writeFileSync(artifact, bytes);
    const manifest = {
      schema: 'simplicio.local-litert-package/v1',
      package: 'litert-lm-fixture',
      version: 'test.1',
      license: 'Apache-2.0',
      components: { litert_lm: 'test.1' },
      artifacts: {
        'darwin-arm64': {
          name: 'fixture.bin',
          source: artifact,
          size_bytes: bytes.length,
          sha256: '0'.repeat(64),
          executable: false,
        },
      },
    };
    const manifestPath = path.join(temp, 'manifest.json');
    const cache = path.join(temp, 'cache');
    fs.writeFileSync(manifestPath, JSON.stringify(manifest));
    const mismatch = runCli([
      'backend', 'install', 'litert', '--yes', '--json',
      '--manifest', manifestPath, '--artifact', artifact,
      '--cache-dir', cache, '--platform', 'darwin-arm64',
    ]);
    assert.equal(mismatch.status, 1);
    assert.equal(JSON.parse(mismatch.stdout).status, 'failed');
    assert.equal(fs.existsSync(path.join(
      cache, 'litert-lm-fixture', 'test.1', 'darwin-arm64', 'fixture.bin',
    )), false);

    const checkoutCache = runCli([
      'backend', 'install', 'litert', '--dry-run', '--json',
      '--manifest', manifestPath, '--artifact', artifact,
      '--cache-dir', root, '--platform', 'darwin-arm64',
    ]);
    assert.equal(checkoutCache.status, 1);
    assert.match(JSON.parse(checkoutCache.stdout).failure_reason, /outside the checkout/);
  } finally {
    fs.rmSync(temp, { recursive: true, force: true });
  }
});


test('LiteRT verify is offline and detects cache tampering', () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'simplicio-litert-verify-'));
  try {
    const artifact = path.join(temp, 'fixture.bin');
    const bytes = Buffer.from('offline fixture\n');
    fs.writeFileSync(artifact, bytes);
    const sha256 = crypto.createHash('sha256').update(bytes).digest('hex');
    const manifest = {
      schema: 'simplicio.local-litert-package/v1',
      package: 'litert-lm-fixture',
      version: 'test.2',
      license: 'Apache-2.0',
      components: { litert_lm: 'test.2' },
      artifacts: {
        'darwin-arm64': {
          name: 'fixture.bin',
          source: 'https://invalid.example.invalid/must-not-download',
          size_bytes: bytes.length,
          sha256,
          executable: false,
        },
      },
    };
    const manifestPath = path.join(temp, 'manifest.json');
    const cache = path.join(temp, 'cache');
    fs.writeFileSync(manifestPath, JSON.stringify(manifest));
    const install = runCli([
      'backend', 'install', 'litert', '--yes', '--json',
      '--manifest', manifestPath, '--artifact', artifact,
      '--cache-dir', cache, '--platform', 'darwin-arm64',
    ]);
    assert.equal(install.status, 0, install.stderr);
    const receipt = JSON.parse(install.stdout);
    const verify = runCli([
      'backend', 'install', 'litert', '--verify', '--json',
      '--manifest', manifestPath, '--cache-dir', cache,
      '--platform', 'darwin-arm64',
    ]);
    assert.equal(verify.status, 0, verify.stderr);
    const report = JSON.parse(verify.stdout);
    assert.equal(report.status, 'verified');
    assert.equal(report.offline, true);
    assert.equal(report.network, false);
    assert.equal(report.writes, false);
    fs.writeFileSync(receipt.destination, 'tampered\n');
    const tampered = runCli([
      'backend', 'install', 'litert', '--verify', '--json',
      '--manifest', manifestPath, '--cache-dir', cache,
      '--platform', 'darwin-arm64',
    ]);
    assert.equal(tampered.status, 0);
    const failure = JSON.parse(tampered.stdout);
    assert.equal(failure.status, 'failed');
    assert.equal(failure.failure_reason, 'offline-integrity-failure');
    assert.equal(failure.offline, true);
  } finally {
    fs.rmSync(temp, { recursive: true, force: true });
  }
});

test('LiteRT rollback requires yes and preserves unmanaged cache files', () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'simplicio-litert-rollback-'));
  try {
    const artifact = path.join(temp, 'fixture.bin');
    const bytes = Buffer.from('rollback fixture\n');
    fs.writeFileSync(artifact, bytes);
    const sha256 = crypto.createHash('sha256').update(bytes).digest('hex');
    const manifest = {
      schema: 'simplicio.local-litert-package/v1',
      package: 'litert-lm-fixture',
      version: 'test.3',
      license: 'Apache-2.0',
      components: { litert_lm: 'test.3' },
      artifacts: {
        'darwin-arm64': {
          name: 'fixture.bin',
          source: 'https://invalid.example.invalid/must-not-download',
          size_bytes: bytes.length,
          sha256,
          executable: false,
        },
      },
    };
    const manifestPath = path.join(temp, 'manifest.json');
    const cache = path.join(temp, 'cache');
    fs.writeFileSync(manifestPath, JSON.stringify(manifest));
    const install = runCli([
      'backend', 'install', 'litert', '--yes', '--json',
      '--manifest', manifestPath, '--artifact', artifact,
      '--cache-dir', cache, '--platform', 'darwin-arm64',
    ]);
    assert.equal(install.status, 0, install.stderr);
    const receipt = JSON.parse(install.stdout);
    const unmanaged = path.join(cache, 'unmanaged-model.litertlm');
    fs.writeFileSync(unmanaged, 'do not remove');
    const denied = runCli([
      'backend', 'install', 'litert', '--rollback', '--json',
      '--manifest', manifestPath, '--cache-dir', cache,
      '--platform', 'darwin-arm64',
    ]);
    assert.equal(denied.status, 1);
    assert.equal(fs.existsSync(receipt.destination), true);
    assert.match(JSON.parse(denied.stdout).failure_reason, /requires explicit --yes/);

    const rollback = runCli([
      'backend', 'install', 'litert', '--rollback', '--yes', '--json',
      '--manifest', manifestPath, '--cache-dir', cache,
      '--platform', 'darwin-arm64',
    ]);
    assert.equal(rollback.status, 0, rollback.stderr);
    const report = JSON.parse(rollback.stdout);
    assert.equal(report.status, 'rolled_back');
    assert.equal(report.offline, true);
    assert.equal(report.writes, true);
    assert.equal(fs.existsSync(receipt.destination), false);
    assert.equal(fs.existsSync(path.join(
      path.dirname(receipt.destination), 'install-receipt.json',
    )), false);
    assert.equal(fs.readFileSync(unmanaged, 'utf8'), 'do not remove');
  } finally {
    fs.rmSync(temp, { recursive: true, force: true });
  }
});

test('LiteRT verify reports an offline cache miss without network access', () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'simplicio-litert-miss-'));
  try {
    const manifestPath = path.join(temp, 'manifest.json');
    const cache = path.join(temp, 'cache');
    fs.writeFileSync(manifestPath, JSON.stringify({
      schema: 'simplicio.local-litert-package/v1',
      package: 'litert-lm-fixture',
      version: 'test.4',
      license: 'Apache-2.0',
      components: { litert_lm: 'test.4' },
      artifacts: {
        'darwin-arm64': {
          name: 'fixture.bin',
          source: 'https://invalid.example.invalid/must-not-download',
          size_bytes: 1,
          sha256: '0'.repeat(64),
          executable: false,
        },
      },
    }));
    const result = runCli([
      'backend', 'install', 'litert', '--verify', '--json',
      '--manifest', manifestPath, '--cache-dir', cache,
      '--platform', 'darwin-arm64',
    ]);
    assert.equal(result.status, 0);
    const report = JSON.parse(result.stdout);
    assert.equal(report.status, 'failed');
    assert.equal(report.failure_reason, 'offline-cache-miss');
    assert.equal(report.offline, true);
    assert.equal(report.network, false);
    assert.equal(fs.existsSync(cache), false);
  } finally {
    fs.rmSync(temp, { recursive: true, force: true });
  }
});


test('LiteRT model cache dry-run is content-addressed and offline', () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'simplicio-model-plan-'));
  try {
    const source = path.join(temp, 'fixture.litertlm');
    const bytes = Buffer.from('model plan fixture\n');
    fs.writeFileSync(source, bytes);
    const sha256 = crypto.createHash('sha256').update(bytes).digest('hex');
    const cache = path.join(temp, 'cache');
    const result = runCli([
      'backend', 'model-cache', 'litert', '--dry-run', '--json',
      '--source', source, '--sha256', sha256, '--size-bytes', String(bytes.length),
      '--cache-dir', cache,
    ]);
    assert.equal(result.status, 0, result.stderr);
    const report = JSON.parse(result.stdout);
    assert.equal(report.schema, 'simplicio.local-litert-model-plan/v1');
    assert.equal(report.status, 'planned');
    assert.equal(report.content_addressed, true);
    assert.equal(report.offline, true);
    assert.equal(report.writes, false);
    assert.match(report.destination, new RegExp(`${sha256}\\.litertlm$`));
    assert.equal(fs.existsSync(cache), false);
  } finally {
    fs.rmSync(temp, { recursive: true, force: true });
  }
});

test('LiteRT model cache installs, verifies tampering, and rolls back only managed content', () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'simplicio-model-cache-'));
  try {
    const source = path.join(temp, 'fixture.litertlm');
    const bytes = Buffer.from('model cache fixture\n');
    fs.writeFileSync(source, bytes);
    const sha256 = crypto.createHash('sha256').update(bytes).digest('hex');
    const cache = path.join(temp, 'cache');
    const install = runCli([
      'backend', 'model-cache', 'litert', '--yes', '--json',
      '--source', source, '--sha256', sha256, '--size-bytes', String(bytes.length),
      '--cache-dir', cache,
    ]);
    assert.equal(install.status, 0, install.stderr);
    const receipt = JSON.parse(install.stdout);
    assert.equal(receipt.schema, 'simplicio.local-litert-model-receipt/v1');
    assert.equal(receipt.status, 'completed');
    assert.equal(fs.readFileSync(receipt.destination, 'utf8'), bytes.toString());
    assert.equal(path.resolve(receipt.destination).startsWith(path.resolve(root)), false);

    const verify = runCli([
      'backend', 'model-cache', 'litert', '--verify', '--json',
      '--sha256', sha256, '--cache-dir', cache,
    ]);
    assert.equal(verify.status, 0, verify.stderr);
    assert.equal(JSON.parse(verify.stdout).status, 'verified');
    fs.writeFileSync(receipt.destination, 'tampered model\n');
    const tampered = runCli([
      'backend', 'model-cache', 'litert', '--verify', '--json',
      '--sha256', sha256, '--cache-dir', cache,
    ]);
    assert.equal(tampered.status, 0, tampered.stderr);
    const failure = JSON.parse(tampered.stdout);
    assert.equal(failure.status, 'failed');
    assert.equal(failure.failure_reason, 'offline-model-integrity-failure');

    fs.writeFileSync(path.join(cache, 'unmanaged.txt'), 'preserve');
    const denied = runCli([
      'backend', 'model-cache', 'litert', '--rollback', '--json',
      '--sha256', sha256, '--cache-dir', cache,
    ]);
    assert.equal(denied.status, 1);
    assert.match(JSON.parse(denied.stdout).failure_reason, /requires explicit --yes/);

    const rollback = runCli([
      'backend', 'model-cache', 'litert', '--rollback', '--yes', '--json',
      '--sha256', sha256, '--cache-dir', cache,
    ]);
    assert.equal(rollback.status, 0, rollback.stderr);
    const report = JSON.parse(rollback.stdout);
    assert.equal(report.schema, 'simplicio.local-litert-model-rollback/v1');
    assert.equal(report.status, 'rolled_back');
    assert.equal(report.writes, true);
    assert.equal(fs.existsSync(receipt.destination), false);
    assert.equal(fs.existsSync(receipt.receipt_path), false);
    assert.equal(fs.readFileSync(path.join(cache, 'unmanaged.txt'), 'utf8'), 'preserve');
  } finally {
    fs.rmSync(temp, { recursive: true, force: true });
  }
});

test('LiteRT model cache rejects mismatched digest without publishing a partial artifact', () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'simplicio-model-fail-'));
  try {
    const source = path.join(temp, 'fixture.litertlm');
    const bytes = Buffer.from('wrong digest\n');
    fs.writeFileSync(source, bytes);
    const digest = '0'.repeat(64);
    const cache = path.join(temp, 'cache');
    const result = runCli([
      'backend', 'model-cache', 'litert', '--yes', '--json',
      '--source', source, '--sha256', digest, '--size-bytes', String(bytes.length),
      '--cache-dir', cache,
    ]);
    assert.equal(result.status, 1);
    assert.equal(JSON.parse(result.stdout).status, 'failed');
    assert.equal(fs.existsSync(path.join(
      cache, 'models', 'sha256', '00', `${digest}.litertlm`,
    )), false);
  } finally {
    fs.rmSync(temp, { recursive: true, force: true });
  }
});
