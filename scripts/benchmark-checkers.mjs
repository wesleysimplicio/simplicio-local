import { createHash } from "node:crypto"
import { spawn, spawnSync } from "node:child_process"
import { readFileSync } from "node:fs"
import { readFile, stat, writeFile } from "node:fs/promises"
import { dirname, basename, resolve } from "node:path"
import os from "node:os"
import process from "node:process"
import { performance } from "node:perf_hooks"

import {
  applyMove,
  boardToAscii,
  COLORS,
  createInitialBoard,
  findMoveFromText,
  formatMove,
  getLegalMoves,
} from "../apps/checkers/checkers-engine.mjs"

const DEFAULT_SERVER = "/tmp/simplicio-local-turboquant-real2/backends/atomic-llama-cpp-turboquant/b10269-1.4.0/build/bin/llama-server"
const DEFAULT_MODEL = "/tmp/simplicio-qwen38-test/Qwen3.8-27B-Q4_K_M.gguf"
const DEFAULT_RECEIPT = "/tmp/simplicio-local-turboquant-real2/backends/atomic-llama-cpp-turboquant/current.json"
const MODEL_SHA256 = "7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169"
const DEFAULT_API = "http://127.0.0.1:18181/v1/chat/completions"

function argsFrom(argv) {
  const values = {}
  for (let index = 0; index < argv.length; index += 1) {
    if (!argv[index].startsWith("--")) continue
    const key = argv[index].slice(2)
    values[key] = argv[index + 1]?.startsWith("--") || argv[index + 1] === undefined ? true : argv[++index]
  }
  return values
}

const options = argsFrom(process.argv.slice(2))
const serverPath = String(options["server-path"] || process.env.SIMPLICIO_LOCAL_LLAMA_SERVER || DEFAULT_SERVER)
const modelPath = String(options["model-path"] || process.env.SIMPLICIO_LOCAL_QWEN_MODEL || DEFAULT_MODEL)
const apiUrl = String(options["server-url"] || process.env.SIMPLICIO_LOCAL_CHECKERS_API || DEFAULT_API)
const repetitions = Math.max(1, Number(options.repetitions || process.env.SIMPLICIO_LOCAL_CHECKERS_REPETITIONS || 3))
const contextSize = Number(options.context || 512)
const threads = Number(options.threads || 9)
const port = Number(new URL(apiUrl).port || 18181)
const externalServerPid = Number(options["server-pid"] || process.env.SIMPLICIO_LOCAL_LLAMA_SERVER_PID || 0) || null
const outputJson = resolve(String(options.output || "docs/benchmarks/checkers-qwen38-turboquant-2026-08-18.json"))
const outputMarkdown = resolve(String(options.report || "docs/benchmarks/checkers-qwen38-turboquant-2026-08-18.md"))

const sleep = (ms) => new Promise((resolvePromise) => setTimeout(resolvePromise, ms))

function parseProcStatus(text) {
  const values = {}
  for (const line of text.split("\n")) {
    const match = /^(VmRSS|VmHWM|VmPeak|VmSwap|voluntary_ctxt_switches|nonvoluntary_ctxt_switches):\s+(\d+)/.exec(line)
    if (match) values[match[1]] = Number(match[2]) * (match[1].startsWith("Vm") ? 1024 : 1)
  }
  return values
}

function parseProcIo(text) {
  const values = {}
  for (const line of text.split("\n")) {
    const match = /^(read_bytes|write_bytes|syscr|syscw):\s+(\d+)/.exec(line)
    if (match) values[match[1]] = Number(match[2])
  }
  return values
}

function parseProcStat(text) {
  const closeParen = text.lastIndexOf(")")
  if (closeParen < 0) return {}
  const fields = text.slice(closeParen + 2).trim().split(/\s+/)
  return {
    minflt: Number(fields[7]),
    majflt: Number(fields[9]),
    utime_ticks: Number(fields[11]),
    stime_ticks: Number(fields[12]),
  }
}

async function readProcessMetrics(pid) {
  if (!pid) return null
  try {
    const [status, io, statText] = await Promise.all([
      readFile(`/proc/${pid}/status`, "utf8"),
      readFile(`/proc/${pid}/io`, "utf8"),
      readFile(`/proc/${pid}/stat`, "utf8"),
    ])
    return { pid, ...parseProcStatus(status), ...parseProcIo(io), ...parseProcStat(statText) }
  } catch {
    return null
  }
}

function readMeminfo() {
  try {
    const text = readFileSync("/proc/meminfo", "utf8")
    const values = {}
    for (const line of text.split("\n")) {
      const match = /^(MemTotal|MemAvailable|SwapTotal|SwapFree):\s+(\d+) kB/.exec(line)
      if (match) values[match[1]] = Number(match[2]) * 1024
    }
    return values
  } catch {
    return {}
  }
}

async function sha256(filePath) {
  const digest = createHash("sha256")
  const data = await readFile(filePath)
  digest.update(data)
  return digest.digest("hex")
}

async function requestJson(url, body) {
  const started = performance.now()
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  const raw = await response.text()
  let payload
  try {
    payload = JSON.parse(raw)
  } catch (cause) {
    throw new Error(`invalid JSON from llama-server (${response.status}): ${cause.message}`)
  }
  if (!response.ok) throw new Error(`llama-server HTTP ${response.status}: ${raw.slice(0, 400)}`)
  return { payload, elapsedMs: performance.now() - started }
}

async function waitForHealth(url, child, timeoutMs) {
  const healthUrl = new URL("/health", url).href
  const started = performance.now()
  while (performance.now() - started < timeoutMs) {
    if (child && child.exitCode !== null) throw new Error(`llama-server exited with ${child.exitCode}`)
    try {
      const response = await fetch(healthUrl)
      if (response.ok) return performance.now() - started
    } catch { /* startup is expected to reject until the model is ready */ }
    await sleep(500)
  }
  throw new Error(`llama-server did not become healthy within ${timeoutMs / 1000}s`)
}

function promptFor(board, legalMoves) {
  return [
    "Escolha uma jogada para as pretas em uma partida de damas.",
    "Responda somente JSON válido no formato {\"move\":\"a7-b6\"}; não inclua explicações.",
    `Jogadas legais obrigatórias: ${legalMoves.map(formatMove).join(", ")}`,
    "Tabuleiro: b/B = pretas, w/W = brancas, ponto = vazio.",
    boardToAscii(board),
  ].join("\n")
}

function numberOrNull(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

function responseMetrics(result, board, legalMoves) {
  const payload = result.payload
  const content = payload.choices?.[0]?.message?.content || payload.choices?.[0]?.message?.reasoning_content || ""
  const chosen = findMoveFromText(board, COLORS.BLACK, content)
  const move = chosen || legalMoves[0]
  const usage = payload.usage || {}
  const timing = payload.timings || {}
  const promptMs = numberOrNull(timing.prompt_ms)
  const decodeMs = numberOrNull(timing.predicted_ms ?? timing.decode_ms)
  const outputTokens = numberOrNull(usage.completion_tokens)
  return {
    request_ms: result.elapsedMs,
    prompt_tokens_in: numberOrNull(usage.prompt_tokens),
    output_tokens_out: outputTokens,
    total_tokens: numberOrNull(usage.total_tokens),
    reasoning_tokens: numberOrNull(usage.completion_tokens_details?.reasoning_tokens),
    cache_read_tokens: numberOrNull(usage.prompt_tokens_details?.cached_tokens),
    ttft_ms: promptMs,
    decode_ms: decodeMs,
    prompt_tokens_per_second: promptMs && usage.prompt_tokens ? usage.prompt_tokens / (promptMs / 1000) : null,
    output_tokens_per_second: decodeMs && outputTokens ? outputTokens / (decodeMs / 1000) : null,
    server_total_ms: numberOrNull(timing.total_ms),
    move: formatMove(move),
    model_output: String(content).slice(0, 500),
    legal_move_from_model: Boolean(chosen),
    fallback: !chosen,
    timings_raw: timing,
  }
}

function median(values) {
  const numbers = values.filter((value) => typeof value === "number" && Number.isFinite(value)).sort((a, b) => a - b)
  if (!numbers.length) return null
  const middle = Math.floor(numbers.length / 2)
  return numbers.length % 2 ? numbers[middle] : (numbers[middle - 1] + numbers[middle]) / 2
}

function sumNullable(values) {
  return values.every((value) => typeof value === "number" && Number.isFinite(value))
    ? values.reduce((sum, value) => sum + value, 0)
    : null
}

function delta(after, before, key) {
  return after?.[key] != null && before?.[key] != null ? after[key] - before[key] : null
}

function aggregateProcess(samples, before, after) {
  const valid = samples.filter(Boolean)
  const max = (key) => valid.length ? Math.max(...valid.map((sample) => sample[key] || 0)) : null
  return {
    peak_rss_bytes_observed: max("VmHWM"),
    peak_vm_peak_bytes_observed: max("VmPeak"),
    swap_bytes_at_last_sample: after?.VmSwap ?? null,
    read_bytes_delta: delta(after, before, "read_bytes"),
    write_bytes_delta: delta(after, before, "write_bytes"),
    minor_page_faults_delta: delta(after, before, "minflt"),
    major_page_faults_delta: delta(after, before, "majflt"),
    voluntary_context_switches_delta: delta(after, before, "voluntary_ctxt_switches"),
    nonvoluntary_context_switches_delta: delta(after, before, "nonvoluntary_ctxt_switches"),
    cpu_time_ms_delta: after && before ? ((after.utime_ticks - before.utime_ticks + after.stime_ticks - before.stime_ticks) * 1000 / 100) : null,
    sampling: valid.length ? "kernel /proc samples at health and request boundaries" : "unavailable: server was not a local child process",
  }
}

function markdownNumber(value, digits = 2) {
  return value == null ? "—" : Number(value).toFixed(digits)
}

function markdown(report) {
  const calls = report.inference.measured_calls
  const rows = calls.map((call, index) => `| ${index + 1} | ${markdownNumber(call.request_ms)} | ${call.prompt_tokens_in ?? "—"} | ${call.cache_read_tokens ?? "—"} | ${call.output_tokens_out ?? "—"} | ${call.total_tokens ?? "—"} | ${markdownNumber(call.ttft_ms)} | ${markdownNumber(call.decode_ms)} | ${markdownNumber(call.prompt_tokens_per_second)} | ${markdownNumber(call.output_tokens_per_second)} | ${call.move} | ${call.legal_move_from_model ? "sim" : "não"} | ${call.fallback ? "sim" : "não"} |`).join("\n")
  const inputSum = sumNullable(calls.map((call) => call.prompt_tokens_in))
  const outputSum = sumNullable(calls.map((call) => call.output_tokens_out))
  const totalSum = sumNullable(calls.map((call) => call.total_tokens))
  return `# Benchmark: jogo de damas com Qwen3.8 + llama.cpp TurboQuant

> Captura real em ${report.captured_at}. Os números abaixo foram medidos; campos sem exposição do provedor permanecem como —.

## Resultado

- Status: **${report.status}**
- Jogo: regras locais executadas e ${calls.length} jogada(s) preta(s) solicitada(s) ao modelo.
- Jogadas do modelo legais: **${calls.filter((call) => call.legal_move_from_model).length}/${calls.length}**.
- Fallback local: **${calls.filter((call) => call.fallback).length}/${calls.length}**.
- Todos os gates do motor e da página foram executados separadamente.

## Ambiente

| Campo | Valor |
|---|---|
| Host | ${report.host.platform} / ${report.host.arch} |
| CPU | ${report.host.cpu} |
| CPUs lógicas | ${report.host.logical_cpus} |
| RAM total | ${(report.host.ram_total_bytes / 1024 ** 3).toFixed(2)} GiB |
| RAM disponível antes | ${(report.host.ram_available_before_bytes / 1024 ** 3).toFixed(2)} GiB |
| Swap total | ${(report.host.swap_total_bytes / 1024 ** 3).toFixed(2)} GiB |
| Node | ${report.host.node} |
| Simplicio | ${report.tooling.simplicio_version} (${report.tooling.simplicio_binary_sha256}) |

## Backend e modelo

| Campo | Valor |
|---|---|
| Backend efetivo | llama-cpp-turboquant |
| Release Atomic | ${report.backend.release} |
| Asset | ${report.backend.asset} |
| llama-server | ${report.backend.server_version} |
| SHA-256 do executável | ${report.backend.executable_sha256} |
| Modelo | ${report.model.file} |
| Quantização | Q4_K_M |
| Tamanho | ${(report.model.size_bytes / 1024 ** 3).toFixed(2)} GiB |
| SHA-256 do modelo | ${report.model.sha256} |
| Contexto | ${report.configuration.context_size} |
| Threads / batch | ${report.configuration.threads} / ${report.configuration.threads_batch} |
| KV K / V | ${report.configuration.cache_type_k} / ${report.configuration.cache_type_v} |
| Flash Attention | ${report.configuration.flash_attention} |
| KV unified | ${report.configuration.kv_unified} |

## Latência e tokens do Qwen

Tempo de prontidão inclui o carregamento do modelo pelo servidor. A tabela é a
agregação medida, sem contar a chamada de aquecimento.

| Rep. | Request ms | Tokens in | Cache read | Tokens out | Tokens total | TTFT/prompt ms | Decode ms | In tok/s | Out tok/s | Jogada | Legal | Fallback |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|:---:|:---:|
${rows}

| Agregado | Valor |
|---|---:|
| Prontidão do llama-server | ${markdownNumber(report.inference.server_ready_ms)} ms |
| Aquecimento | ${markdownNumber(report.inference.warmup.request_ms)} ms |
| Requests medidos | ${calls.length} |
| Soma tokens in | ${inputSum ?? "—"} |
| Soma cache read | ${sumNullable(calls.map((call) => call.cache_read_tokens)) ?? "—"} |
| Soma tokens out | ${outputSum ?? "—"} |
| Soma tokens total | ${totalSum ?? "—"} |
| Mediana request | ${markdownNumber(median(calls.map((call) => call.request_ms)))} ms |
| Mediana TTFT/prompt | ${markdownNumber(median(calls.map((call) => call.ttft_ms)))} ms |
| Mediana decode | ${markdownNumber(median(calls.map((call) => call.decode_ms)))} ms |
| Mediana input tok/s | ${markdownNumber(median(calls.map((call) => call.prompt_tokens_per_second)))} |
| Mediana output tok/s | ${markdownNumber(median(calls.map((call) => call.output_tokens_per_second)))} |

## Recursos do processo llama-server

| Métrica | Valor |
|---|---:|
| Pico RSS observado | ${report.process.peak_rss_bytes_observed == null ? "—" : `${(report.process.peak_rss_bytes_observed / 1024 ** 3).toFixed(2)} GiB`} |
| Pico virtual observado | ${report.process.peak_vm_peak_bytes_observed == null ? "—" : `${(report.process.peak_vm_peak_bytes_observed / 1024 ** 3).toFixed(2)} GiB`} |
| Swap no último sample | ${report.process.swap_bytes_at_last_sample == null ? "—" : `${(report.process.swap_bytes_at_last_sample / 1024 ** 2).toFixed(2)} MiB`} |
| Read bytes delta | ${report.process.read_bytes_delta == null ? "—" : `${(report.process.read_bytes_delta / 1024 ** 2).toFixed(2)} MiB`} |
| Write bytes delta | ${report.process.write_bytes_delta == null ? "—" : `${(report.process.write_bytes_delta / 1024 ** 2).toFixed(2)} MiB`} |
| Minor / major page faults | ${report.process.minor_page_faults_delta ?? "—"} / ${report.process.major_page_faults_delta ?? "—"} |
| CPU time delta | ${report.process.cpu_time_ms_delta == null ? "—" : `${report.process.cpu_time_ms_delta.toFixed(0)} ms`} |
| Medição térmica/energia | — (sem sensor/medidor calibrado disponível) |

## Gates

- Motor: node --test tests/checkers_engine.test.mjs tests/checkers_static.test.mjs.
- Sintaxe: node --check apps/checkers/checkers.js.
- Página: arquivos estáticos servidos por HTTP; teste de integridade dos controles concluído.
- O download do Chromium do Playwright foi tentado, mas o CDN respondeu erro de certificado/502; portanto não há claim de browser E2E nesta captura.

## Reprodutibilidade

\`\`\`bash
python3 -m http.server 4173 --directory apps/checkers
node scripts/benchmark-checkers.mjs --repetitions 3
\`\`\`

Flags usadas no servidor: --cache-type-k turbo3 --cache-type-v turbo3
--flash-attn auto --kv-unified --ctx-size ${report.configuration.context_size}
--threads ${report.configuration.threads} --threads-batch ${report.configuration.threads_batch}
--parallel 1 --reasoning off --metrics --no-webui.

## Limitações

- O host é CPU-only; esta captura prova integração real com o fork Atomic e o
  caminho TurboQuant em CPU, não throughput GPU.
- Tokens de raciocínio, cache hit, rede física e energia só são publicados se o
  servidor os expuser ou houver medidor apropriado; não foram inferidos.
- A jogada é considerada do Qwen somente quando a saída textual corresponde a
  uma jogada legal do estado atual. Fallbacks ficam explícitos.
`
}

async function loadReceipt() {
  try { return JSON.parse(await readFile(String(options.receipt || process.env.SIMPLICIO_LOCAL_TURBOQUANT_RECEIPT || DEFAULT_RECEIPT), "utf8")) } catch { return {} }
}

async function main() {
  const modelStat = await stat(modelPath)
  const backendReceipt = await loadReceipt()
  const executableSha = await sha256(serverPath)
  const versionResult = spawnSync(serverPath, ["--version"], { encoding: "utf8" })
  const versionOutput = [versionResult.stdout, versionResult.stderr].filter(Boolean).join(" ").trim().replace(/\s+/g, " ")
  const memoryBefore = readMeminfo()
  const child = options["server-url"] ? null : spawn(serverPath, [
    "--model", modelPath, "--host", "127.0.0.1", "--port", String(port), "--no-webui", "--metrics",
    "--load-mode", "mmap", "--ctx-size", String(contextSize), "--parallel", "1", "--threads", String(threads),
    "--threads-batch", String(threads), "--reasoning", "off", "--cache-type-k", "turbo3",
    "--cache-type-v", "turbo3", "--flash-attn", "auto", "-kvu", "--cors-origins", "*",
  ], { stdio: ["ignore", "ignore", "pipe"] })
  let serverStderr = ""
  child?.stderr?.on("data", (chunk) => { serverStderr = `${serverStderr}${chunk}`.slice(-4000) })
  const start = performance.now()
  const serverReadyMs = await waitForHealth(apiUrl, child, 600_000)
  const serverPid = child?.pid || externalServerPid
  const processBefore = await readProcessMetrics(serverPid)
  const warmup = await requestJson(apiUrl, {
    model: "qwen3.8-27b-q4-turboquant",
    messages: [{ role: "user", content: "Responda somente READY." }],
    temperature: 0,
    max_tokens: 2,
    stream: false,
  })
  const samples = [await readProcessMetrics(serverPid)]
  let board = createInitialBoard()
  const measured = []
  const opening = getLegalMoves(board, COLORS.WHITE)[0]
  board = applyMove(board, opening)
  for (let index = 0; index < repetitions; index += 1) {
    const legalMoves = getLegalMoves(board, COLORS.BLACK)
    if (!legalMoves.length) break
    const result = await requestJson(apiUrl, {
      model: "qwen3.8-27b-q4-turboquant",
      messages: [
        { role: "system", content: "Você é um motor de damas. Respeite exatamente o JSON solicitado." },
        { role: "user", content: promptFor(board, legalMoves) },
      ],
      temperature: 0,
      max_tokens: 24,
      stream: false,
    })
    const call = responseMetrics(result, board, legalMoves)
    measured.push(call)
    board = applyMove(board, findMoveFromText(board, COLORS.BLACK, call.model_output) || legalMoves[0])
    samples.push(await readProcessMetrics(serverPid))
    const whiteMoves = getLegalMoves(board, COLORS.WHITE)
    if (!whiteMoves.length) break
    board = applyMove(board, whiteMoves[0])
    samples.push(await readProcessMetrics(serverPid))
  }
  const processAfter = await readProcessMetrics(serverPid)
  if (child) {
    child.kill("SIGTERM")
    await new Promise((resolvePromise) => child.once("exit", resolvePromise))
  }

  const report = {
    schema: "simplicio.local.checkers-benchmark/v1",
    status: measured.length === repetitions ? "captured" : "captured_partial",
    captured_at: new Date().toISOString(),
    repository: "wesleysimplicio/simplicio-local",
    tooling: { simplicio_version: "3.8.13", simplicio_binary_sha256: "6df309002e6e1243668de64d696ec22b8bffa42cd5b9d103a0e06269ef1e6a43" },
    host: {
      platform: os.platform(), arch: os.arch(), cpu: os.cpus()[0]?.model || null, logical_cpus: os.cpus().length,
      node: process.version, ram_total_bytes: os.totalmem(), ram_available_before_bytes: memoryBefore.MemAvailable || os.freemem(),
      swap_total_bytes: memoryBefore.SwapTotal || 0, swap_free_before_bytes: memoryBefore.SwapFree || 0,
    },
    backend: {
      id: "llama-cpp-turboquant", repository: backendReceipt.repository || "AtomicBot-ai/atomic-llama-cpp-turboquant",
      release: backendReceipt.tag || "b10269-1.4.0", asset: backendReceipt.asset || "llama-turboquant-linux-x64-vulkan.tar.gz",
      archive_sha256: backendReceipt.archive_sha256 || null, server_version: versionOutput, executable_sha256: executableSha,
    },
    model: { id: "qwen3.8-27b-q4", file: basename(modelPath), size_bytes: modelStat.size, sha256: MODEL_SHA256, sha256_source: "previous real-model provider receipt; not recomputed in this run" },
    configuration: { context_size: contextSize, threads, threads_batch: threads, parallel: 1, cache_type_k: "turbo3", cache_type_v: "turbo3", flash_attention: "auto", kv_unified: true, reasoning: "off" },
    inference: { server_ready_ms: serverReadyMs, measured_from_process_start_ms: performance.now() - start, warmup: { request_ms: warmup.elapsedMs, usage: warmup.payload.usage || null, timings: warmup.payload.timings || null }, measured_calls: measured },
    process: aggregateProcess(samples, processBefore, processAfter),
    notes: ["A página standalone de damas usa o mesmo contrato OpenAI-compatible testado aqui.", "O relatório não conta warmup na tabela de chamadas medidas.", serverStderr ? `stderr_tail=${serverStderr}` : "sem stderr de erro no encerramento"],
  }
  await writeFile(outputJson, `${JSON.stringify(report, null, 2)}\n`, "utf8")
  await writeFile(outputMarkdown, markdown(report), "utf8")
  console.log(JSON.stringify({ outputJson, outputMarkdown, status: report.status, calls: measured.length, serverReadyMs, measured }, null, 2))
}

main().catch((cause) => {
  console.error(cause.stack || cause)
  process.exitCode = 1
})
