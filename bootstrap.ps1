<#
.SYNOPSIS
  Agentic Starter installer/upgrader (Windows native / PowerShell 5.1+ / pwsh 7+).

.DESCRIPTION
  Mirror of bootstrap.sh:
    1. Auto-detects PRODUCT_NAME (cwd basename), DOMAIN ("generico"),
       TEAM ("Plataforma"), STACK (Node, .NET, Python, Go, Rust, Flutter,
       PHP/Laravel, Ruby, Elixir, Kotlin/Java).
       INIT.md refines TEAM/DOMAIN with the human afterwards.
    2. Asks only TWO questions:
        - Append recommended ignore entries to .gitignore? (y/N)
        - Which CLI/LLM should run INIT.md?
    3. Substitutes <PRODUCT_NAME>/<TEAM>/<DOMAIN>/<STACK> ONLY inside
       starter-managed paths (.specs/, .agents/, .skills/, .claude/,
       .codex/, .github/copilot*, .github/workflows/{ci,dod}.yml,
       plus root AGENTS.md/CLAUDE.md/INIT.md/README*.md ONLY if those
       files actually contain a placeholder).
    4. NEVER overwrites pre-existing user files (.razor, .cs, .ts, .py,
       package.json, README.md, AGENTS.md, CLAUDE.md, INIT.md, .gitignore).
       Existing instruction files are flagged in .starter-meta.json so
       INIT.md can read them and improve in place (essence preserved).
    5. Hands off to the chosen CLI/LLM to execute INIT.md.

.EXAMPLE
  PS> .\bootstrap.ps1
  PS> .\bootstrap.ps1 -NonInteractive -Cli claude -AppendGitignore yes
#>
[CmdletBinding()]
param(
  [switch]$NonInteractive,
  [string]$Cli              = "",
  [ValidateSet("yes","no","")]
  [string]$AppendGitignore  = ""
)

$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# auto-detect stack
# ---------------------------------------------------------------------------
function Detect-Stack {
  if (Test-Path "package.json") {
    $pkg = Get-Content "package.json" -Raw
    if     ($pkg -match '"next"')                      { return "next-ts" }
    elseif ($pkg -match '"react"')                     { return "react-ts" }
    elseif ($pkg -match '"vue"')                       { return "vue-ts" }
    elseif ($pkg -match '"@nestjs/core"|"nestjs"')     { return "nestjs" }
    elseif ($pkg -match '"express"')                   { return "node-express" }
    else                                               { return "node-ts" }
  }
  if (Get-ChildItem -Filter "*.csproj" -File -ErrorAction SilentlyContinue) { return "dotnet" }
  if (Get-ChildItem -Filter "*.sln"    -File -ErrorAction SilentlyContinue) { return "dotnet" }
  if ((Test-Path "pyproject.toml") -or (Test-Path "requirements.txt")) {
    $py = ""
    if (Test-Path "pyproject.toml")    { $py += (Get-Content "pyproject.toml" -Raw) }
    if (Test-Path "requirements.txt")  { $py += (Get-Content "requirements.txt" -Raw) }
    if     ($py -match '(?i)django')  { return "python-django" }
    elseif ($py -match '(?i)fastapi') { return "python-fastapi" }
    elseif ($py -match '(?i)flask')   { return "python-flask" }
    else                              { return "python" }
  }
  if (Test-Path "go.mod")           { return "go" }
  if (Test-Path "Cargo.toml")       { return "rust" }
  if (Test-Path "pubspec.yaml")     { return "flutter" }
  if (Test-Path "composer.json") {
    if ((Get-Content "composer.json" -Raw) -match "laravel/framework") { return "laravel" }
    return "php"
  }
  if (Test-Path "Gemfile")          { return "ruby" }
  if (Test-Path "mix.exs")          { return "elixir" }
  if (Test-Path "build.gradle.kts") { return "kotlin-gradle" }
  if (Test-Path "build.gradle")     { return "java-gradle" }
  if (Test-Path "pom.xml")          { return "java-maven" }
  return "unknown"
}

$ProductName = (Get-Item -Path ".").Name
$Team        = "Plataforma"
$Domain      = "generico"
$Stack       = Detect-Stack

Write-Host "=========================================="
Write-Host "  Agentic Starter - Bootstrap (PowerShell)"
Write-Host "=========================================="
Write-Host ""
Write-Host "Auto-detected (INIT.md will refine TEAM/DOMAIN with you):"
Write-Host "  PRODUCT_NAME: $ProductName"
Write-Host "  TEAM:         $Team"
Write-Host "  DOMAIN:       $Domain"
Write-Host "  STACK:        $Stack"
Write-Host ""

# ---------------------------------------------------------------------------
# detect existing instruction files (DO NOT overwrite — flag for INIT.md)
# ---------------------------------------------------------------------------
$ExistingInstructionFiles = @()
$candidates = @("AGENTS.md","CLAUDE.md","INIT.md",".github/copilot-instructions.md")
foreach ($f in $candidates) {
  if (Test-Path $f) {
    $content = Get-Content $f -Raw -ErrorAction SilentlyContinue
    if ($content -and $content -notmatch 'Agentic Starter|<PRODUCT_NAME>|<STACK>') {
      $ExistingInstructionFiles += $f
    }
  }
}

if ($ExistingInstructionFiles.Count -gt 0) {
  Write-Host "Detected pre-existing instruction files (will be preserved):"
  foreach ($f in $ExistingInstructionFiles) { Write-Host "  - $f" }
  Write-Host "  -> INIT.md will READ them and IMPROVE in place (essence preserved)."
  Write-Host ""
}

# ---------------------------------------------------------------------------
# substitute placeholders ONLY in starter-managed paths
# ---------------------------------------------------------------------------
$StarterDirs = @(".specs",".agents",".skills",".claude",".codex")
$StarterGithubPatterns = @(
  ".github/copilot-instructions.md",
  ".github/copilot",
  ".github/PULL_REQUEST_TEMPLATE.md",
  ".github/ISSUE_TEMPLATE",
  ".github/workflows/ci.yml",
  ".github/workflows/dod.yml"
)
$StarterRootFiles = @(
  "AGENTS.md","CLAUDE.md","INIT.md","_BOOTSTRAP.md",
  "README.md","README.pt-BR.md",
  "playwright.config.ts"
)

$Touched = 0

function Substitute-InFile($path) {
  if (-not (Test-Path $path -PathType Leaf)) { return }
  try {
    $bytes = [System.IO.File]::ReadAllBytes($path)
    if ($bytes.Length -eq 0) { return }
    $head = if ($bytes.Length -gt 8192) { $bytes[0..8191] } else { $bytes }
    if ($head -contains 0) { return }
    $content = [System.IO.Text.Encoding]::UTF8.GetString($bytes)
    if ($content -notmatch '<PRODUCT_NAME>|<TEAM>|<DOMAIN>|<STACK>') { return }
    $orig = $content
    $content = $content.Replace("<PRODUCT_NAME>", $script:ProductName)
    $content = $content.Replace("<TEAM>",         $script:Team)
    $content = $content.Replace("<DOMAIN>",       $script:Domain)
    $content = $content.Replace("<STACK>",        $script:Stack)
    if ($content -ne $orig) {
      [System.IO.File]::WriteAllText($path, $content, [System.Text.UTF8Encoding]::new($false))
      $script:Touched++
    }
  } catch {
  }
}

Write-Host "Substituting placeholders inside starter-managed paths..."

foreach ($dir in $StarterDirs) {
  if (Test-Path $dir -PathType Container) {
    Get-ChildItem -Path $dir -Recurse -File -Include @("*.md","*.json","*.toml","*.yml","*.yaml","*.ts") -ErrorAction SilentlyContinue |
      ForEach-Object { Substitute-InFile $_.FullName }
  }
}

foreach ($p in $StarterGithubPatterns) {
  if (Test-Path $p -PathType Container) {
    Get-ChildItem -Path $p -Recurse -File -ErrorAction SilentlyContinue |
      ForEach-Object { Substitute-InFile $_.FullName }
  } elseif (Test-Path $p -PathType Leaf) {
    Substitute-InFile $p
  }
}

foreach ($f in $StarterRootFiles) { Substitute-InFile $f }

Write-Host "-> $Touched files updated (only starter-managed paths)."
Write-Host ""

# ---------------------------------------------------------------------------
# .gitignore — NEVER overwrite. Append (or create) on opt-in only.
# ---------------------------------------------------------------------------
$RecommendedIgnores = @"
# === Agentic Starter (auto-managed) — do not remove this header ===
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
"@

function Handle-Gitignore {
  $choice = $script:AppendGitignore
  if ([string]::IsNullOrEmpty($choice) -and -not $script:NonInteractive) {
    Write-Host "=========================================="
    Write-Host "  .gitignore"
    Write-Host "=========================================="
    if (Test-Path ".gitignore") {
      Write-Host "An existing .gitignore was found."
      Write-Host "I can APPEND recommended entries (your existing content is NEVER modified)."
    } else {
      Write-Host "No .gitignore found. I can CREATE one with recommended entries."
    }
    $resp = Read-Host "Proceed? [y/N]"
    if (-not $resp) { $resp = "n" }
    $first = $resp.Substring(0,1).ToLower()
    if ($first -eq "y" -or $first -eq "s") { $choice = "yes" } else { $choice = "no" }
    Write-Host ""
  }
  if (-not $choice) { $choice = "no" }

  if ($choice -ne "yes") {
    Write-Host "-> .gitignore left untouched."
    return
  }

  if (Test-Path ".gitignore") {
    $existing = Get-Content ".gitignore" -Raw -ErrorAction SilentlyContinue
    if ($existing -match "Agentic Starter \(auto-managed\)") {
      Write-Host "-> Recommended entries already present in .gitignore. Nothing to do."
    } else {
      Add-Content -Path ".gitignore" -Value "`n$RecommendedIgnores"
      Write-Host "-> Recommended entries APPENDED to .gitignore (original content preserved)."
    }
  } else {
    Set-Content -Path ".gitignore" -Value $RecommendedIgnores -Encoding UTF8
    Write-Host "-> .gitignore CREATED."
  }
}

Handle-Gitignore
Write-Host ""

# ---------------------------------------------------------------------------
# .starter-meta.json (machine-readable handoff for INIT.md)
# ---------------------------------------------------------------------------
$readOnlyGlobs = @(
  "**/*.razor","**/*.cs","**/*.csproj","**/*.sln",
  "package.json","pnpm-lock.yaml","yarn.lock","package-lock.json",
  "**/*.py","**/*.go","**/*.rs","**/*.java","**/*.kt","**/*.dart","**/*.php","**/*.rb"
)

$meta = [ordered]@{
  product_name                = $ProductName
  team                        = $Team
  domain                      = $Domain
  stack                       = $Stack
  bootstrapped_at             = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
  starter_version             = "0.2.0"
  existing_instruction_files  = $ExistingInstructionFiles
  init_must_ask               = @("team","domain","vision_oneliner","primary_personas")
  init_must_merge             = $ExistingInstructionFiles
  read_only_globs             = $readOnlyGlobs
}
$meta | ConvertTo-Json -Depth 6 | Out-File -FilePath ".starter-meta.json" -Encoding utf8
Write-Host "-> .starter-meta.json saved."
Write-Host ""

# ---------------------------------------------------------------------------
# choose CLI / LLM
# ---------------------------------------------------------------------------
$InitPrompt = 'Read INIT.md and execute it. Do NOT modify any user source files (.razor, .cs, .ts, .py, .go, .rs, package.json, etc). Only write inside .specs/, .agents/, .skills/, .claude/, .codex/, .github/copilot*, .github/workflows/dod.yml plus root AGENTS.md/CLAUDE.md/INIT.md/README*.md. If AGENTS.md/CLAUDE.md/copilot-instructions.md already existed before bootstrap (see .starter-meta.json), READ them and IMPROVE in place — preserve their essence. Ask the human only the questions listed in .starter-meta.json -> init_must_ask (team, domain, vision oneliner, personas). Use parallel multi-agents.'

$CliOpts = @(
  @{ Key="claude";   Label="Claude Code";                                                       Cmd="claude" },
  @{ Key="codex";    Label="Codex CLI";                                                         Cmd="codex" },
  @{ Key="copilot";  Label="GitHub Copilot CLI (chat — no agent loop)";                         Cmd="gh" },
  @{ Key="cursor";   Label="Cursor Agent (cursor-agent)";                                       Cmd="cursor-agent" },
  @{ Key="deepseek"; Label="Deepseek (via aider --model deepseek/deepseek-coder)";              Cmd="aider" },
  @{ Key="kimi";     Label="Kimi K2.6 (via aider --model openrouter/moonshotai/kimi-k2)";       Cmd="aider" },
  @{ Key="minimax";  Label="MiniMax M2.7 (via aider --model openrouter/minimax/minimax-text-01)"; Cmd="aider" },
  @{ Key="glm";      Label="GLM 5.1 (via aider --model openrouter/z-ai/glm-4.5)";               Cmd="aider" },
  @{ Key="hermes";   Label="Hermes Agent (Nous Research)";                                      Cmd="hermes" },
  @{ Key="openclaw"; Label="OpenClaw";                                                          Cmd="openclaw" },
  @{ Key="aider";    Label="Aider (pick model interactively)";                                  Cmd="aider" },
  @{ Key="other";    Label="Other / manual (copy prompt to clipboard)";                         Cmd="" },
  @{ Key="skip";     Label="Skip — I will run INIT.md later";                                   Cmd="" }
)

function Has-Cmd($name) {
  if ([string]::IsNullOrEmpty($name)) { return $false }
  return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Choose-Cli {
  if (-not [string]::IsNullOrEmpty($script:Cli)) { return $script:Cli }
  if ($script:NonInteractive) { return "skip" }

  Write-Host "=========================================="
  Write-Host "  Choose the CLI/LLM to run INIT.md"
  Write-Host "=========================================="
  Write-Host ""
  for ($i = 0; $i -lt $CliOpts.Count; $i++) {
    $opt = $CliOpts[$i]
    $mark = ""
    if (Has-Cmd $opt.Cmd) { $mark = "  [installed]" }
    Write-Host ("  [{0,2}] {1}{2}" -f ($i+1), $opt.Label, $mark)
  }
  Write-Host ""
  $resp = Read-Host "Number [13]"
  if ([string]::IsNullOrEmpty($resp)) { $resp = "13" }
  $idx = 0
  if (-not [int]::TryParse($resp, [ref]$idx)) { $idx = 13 }
  if ($idx -lt 1 -or $idx -gt $CliOpts.Count) { $idx = 13 }
  return $CliOpts[$idx-1].Key
}

$CliChoice = Choose-Cli

# ---------------------------------------------------------------------------
# clipboard helper
# ---------------------------------------------------------------------------
function Copy-ToClipboard($text) {
  try { Set-Clipboard -Value $text; return $true } catch { return $false }
}

# ---------------------------------------------------------------------------
# handoff
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "=========================================="
Write-Host "  Handing off to: $CliChoice"
Write-Host "=========================================="
Write-Host ""

function Require-Cmd($name, $installHint) {
  if (-not (Has-Cmd $name)) {
    Write-Host "$name not installed: $installHint"
    exit 1
  }
}

switch ($CliChoice) {
  "claude" {
    Require-Cmd "claude" "https://docs.claude.com/claude-code"
    & claude $InitPrompt
    exit $LASTEXITCODE
  }
  "codex" {
    Require-Cmd "codex" "https://github.com/openai/codex"
    & codex exec $InitPrompt
    exit $LASTEXITCODE
  }
  "copilot" {
    Require-Cmd "gh" "https://cli.github.com"
    if (Copy-ToClipboard $InitPrompt) { Write-Host "Prompt copied to clipboard." } else { Write-Host "(clipboard unavailable - copy manually below)" }
    Write-Host ""
    Write-Host "GitHub Copilot CLI does not run an autonomous agent loop."
    Write-Host "Open Copilot Chat (VS Code / IDE) and paste the prompt:"
    Write-Host ""
    Write-Host "  $InitPrompt"
    Write-Host ""
  }
  "cursor" {
    Require-Cmd "cursor-agent" "Cursor 3.0+ required"
    & cursor-agent $InitPrompt
    exit $LASTEXITCODE
  }
  "deepseek" {
    Require-Cmd "aider" "pipx install aider-chat"
    & aider --model deepseek/deepseek-coder --message $InitPrompt
    exit $LASTEXITCODE
  }
  "kimi" {
    Require-Cmd "aider" "pipx install aider-chat"
    & aider --model openrouter/moonshotai/kimi-k2 --message $InitPrompt
    exit $LASTEXITCODE
  }
  "minimax" {
    Require-Cmd "aider" "pipx install aider-chat"
    & aider --model openrouter/minimax/minimax-text-01 --message $InitPrompt
    exit $LASTEXITCODE
  }
  "glm" {
    Require-Cmd "aider" "pipx install aider-chat"
    & aider --model openrouter/z-ai/glm-4.5 --message $InitPrompt
    exit $LASTEXITCODE
  }
  "hermes" {
    Require-Cmd "hermes" "https://github.com/NousResearch/hermes-agent"
    Copy-ToClipboard $InitPrompt | Out-Null
    Write-Host "(prompt copied to clipboard as fallback)"
    & hermes $InitPrompt
    exit $LASTEXITCODE
  }
  "openclaw" {
    Require-Cmd "openclaw" "npm install -g openclaw@latest"
    Copy-ToClipboard $InitPrompt | Out-Null
    Write-Host "(prompt copied to clipboard as fallback)"
    & openclaw $InitPrompt
    exit $LASTEXITCODE
  }
  "aider" {
    Require-Cmd "aider" "pipx install aider-chat"
    & aider --message $InitPrompt
    exit $LASTEXITCODE
  }
  "other" {
    if (Copy-ToClipboard $InitPrompt) {
      Write-Host "Prompt copied to clipboard. Paste it into your CLI/agent of choice."
    } else {
      Write-Host "(clipboard unavailable - copy the prompt below manually)"
    }
    Write-Host ""
    Write-Host "Prompt:"
    Write-Host "  $InitPrompt"
    Write-Host ""
  }
  default {
    @"
Skipped CLI handoff. To run INIT.md later, open your agent and paste:

  $InitPrompt

Recommended next steps:
  1) Open an agent in this folder.
  2) Paste the prompt above.
  3) Review .specs/product/VISION.md, DOMAIN.md, architecture/DESIGN.md.
  4) git add -A; git commit -m "chore: bootstrap agentic starter"

Docs: https://github.com/wesleysimplicio/agentic-starter
"@ | Write-Host
  }
}
