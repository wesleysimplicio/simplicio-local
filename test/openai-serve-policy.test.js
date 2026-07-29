'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const test = require('node:test');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '..');
const script = path.join(root, 'scripts', 'openai_serve.py');

test('direct serve script is paused before dependency import, bind, or upstream contact', () => {
  const result = spawnSync('python3', [script], {
    cwd: root,
    encoding: 'utf8',
    env: { ...process.env, US4_SERVE_PORT: '0' },
  });
  assert.equal(result.status, 78, result.stderr);
  assert.match(result.stderr, /LOCAL_INFERENCE_PAUSED/);
});

test('policy helper needs Runtime admission and a non-empty lease', () => {
  const probe = [
    'import os,sys;',
    `sys.path.insert(0, ${JSON.stringify(path.join(root, 'scripts'))});`,
    'import openai_serve;',
    'print(openai_serve._runtime_admission()[0])',
  ].join('');
  const denied = spawnSync('python3', ['-c', probe], { encoding: 'utf8' });
  assert.equal(denied.status, 0, denied.stderr);
  assert.equal(denied.stdout.trim(), 'False');

  const admitted = spawnSync('python3', ['-c', probe], {
    encoding: 'utf8',
    env: {
      ...process.env,
      US4_LOCAL_INFERENCE: 'enabled',
      US4_RUNTIME_POLICY: 'admitted',
      US4_RUNTIME_LEASE: 'lease-test-only',
    },
  });
  assert.equal(admitted.status, 0, admitted.stderr);
  assert.equal(admitted.stdout.trim(), 'True');
});

test('OpenAI facade exposes actual readiness and proxies completion/stream', () => {
  const probe = `
import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, ${JSON.stringify(path.join(root, 'scripts'))})
import openai_serve as app

class Upstream(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path != '/health':
            self.send_response(404)
            self.end_headers()
            return
        body = b'{}'
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', '0'))
        request = json.loads(self.rfile.read(length))
        if request.get('stream'):
            body = b'data: {\"id\":\"stream\"}\\n\\ndata: [DONE]\\n\\n'
            content_type = 'text/event-stream'
        else:
            body = b'{\"id\":\"completion\",\"object\":\"chat.completion\"}'
            content_type = 'application/json'
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

upstream = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
threading.Thread(target=upstream.serve_forever, daemon=True).start()
app.SETTINGS.chat_backend = 'custom'
app.SETTINGS.chat_upstream_override = f'http://127.0.0.1:{upstream.server_port}'
app.SETTINGS.disable_chat = False
app.SETTINGS.disable_embed = True
app._set_chat_backend_ready(False)
facade = ThreadingHTTPServer(('127.0.0.1', 0), app.Us4Handler)
threading.Thread(target=facade.serve_forever, daemon=True).start()
base = f'http://127.0.0.1:{facade.server_port}'

def call(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(base + path, data=data, headers={'Content-Type': 'application/json'} if data else {})
    return urllib.request.urlopen(request, timeout=5)

try:
    try:
        call('/health')
        raise AssertionError('unready health must return 503')
    except urllib.error.HTTPError as error:
        assert error.code == 503
        payload = json.loads(error.read())
        assert payload['status'] == 'degraded' and payload['ready'] is False
    app._set_chat_backend_ready(True)
    with call('/health') as response:
        assert response.status == 200
        assert json.loads(response.read())['ready'] is True
    with call('/v1/chat/completions', {'model': 'fixture', 'messages': []}) as response:
        assert response.status == 200
        assert json.loads(response.read())['id'] == 'completion'
    with call('/v1/chat/completions', {'model': 'fixture', 'messages': [], 'stream': True}) as response:
        body = response.read().decode()
        assert 'data: {\"id\":\"stream\"}' in body and 'data: [DONE]' in body
finally:
    facade.shutdown()
    facade.server_close()
    upstream.shutdown()
    upstream.server_close()
print('readiness-completion-stream: ok')
`;
  const result = spawnSync('python3', ['-c', probe], { cwd: root, encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.match(result.stdout, /readiness-completion-stream: ok/);
});
