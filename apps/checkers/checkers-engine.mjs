export const BOARD_SIZE = 8
export const COLORS = Object.freeze({ WHITE: "white", BLACK: "black" })

const FILES = "abcdefgh"

export function indexOfSquare(row, col) {
  return row * BOARD_SIZE + col
}

export function rowOf(index) {
  return Math.floor(index / BOARD_SIZE)
}

export function colOf(index) {
  return index % BOARD_SIZE
}

export function isPlayable(row, col) {
  return row >= 0 && row < BOARD_SIZE && col >= 0 && col < BOARD_SIZE && (row + col) % 2 === 1
}

export function squareName(index) {
  return `${FILES[colOf(index)]}${BOARD_SIZE - rowOf(index)}`
}

export function parseSquare(value) {
  const match = /^([a-h])([1-8])$/i.exec(String(value).trim())
  if (!match) return null
  const col = FILES.indexOf(match[1].toLowerCase())
  const row = BOARD_SIZE - Number(match[2])
  return isPlayable(row, col) ? indexOfSquare(row, col) : null
}

export function createInitialBoard() {
  const board = Array(BOARD_SIZE * BOARD_SIZE).fill(null)
  for (let row = 0; row < BOARD_SIZE; row += 1) {
    for (let col = 0; col < BOARD_SIZE; col += 1) {
      if (!isPlayable(row, col)) continue
      if (row < 3) board[indexOfSquare(row, col)] = { color: COLORS.BLACK, king: false }
      if (row > 4) board[indexOfSquare(row, col)] = { color: COLORS.WHITE, king: false }
    }
  }
  return board
}

export function cloneBoard(board) {
  return board.map((piece) => piece && { ...piece })
}

function directionsFor(piece) {
  const forward = piece.color === COLORS.BLACK ? 1 : -1
  if (piece.king) return [[-1, -1], [-1, 1], [1, -1], [1, 1]]
  return [[forward, -1], [forward, 1]]
}

function opponentOf(color) {
  return color === COLORS.WHITE ? COLORS.BLACK : COLORS.WHITE
}

function promotionRow(color) {
  return color === COLORS.WHITE ? 0 : BOARD_SIZE - 1
}

function singleCaptures(board, current, piece) {
  const row = rowOf(current)
  const col = colOf(current)
  return directionsFor(piece).flatMap(([dr, dc]) => {
    const jumpedRow = row + dr
    const jumpedCol = col + dc
    const landingRow = row + dr * 2
    const landingCol = col + dc * 2
    if (!isPlayable(landingRow, landingCol)) return []
    const jumped = board[indexOfSquare(jumpedRow, jumpedCol)]
    const landing = indexOfSquare(landingRow, landingCol)
    if (!jumped || jumped.color !== opponentOf(piece.color) || board[landing]) return []
    return [{ landing, captured: indexOfSquare(jumpedRow, jumpedCol) }]
  })
}

function exploreCaptures(board, current, piece, path, captures, output) {
  const continuations = singleCaptures(board, current, piece)
  if (!continuations.length) {
    if (captures.length) output.push({ path, captures })
    return
  }

  for (const continuation of continuations) {
    const nextBoard = cloneBoard(board)
    nextBoard[current] = null
    nextBoard[continuation.captured] = null
    const landingRow = rowOf(continuation.landing)
    const promoted = !piece.king && landingRow === promotionRow(piece.color)
    const nextPiece = { ...piece, king: piece.king || promoted }
    nextBoard[continuation.landing] = nextPiece
    const nextPath = [...path, continuation.landing]
    const nextCaptures = [...captures, continuation.captured]

    // A man stops after the jump that promotes it in American checkers.
    if (promoted) output.push({ path: nextPath, captures: nextCaptures })
    else exploreCaptures(nextBoard, continuation.landing, nextPiece, nextPath, nextCaptures, output)
  }
}

function captureMoves(board, color) {
  const moves = []
  board.forEach((piece, start) => {
    if (!piece || piece.color !== color) return
    exploreCaptures(board, start, piece, [start], [], moves)
  })
  return moves
}

function quietMoves(board, color) {
  const moves = []
  board.forEach((piece, start) => {
    if (!piece || piece.color !== color) return
    const row = rowOf(start)
    const col = colOf(start)
    for (const [dr, dc] of directionsFor(piece)) {
      const landingRow = row + dr
      const landingCol = col + dc
      if (!isPlayable(landingRow, landingCol)) continue
      const landing = indexOfSquare(landingRow, landingCol)
      if (!board[landing]) moves.push({ path: [start, landing], captures: [] })
    }
  })
  return moves
}

export function getLegalMoves(board, color) {
  const captures = captureMoves(board, color)
  return captures.length ? captures : quietMoves(board, color)
}

export function moveKey(move) {
  return move.path.join(">")
}

export function formatMove(move) {
  return move.path.map(squareName).join("-")
}

export function findMoveFromText(board, color, text) {
  const normalized = String(text).toLowerCase().replace(/[→–—]/g, "-")
  const squares = [...normalized.matchAll(/[a-h][1-8]/g)].map((match) => parseSquare(match[0]))
  if (squares.some((square) => square === null) || squares.length < 2) return null
  const wanted = squares.join(">")
  return getLegalMoves(board, color).find((move) => moveKey(move) === wanted) || null
}

export function applyMove(board, move) {
  const piece = board[move.path[0]]
  if (!piece) throw new Error("cannot move an empty square")
  const legal = getLegalMoves(board, piece.color).find((candidate) => moveKey(candidate) === moveKey(move))
  if (!legal) throw new Error(`illegal move: ${formatMove(move)}`)

  const next = cloneBoard(board)
  const moving = { ...piece }
  next[legal.path[0]] = null
  for (let step = 1; step < legal.path.length; step += 1) {
    const from = legal.path[step - 1]
    const to = legal.path[step]
    if (Math.abs(rowOf(to) - rowOf(from)) === 2) {
      next[indexOfSquare((rowOf(from) + rowOf(to)) / 2, (colOf(from) + colOf(to)) / 2)] = null
    }
  }
  if (rowOf(legal.path.at(-1)) === promotionRow(moving.color)) moving.king = true
  next[legal.path.at(-1)] = moving
  return next
}

export function countPieces(board) {
  return board.reduce((counts, piece) => {
    if (piece) counts[piece.color] += 1
    return counts
  }, { [COLORS.WHITE]: 0, [COLORS.BLACK]: 0 })
}

export function gameStatus(board, turn) {
  const pieces = countPieces(board)
  if (!pieces.white) return { over: true, winner: COLORS.BLACK, reason: "all pieces captured" }
  if (!pieces.black) return { over: true, winner: COLORS.WHITE, reason: "all pieces captured" }
  if (!getLegalMoves(board, turn).length) return { over: true, winner: opponentOf(turn), reason: "no legal moves" }
  return { over: false, winner: null, reason: null }
}

export function boardToAscii(board) {
  return Array.from({ length: BOARD_SIZE }, (_, row) => {
    const cells = Array.from({ length: BOARD_SIZE }, (_, col) => {
      if (!isPlayable(row, col)) return " "
      const piece = board[indexOfSquare(row, col)]
      if (!piece) return "."
      return piece.color === COLORS.WHITE ? (piece.king ? "W" : "w") : (piece.king ? "B" : "b")
    })
    return `${BOARD_SIZE - row} ${cells.join(" ")}`
  }).join("\n") + "\n  a b c d e f g h"
}
