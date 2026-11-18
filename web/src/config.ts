export const STA = '/sta/FROST-Server/v1.1'
export const OGC = '/ogc'
export const MF = '/mf'

export const PERIOD_START = Date.parse('2026-11-04T05:00:00Z')
export const PERIOD_END = Date.parse('2026-11-13T23:00:00Z')
export const DEFAULT_TIME = Date.parse('2026-11-12T10:00:00Z')
export const LIVE_START = Date.parse('2026-11-14T00:00:00Z')
export const MQTT_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/sta/mqtt`

export const INCA_BBOX = [9.46, 46.45, 17.19, 49.09]
export const CORRIDOR_WIDTH_KM = 10
export const MAX_CORRIDOR_VERTICES = 60

export const COLORS = {
  train: '#2a78d6',
  trainSelected: '#eb6834',
  rail: '#52514e',
  railHighlight: '#2a78d6',
  surface: '#fcfcfb',
  textPrimary: '#0b0b0b',
  textSecondary: '#52514e',
}

export const ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> saradnici (ODbL) | ' +
  'Vreme: <a href="https://data.hub.geosphere.at">GeoSphere Austria</a> (CC BY 4.0) | ' +
  'Vozovi i podaci o zemljištu: simulirani'
