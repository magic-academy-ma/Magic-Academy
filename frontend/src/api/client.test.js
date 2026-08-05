import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiRequest } from './client.js'

afterEach(() => vi.restoreAllMocks())

describe.each([
  [401, '로그인이 필요하거나 만료되었습니다.'],
  [403, '접근 권한이 없습니다.'],
  [404, 'Simulation을 찾을 수 없습니다.'],
  [500, '서버 오류가 발생했습니다.'],
])('API error %s', (status, message) => {
  it('maps the status to the basic UI message', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: false, status })
    await expect(apiRequest('/test')).rejects.toMatchObject({ status, message })
  })
})
