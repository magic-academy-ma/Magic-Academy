import { expect, test } from '@playwright/test'

const user = {
  id: '01900000-0000-7000-8000-000000000001',
  username: 'slice-two-e2e',
  display_name: 'Slice Two E2E',
  roles: ['USER'],
}

const simulation = {
  id: '01900000-0000-7000-8000-000000000002',
  owner_id: user.id,
  name: 'Slice 2 E2E',
  status: 'ready',
  current_day: 1,
  current_tick: 0,
  magic_enabled: true,
  created_at: '2026-08-25T00:00:00Z',
}

const agents = [
  {
    id: '01900000-0000-7000-8000-000000000010',
    fixture_key: 'professor-01',
    fixture_version: 'professor-fixture-v0.2',
    name: '에단',
    agent_type: 'professor',
    mbti_type: 'ISTJ',
    profile: {
      openness: 50,
      conscientiousness: 50,
      extraversion: 50,
      agreeableness: 50,
      emotional_stability: 50,
    },
    student_profile: null,
    professor_profile: { academic_rank: '통합 교수', specialty: '통합마법학과' },
    state: { hunger: 50, fatigue: 10, stress: 0, satisfaction: 50, mood: 0 },
    location: { id: '01900000-0000-7000-8000-000000000020', code: 'classroom', name: '교실' },
  },
  {
    id: '01900000-0000-7000-8000-000000000011',
    fixture_key: 'student-01',
    fixture_version: 'student-fixture-v0.2',
    name: '아델',
    agent_type: 'student',
    mbti_type: 'INFP',
    profile: {
      openness: 50,
      conscientiousness: 50,
      extraversion: 50,
      agreeableness: 50,
      emotional_stability: 50,
    },
    student_profile: { grade: 1, interest_field: '마법 연구' },
    professor_profile: null,
    state: { hunger: 50, fatigue: 10, stress: 0, satisfaction: 50, mood: 0 },
    location: { id: '01900000-0000-7000-8000-000000000021', code: 'dormitory', name: '기숙사' },
  },
]

test('committed state and directional relationship deltas are rendered and cleared on failure', async ({ page }) => {
  let tickAttempt = 0
  await page.route('**/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())

    if (url.pathname === '/v1/auth/login') {
      await route.fulfill({ json: { access_token: 'e2e-token', token_type: 'bearer', user } })
      return
    }
    if (url.pathname === '/v1/simulations' && request.method() === 'POST') {
      await route.fulfill({ status: 201, json: simulation })
      return
    }
    if (url.pathname === `/v1/simulations/${simulation.id}/agents`) {
      await route.fulfill({ json: agents })
      return
    }
    if (url.pathname === `/v1/simulations/${simulation.id}/ticks/advance`) {
      tickAttempt += 1
      if (tickAttempt === 2) {
        await route.fulfill({
          status: 500,
          json: { error: { code: 'INTERNAL_ERROR', message: 'Tick failure' } },
        })
        return
      }
      await route.fulfill({
        json: {
          previous_tick: 0,
          current_tick: 1,
          current_day: 1,
          status: 'COMPLETED',
          agent_results: [],
          state_deltas: [{
            effect_id: 'state-fatigue',
            rule_id: 'STATE_FATIGUE_UP_MEDIUM',
            agent_id: agents[0].id,
            agent_name: agents[0].name,
            metric: 'fatigue',
            delta: 5,
            before: 10,
            after: 15,
            reason: '수업 참여',
          }],
          relationship_deltas: [{
            effect_id: 'relationship-trust',
            rule_id: 'REL_TRUST_UP_MEDIUM',
            source_agent_id: agents[0].id,
            target_agent_id: agents[1].id,
            metric: 'trust',
            delta: 3,
            before: 20,
            after: 23,
            reason: '협력 행동',
          }],
        },
      })
      return
    }
    await route.abort()
  })

  await page.goto('/')
  await page.getByLabel('아이디').fill(user.username)
  await page.getByLabel('비밀번호').fill('Slice2-e2e-password!')
  await page.getByRole('button', { name: '로그인' }).click()
  await page.getByRole('button', { name: 'Simulation 생성' }).click()
  await page.getByRole('button', { name: 'Tick 실행' }).click()

  await expect(page.getByLabel('에단의 피로 +5, 10에서 15으로 변화')).toBeVisible()
  const relationshipDeltas = page.getByLabel('에단에서 아델로 신뢰 +3, 20에서 23으로 변화')
  await expect(relationshipDeltas).toHaveCount(2)
  await expect(relationshipDeltas.first()).toBeVisible()
  await expect(page.getByText('에단→아델').first()).toBeVisible()

  await page.getByRole('button', { name: 'Tick 실행' }).click()

  await expect(page.getByRole('alert')).toContainText('Tick 실행 중 서버 오류가 발생했습니다.')
  await expect(page.getByLabel('에단의 피로 +5, 10에서 15으로 변화')).toHaveCount(0)
  await expect(page.getByLabel('에단에서 아델로 신뢰 +3, 20에서 23으로 변화')).toHaveCount(0)
})
