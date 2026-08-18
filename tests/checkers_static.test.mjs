import test from "node:test"
import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"

test("checkers page exposes playable controls and TurboQuant configuration", async () => {
  const html = await readFile(new URL("../apps/checkers/index.html", import.meta.url), "utf8")
  for (const marker of ["id=\"board\"", "id=\"ai-turn\"", "id=\"api-url\"", "Qwen3.8", "TurboQuant"]) {
    assert.match(html, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")))
  }
})

test("checkers client imports the real rules engine and requests usage metrics", async () => {
  const client = await readFile(new URL("../apps/checkers/checkers.js", import.meta.url), "utf8")
  assert.match(client, /checkers-engine\.mjs/)
  assert.match(client, /prompt_tokens/)
  assert.match(client, /completion_tokens/)
  assert.match(client, /fallback/)
})
