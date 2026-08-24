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
describe('API error body parsing', () => {
  it('extracts code and message from the error body', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 409,
      json: () => Promise.resolve({
        error: { code: 'TICK_ALREADY_RUNNING', message: '이미 진행 중인 Tick이 있습니다.', trace_id: 'req_1' },
      }),
    })

    await expect(apiRequest('/test')).rejects.toMatchObject({
      status: 409,
      code: 'TICK_ALREADY_RUNNING',
      message: '이미 진행 중인 Tick이 있습니다.',
    })
  })

  it('falls back to the status message when the body has no error field', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({}),
    })

    await expect(apiRequest('/test')).rejects.toMatchObject({
      status: 500,
      code: undefined,
      message: '서버 오류가 발생했습니다.',
    })
  })

  it('falls back gracefully when the body is not JSON', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 404,
      json: () => Promise.reject(new Error('not json')),
    })

    await expect(apiRequest('/test')).rejects.toMatchObject({
      status: 404,
      code: undefined,
      message: 'Simulation을 찾을 수 없습니다.',
    })
  })
})