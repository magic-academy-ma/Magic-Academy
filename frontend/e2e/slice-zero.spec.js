import { expect, test } from '@playwright/test'

test('registers, logs in, creates a simulation, and displays the API agent set', async ({ page }) => {
  const username = `e2e_${Date.now()}`
  await page.goto('/')
  await page.getByRole('button', { name: '계정 만들기' }).click()
  await page.getByLabel('아이디').fill(username)
  await page.getByLabel('표시 이름').fill('E2E User')
  await page.getByLabel('비밀번호').fill('Slice0-e2e-password!')
  const agentsResponsePromise = page.waitForResponse((response) => response.url().includes('/agents') && response.request().method() === 'GET')
  await page.getByRole('button', { name: '가입하고 로그인' }).click()
  await page.getByRole('button', { name: 'Simulation 생성' }).click()
  const apiAgents = await (await agentsResponsePromise).json()
  await expect(page.getByText('Agent 6명')).toBeVisible()
  const uiIds = await page.locator('[data-agent-id]').evaluateAll((nodes) => nodes.map((node) => node.dataset.agentId).sort())
  expect(uiIds).toEqual(apiAgents.map((agent) => agent.id).sort())
  await page.getByRole('button', { name: /아델/ }).click()
  await expect(page.getByRole('heading', { name: '아델' })).toBeVisible()
})
