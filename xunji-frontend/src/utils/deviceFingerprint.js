export function generateDeviceId() {
  if (window.crypto && window.crypto.randomUUID) {
    return window.crypto.randomUUID()
  }
  const array = new Uint8Array(16)
  if (window.crypto && window.crypto.getRandomValues) {
    window.crypto.getRandomValues(array)
  } else {
    for (let i = 0; i < array.length; i += 1) {
      array[i] = Math.floor(Math.random() * 256)
    }
  }
  return Array.from(array, (b) => b.toString(16).padStart(2, '0')).join('')
}

export function getOrCreateDeviceId() {
  const existing = localStorage.getItem('device_id')
  if (existing) {
    return existing
  }
  const deviceId = generateDeviceId()
  localStorage.setItem('device_id', deviceId)
  return deviceId
}
