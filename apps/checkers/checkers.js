import {
  applyMove,
  boardToAscii,
  COLORS,
  countPieces,
  createInitialBoard,
  findMoveFromText,
  formatMove,
  gameStatus,
  getLegalMoves,
  rowOf,
  colOf,
  squareName,
} from "./checkers-engine.mjs"

const boardElement = document.querySelector("#board")
const statusElement = document.querySelector("#game-status")
const historyElement = document.querySelector("#move-history")
const metricsElement = document.querySelector("#metrics-last")
const aiButton = document.querySelector("#ai-turn")
const newGameButton = document.querySelector("#new-game")
const autoAiElement = document.querySelector("#auto-ai")
const apiUrlElement = document.querySelector("#api-url")
const modelElement = document.querySelector("#model-id")
const errorElement = document.querySelector("#game-error")

const state = {
  board: createInitialBoard(),
  turn: COLORS.WHITE,
  selected: null,
  history: [],
  pending: false,
  lastMetrics: null,
}

function setError(message = "") {
  errorElement.textContent = message
  errorElement.hidden = !message
}

function selectedMoves() {
  if (state.selected === null) return []
  return getLegalMoves(state.board, state.turn).filter((move) => move.path[0] === state.selected)
}

function render() {
  const legal = getLegalMoves(state.board, state.turn)
  const destinations = new Set(selectedMoves().map((move) => move.path[1]))
  boardElement.replaceChildren()
  for (let index = 0; index < 64; index += 1) {
    const row = rowOf(index)
    const col = colOf(index)
    const square = document.createElement("button")
    square.type = "button"
    square.className = `square ${(row + col) % 2 ? "dark" : "light"}`
    square.dataset.square = String(index)
    square.setAttribute("aria-label", `Casa ${squareName(index)}`)
    if (state.selected === index) square.classList.add("selected")
    if (destinations.has(index)) square.classList.add("legal-target")
    const piece = state.board[index]
    if (piece) {
      const token = document.createElement("span")
      token.className = `piece ${piece.color}${piece.king ? " king" : ""}`
      token.textContent = piece.king ? "♛" : ""
      token.setAttribute("aria-label", `${piece.color === COLORS.WHITE ? "Branca" : "Preta"}${piece.king ? " dama" : " peça"}`)
      square.append(token)
    }
    square.addEventListener("click", () => handleSquare(index))
    boardElement.append(square)
  }

  const pieces = countPieces(state.board)
  const status = gameStatus(state.board, state.turn)
  if (status.over) {
    statusElement.textContent = `Fim de jogo: ${status.winner === COLORS.WHITE ? "brancas" : "pretas"} venceram (${status.reason}).`
  } else {
    statusElement.textContent = `Vez das ${state.turn === COLORS.WHITE ? "brancas" : "pretas"}. ${legal.length} jogada(s) legal(is).`
  }
  document.querySelector("#white-count").textContent = String(pieces.white)
  document.querySelector("#black-count").textContent = String(pieces.black)
  historyElement.replaceChildren(...state.history.map((item, index) => {
    const row = document.createElement("li")
    row.textContent = `${index + 1}. ${item}`
    return row
  }))
  aiButton.disabled = state.pending || state.turn !== COLORS.BLACK || status.over
  aiButton.textContent = state.pending ? "Qwen pensando…" : "Jogar com Qwen"
  if (state.lastMetrics) {
    const metrics = state.lastMetrics
    metricsElement.textContent = metrics.error
      ? `Falha no modelo; fallback local usado: ${metrics.error}`
      : `Última jogada: ${metrics.move} · ${metrics.promptTokens ?? "?"} in / ${metrics.outputTokens ?? "?"} out · ${metrics.elapsedMs.toFixed(0)} ms`
  } else {
    metricsElement.textContent = "Nenhuma chamada ao modelo ainda."
  }
}

function handleSquare(index) {
  if (state.pending || state.turn !== COLORS.WHITE) return
  const piece = state.board[index]
  const moves = selectedMoves()
  const chosen = moves.find((move) => move.path[1] === index)
  if (chosen) {
    state.board = applyMove(state.board, chosen)
    state.history.push(`Brancas: ${formatMove(chosen)}`)
    state.selected = null
    state.turn = COLORS.BLACK
    setError()
    render()
    if (autoAiElement.checked) void requestAiMove()
    return
  }
  if (piece?.color === COLORS.WHITE) {
    state.selected = index
    setError()
    render()
  }
}

function aiPrompt(legalMoves) {
  return [
    "Escolha uma jogada de damas para as pretas.",
    "Responda somente JSON no formato {\"move\":\"a7-b6\"}; não escreva explicações.",
    `Jogadas legais obrigatórias: ${legalMoves.map(formatMove).join(", ")}`,
    "Tabuleiro (maiúsculas são damas; b/B pretas; w/W brancas; . vazio):",
    boardToAscii(state.board),
  ].join("\n")
}

async function requestAiMove() {
  if (state.pending || state.turn !== COLORS.BLACK) return
  const legalMoves = getLegalMoves(state.board, COLORS.BLACK)
  if (!legalMoves.length) return
  state.pending = true
  setError()
  render()
  const started = performance.now()
  let metrics
  try {
    const response = await fetch(apiUrlElement.value.trim(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: modelElement.value.trim(),
        messages: [
          { role: "system", content: "Você é um motor de damas. Siga exatamente o formato pedido." },
          { role: "user", content: aiPrompt(legalMoves) },
        ],
        temperature: 0,
        max_tokens: 24,
        stream: false,
      }),
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const payload = await response.json()
    const content = payload.choices?.[0]?.message?.content || payload.choices?.[0]?.message?.reasoning_content || ""
    const chosen = findMoveFromText(state.board, COLORS.BLACK, content)
    const move = chosen || legalMoves[0]
    metrics = {
      elapsedMs: performance.now() - started,
      promptTokens: payload.usage?.prompt_tokens ?? null,
      outputTokens: payload.usage?.completion_tokens ?? null,
      totalTokens: payload.usage?.total_tokens ?? null,
      move: formatMove(move),
      modelText: content,
      fallback: !chosen,
      timings: payload.timings || null,
    }
    state.board = applyMove(state.board, move)
    state.history.push(`Pretas/Qwen: ${formatMove(move)}${chosen ? "" : " (fallback legal)"}`)
    state.turn = COLORS.WHITE
  } catch (cause) {
    const fallback = legalMoves[0]
    state.board = applyMove(state.board, fallback)
    state.history.push(`Pretas/local: ${formatMove(fallback)} (fallback por erro)`)
    state.turn = COLORS.WHITE
    metrics = { elapsedMs: performance.now() - started, move: formatMove(fallback), error: cause instanceof Error ? cause.message : String(cause) }
    setError(`O endpoint TurboQuant não respondeu; uma jogada legal local manteve a partida funcionando.`)
  } finally {
    state.lastMetrics = metrics
    state.pending = false
    render()
  }
}

newGameButton.addEventListener("click", () => {
  state.board = createInitialBoard()
  state.turn = COLORS.WHITE
  state.selected = null
  state.history = []
  state.lastMetrics = null
  setError()
  render()
})
aiButton.addEventListener("click", () => void requestAiMove())
render()
