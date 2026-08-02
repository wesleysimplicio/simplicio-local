<h1 align="center">Simplicio Local</h1>

<p align="center">
  <strong>Universal State Runtime untuk inferensi LLM lokal di Apple Silicon: MLX, Metal, NEON, jalur ANE, dan CLI praktis.</strong><br />
  <em>Perintah tetap dalam bahasa Inggris agar bisa disalin persis.</em>
</p>

<p align="center">
<a href="https://github.com/wesleysimplicio/simplicio-local/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/wesleysimplicio/simplicio-local?style=flat-square" /></a>
<img alt="Apple Silicon" src="https://img.shields.io/badge/Apple%20Silicon-M1--M5-111827?style=flat-square" />
<img alt="CMake" src="https://img.shields.io/badge/CMake-3.27+-064f8c?style=flat-square" />
</p>

<p align="center">
<a href="../README.md">English</a> | <a href="README.pt-BR.md">Português</a> | <a href="README.es-ES.md">Español</a> | <a href="README.ja-JP.md">日本語</a> | <a href="README.ko-KR.md">한국어</a> | <a href="README.zh-CN.md">简体中文</a> | <a href="README.it-IT.md">Italiano</a> | <a href="README.fr-FR.md">Français</a> | <a href="README.ru-RU.md">Русский</a> | <a href="README.pl-PL.md">Polski</a> | <a href="README.hi-IN.md">हिन्दी</a> | <a href="README.ar-SA.md">العربية</a> | <a href="README.he-IL.md">עברית</a> | <a href="README.ms-MY.md">Bahasa Melayu</a> | <a href="README.id-ID.md">Bahasa Indonesia</a>
</p>

<p align="center">
  <img src="../assets/us4-v6-apple-edition-promo.png" alt="Simplicio Local preview" width="860" />
</p>

---

## Ringkasnya

Universal State Runtime untuk inferensi LLM lokal di Apple Silicon: MLX, Metal, NEON, jalur ANE, dan CLI praktis.

## DNA proyek

Halaman lokal ini mempertahankan jalur cepat. Panduan teknis lengkap yang dipulihkan ada di README utama agar suara asli dan detail operasional proyek tetap hidup.

- Full restored guide: [../README.md](../README.md)
- Local project note: simplicio-local is the local inference edge of the ecosystem: native launchers, bootstrap scripts, CMake/package metadata, and the Apple-facing path for a local Simplicio experience. The refreshed README now keeps the global polish while preserving the practical installation and build notes from the earlier guide.

## Mulai cepat

```bash
brew install cmake ninja node
npm ci
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
./build/apps/us4-cli --probe
```

## Apa yang dilakukan

- Local-first runtime path for Apple Silicon inference experiments.
- CMake + Ninja build with CLI smoke flows.
- Ollama/custom upstream serve path for practical chat backends.
- Runtime docs for MLX, Metal, scheduler, memory, cache and benchmarks.

## Mengapa README ini dibuat agar mudah menarik perhatian

- janji nilai yang jelas di layar pertama
- tautan bahasa sebelum instalasi
- badge dan hero untuk kepercayaan
- quick start siap salin
- bukti sebelum detail panjang
- grafik bintang sebagai social proof

## Cara kerjanya

```mermaid
flowchart LR
  mapper["simplicio-mapper
repo context"] --> current["Simplicio Local
this project"]
  prompt["simplicio-prompt
reasoning runtime"] --> current
  current --> evidence["validated evidence
tests, docs, screenshots"]
  current --> sprint["simplicio-sprint
delivery loop"]
```

## Bukti dan validasi

- Changelog tracks CMake project version and starter package version separately.
- Playwright CLI smoke tests are the high-signal E2E path.
- Repo currently resolves on GitHub as wesleysimplicio/simplicio-local.

## Ekosistem Simplicio

- [simplicio-mapper](https://github.com/wesleysimplicio/simplicio-mapper) supplies repo context before interpretation.
- [simplicio-cli](https://github.com/wesleysimplicio/simplicio-dev-cli) executes focused code tasks with verification.
- [simplicio-prompt](https://github.com/wesleysimplicio/simplicio-prompt) provides fan-out and consensus runtime patterns.
- [simplicio-sprint](https://github.com/wesleysimplicio/simplicio-sprint) turns cards into draft PR delivery loops.

## Standar dokumentasi

- [runtime/README.md](../runtime/README.md)
- [CHANGELOG.md](../CHANGELOG.md)
- [docs/readme-globalization-standard.md](../docs/readme-globalization-standard.md)

## Riwayat bintang

<a href="https://www.star-history.com/#wesleysimplicio/simplicio-local&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=wesleysimplicio/simplicio-local&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=wesleysimplicio/simplicio-local&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=wesleysimplicio/simplicio-local&type=Date" />
  </picture>
</a>

## Lisensi

See the repository license and distribution notes before production use.
