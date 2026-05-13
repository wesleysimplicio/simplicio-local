import { defineConfig, devices } from '@playwright/test';

/**
 * Configuração Playwright do starter.
 *
 * - Trace sempre ligado para auditoria de qualquer execução.
 * - Screenshots e vídeos só em falha (artefato menor em verde).
 * - Reporters html/json/junit gerados em test-results/ para o gate de DoD.
 * - Projetos cobrindo Chromium, Firefox e WebKit (cross-browser baseline).
 */
export default defineConfig({
  testDir: './tests/e2e',
  // Timeout por teste; ajuste por projeto se preciso.
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  // Em CI, garante que test.only nunca passe despercebido.
  forbidOnly: !!process.env.CI,
  // Retries só em CI para flakiness ocasional.
  retries: process.env.CI ? 2 : 0,
  // Limita paralelismo em CI para estabilidade.
  workers: process.env.CI ? 2 : undefined,
  // Diretório raiz para artefatos (traces, screenshots, vídeos, junit/json).
  outputDir: 'test-results/',
  reporter: [
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['json', { outputFile: 'test-results/results.json' }],
    ['junit', { outputFile: 'test-results/results.xml' }],
    ['list'],
  ],
  use: {
    // Base URL é opcional; sobrescreva via env BASE_URL.
    baseURL: process.env.BASE_URL,
    trace: 'on',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],
  // Caso o projeto rode dev server local, descomente e ajuste:
  // webServer: {
  //   command: 'npm run dev',
  //   url: 'http://localhost:3000',
  //   reuseExistingServer: !process.env.CI,
  //   timeout: 120_000,
  // },
});
