export const DATA_VERSION = '2026-04-b88e78b'

export function dataUrl(path: string) {
  return `${path}?v=${DATA_VERSION}`
}
