---
name: Bug
about: Reportar bug com reprodução, ambiente e evidência
title: "fix: "
labels: ["bug", "needs-triage"]
assignees: []
---

# Bug

## Resumo

<!-- 1-2 frases descrevendo o bug. -->

## Comportamento observado

<!-- O que está acontecendo de fato. -->

## Comportamento esperado

<!-- O que deveria acontecer. -->

## Passos para reproduzir

1. ...
2. ...
3. ...

## Reprodução mínima

<!-- Snippet de código, URL, payload, comando, ou link pra repro. Quanto menor, melhor. -->

```
<repro aqui>
```

## Frequência

- [ ] Sempre (100%)
- [ ] Frequente (>50%)
- [ ] Intermitente (<50%)
- [ ] Raro (1x até agora)

## Severidade

- [ ] Bloqueante (produção quebrada, perda de dados)
- [ ] Alta (feature crítica indisponível)
- [ ] Média (feature degradada, workaround existe)
- [ ] Baixa (cosmético, edge case)

## Ambiente

- Versão do app/projeto: <!-- ex: 1.4.2 ou commit SHA -->
- OS: <!-- macOS 14.5, Ubuntu 22.04, Windows 11 -->
- Browser/Runtime: <!-- Chrome 124, Node 22.3, etc -->
- Stack relevante: <!-- <STACK> -->
- Ambiente: <!-- local / staging / produção -->

## Evidência

<!-- Screenshots, logs, stack trace, network HAR, vídeo, trace Playwright. Anexe ou cole abaixo. -->

```
<logs aqui>
```

## Análise inicial

<!-- Hipóteses, arquivos suspeitos, commits recentes que parecem relacionados. -->

## Workaround temporário

<!-- Se existe, qual? Caso contrário, "Nenhum identificado". -->

## Definition of Done para o fix

- [ ] Teste de regressão escrito (unit + e2e quando aplicável)
- [ ] Bug não reproduz mais com os passos acima
- [ ] Coverage mantido >= 80%
- [ ] Changelog atualizado em "Fixed"
- [ ] PR linkado a esta issue (`Closes #N`)

## Links relacionados

<!-- Issues parecidas, PRs anteriores, ADRs relevantes. -->
