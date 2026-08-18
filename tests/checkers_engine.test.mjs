import test from "node:test"
import assert from "node:assert/strict"

import {
  applyMove,
  COLORS,
  countPieces,
  createInitialBoard,
  findMoveFromText,
  formatMove,
  getLegalMoves,
  indexOfSquare,
} from "../apps/checkers/checkers-engine.mjs"

test("initializes a standard 12 versus 12 board", () => {
  const counts = countPieces(createInitialBoard())
  assert.deepEqual(counts, { white: 12, black: 12 })
  assert.equal(getLegalMoves(createInitialBoard(), COLORS.WHITE).length, 7)
})

test("forces a capture when one exists", () => {
  const board = Array(64).fill(null)
  board[indexOfSquare(5, 0)] = { color: COLORS.WHITE, king: false }
  board[indexOfSquare(4, 1)] = { color: COLORS.BLACK, king: false }
  const moves = getLegalMoves(board, COLORS.WHITE)
  assert.equal(moves.length, 1)
  assert.equal(formatMove(moves[0]), "a3-c5")
  const next = applyMove(board, moves[0])
  assert.equal(countPieces(next).black, 0)
})

test("parses only a legal model move", () => {
  const board = createInitialBoard()
  assert.equal(formatMove(findMoveFromText(board, COLORS.WHITE, '{"move":"c3-d4"}')), "c3-d4")
  assert.equal(findMoveFromText(board, COLORS.WHITE, "a1-h8"), null)
})

test("promotes a man when it reaches the far row", () => {
  const board = Array(64).fill(null)
  board[indexOfSquare(1, 2)] = { color: COLORS.WHITE, king: false }
  const move = findMoveFromText(board, COLORS.WHITE, "c7-b8")
  const next = applyMove(board, move)
  assert.equal(next[indexOfSquare(0, 1)].king, true)
})
