import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mockStorage = new Map()

beforeEach(() => {
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: {
      getItem: (key) => mockStorage.get(key) ?? null,
      setItem: (key, value) => mockStorage.set(key, String(value)),
      clear: () => mockStorage.clear(),
    },
  })
  window.localStorage.setItem('VITE_USE_MOCK', 'true')
})

afterEach(() => {
  cleanup()
  window.localStorage.clear()
  vi.restoreAllMocks()
  vi.resetModules()
})

describe('Mock 모드 통합 흐름', () => {
  it('백엔드 없이 로그인하고 Simulation과 Agent 6명을 Inspector에 표시한다', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const { default: App } = await import('./App.jsx')

    render(<App />)
    await userEvent.type(screen.getByLabelText('이메일'), 'wizard@magic.ac')
    await userEvent.type(screen.getByLabelText('비밀번호'), 'mock-password')
    await userEvent.click(screen.getByRole('button', { name: '로그인' }))

    await userEvent.click(await screen.findByRole('button', { name: '시뮬레이션 시작' }))
    await userEvent.click(await screen.findByRole('button', { name: '건너뛰기 →' }))
    await userEvent.click(await screen.findByRole('button', { name: '이 Persona로 시작하기 →' }))
    await userEvent.click(await screen.findByRole('button', { name: /시뮬레이션 시작/ }))

    expect(await screen.findByText('Agent 6명')).toBeInTheDocument()
    expect(document.querySelectorAll('[data-agent-id]')).toHaveLength(6)
    expect(screen.getByRole('heading', { name: 'Inspector' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '에단' })).toBeInTheDocument()
    expect(screen.getByText(/교실/, { selector: 'dd' })).toBeInTheDocument()
    expect(fetchSpy).not.toHaveBeenCalled()
  }, 10000)
})
