import { expect, test } from '@playwright/test';

const e2eApiUrl = process.env.E2E_API_URL ?? 'http://127.0.0.1:8001';
const e2eApiOrigin = new URL(e2eApiUrl).origin;

// 실제 API/DB. 서버의 LLM 의존성만 테스트 대역으로 바꾼다.
test.beforeAll(async ({ request }) => {
  const response = await request.get(`${e2eApiUrl}/health/e2e-runtime`);
  expect(
    response.ok(),
    '실제 LLM 호출을 막기 위해 tests/test_rumor_challenge_service.py 서버를 먼저 실행해야 합니다.',
  ).toBe(true);
  await expect(response.json()).resolves.toEqual({ runtime: 'mock' });
});

test.beforeEach(async ({ page }) => {
  await page.route('**/v1/**', async (route) => {
    expect(
      new URL(route.request().url()).origin,
      'E2E 프론트가 Mock Runtime 테스트 API가 아닌 서버를 호출하려고 했습니다.',
    ).toBe(e2eApiOrigin);
    await route.continue();
  });
});

test('CHAPTER 1 조사, 새로고침 이어하기, 개입, 9틱 엔딩', async ({ page }, testInfo) => {
  const username = `rumor_${Date.now()}`;
  const password = 'Rumor-e2e-test-password!';
  await page.goto('/');
  await page.getByRole('button', { name: '회원가입', exact: true }).click();
  await page.getByLabel('아이디', { exact: true }).fill(username);
  await page.getByLabel('표시 이름').fill('소문 조정관');
  await page.getByLabel('비밀번호').fill(password);
  await page.getByRole('button', { name: '가입하고 로그인' }).click();
  await page.getByRole('button', { name: '스토리모드', exact: true }).click();
  await page.getByRole('button', { name: '임시 조정관 임명을 받아들인다' }).click();
  await page.getByRole('button', { name: '사건을 맡는다' }).click();
  await page.getByRole('button', { name: '다음 틱 관찰' }).click();
  await expect(page.getByText('1라운드 · 1 / 9틱')).toBeVisible();
  await page.getByLabel('대화 상대').selectOption({ label: '에단' });
  await page.getByLabel('질문 주제').selectOption('VERIFY');
  await page.getByRole('button', { name: '조사·대화하기' }).click();
  await expect(page.getByText(/^확인된 사실 —/)).toBeVisible();
  await page.getByRole('button', { name: '아델 상태·관계' }).click();
  await expect(page.getByRole('complementary', { name: 'Agent Inspector' })).toBeVisible();
  await page.getByRole('button', { name: '관계 보기', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('button', { name: /닫기/ }).last().click();
  await page.screenshot({ path: testInfo.outputPath('rumor-chapter-investigation.png'), fullPage: true });
  await page.reload();
  await page.getByLabel('아이디', { exact: true }).fill(username);
  await page.getByLabel('비밀번호').fill(password);
  await page.getByRole('button', { name: '로그인', exact: true }).click();
  await page.getByRole('button', { name: '스토리모드', exact: true }).click();
  await expect(page.getByText('1라운드 · 1 / 9틱')).toBeVisible();
  await expect(page.getByText(/^확인된 사실 —/)).toBeVisible();
  await page.getByLabel('개입 방식').selectOption('PUBLISH_FACT');
  await page.getByRole('button', { name: '개입 제출' }).click();
  for (let tick = 2; tick <= 9; tick++) {
    await page.getByRole('button', { name: '다음 틱 관찰' }).click();
    await expect(page.getByText(new RegExp(`라운드 · ${tick} / 9틱`))).toBeVisible();
    if ([4, 7].includes(tick)) {
      await page.getByLabel('개입 방식').selectOption('WATCH');
      await page.getByRole('button', { name: '개입 제출' }).click();
    }
  }
  await expect(page.getByRole('heading', { name: '챕터 종료' })).toBeVisible();
  await expect(page.getByText('CHAPTER 1 클리어', { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('rumor-chapter-ending.png'), fullPage: true });
});

test('모바일 폭에서도 조사와 개입을 사용할 수 있다', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.getByRole('button', { name: '회원가입', exact: true }).click();
  await page.getByLabel('아이디', { exact: true }).fill(`rumor_mobile_${Date.now()}`);
  await page.getByLabel('표시 이름').fill('모바일 조정관');
  await page.getByLabel('비밀번호').fill('Rumor-e2e-test-password!');
  await page.getByRole('button', { name: '가입하고 로그인' }).click();
  await page.getByRole('button', { name: '스토리모드', exact: true }).click();
  await page.getByRole('button', { name: '임시 조정관 임명을 받아들인다' }).click();
  await page.getByRole('button', { name: '사건을 맡는다' }).click();
  await page.getByRole('button', { name: '다음 틱 관찰' }).click();
  await expect(page.getByLabel('질문 주제')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('rumor-chapter-mobile.png'), fullPage: true });
});
