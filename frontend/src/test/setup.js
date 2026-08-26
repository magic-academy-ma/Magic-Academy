import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

// React Flow(@xyflow/react)가 렌더링 시 ResizeObserver를 요구하지만 jsdom에는 없다.
global.ResizeObserver = global.ResizeObserver || class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

global.WebSocket = class WebSocket {
  constructor() {}
  close() {}
}

afterEach(() => {
  cleanup()
})
