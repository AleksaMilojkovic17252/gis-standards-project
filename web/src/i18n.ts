export const LOCALE = 'sr-Latn-RS'

export function formatNumber(value: number, digits = 1): string {
  return value.toLocaleString(LOCALE, { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

const propertyNames: Record<string, string> = {
  'Air temperature': 'Temperatura vazduha',
  'Relative humidity': 'Relativna vlažnost',
  'Air pressure': 'Vazdušni pritisak',
  'Wind speed': 'Brzina vetra',
  Precipitation: 'Padavine',
  'Global radiation': 'Globalno zračenje',
  'Soil temperature at 10 cm': 'Temperatura zemljišta na 10 cm',
  'Soil moisture': 'Vlažnost zemljišta',
  'Soil state': 'Stanje zemljišta',
}

const soilStates: Record<string, string> = {
  dry: 'suvo',
  moist: 'vlažno',
  wet: 'mokro',
  waterlogged: 'natopljeno',
}

export function propertyName(name: string): string {
  return propertyNames[name] ?? name
}

export function resultText(result: number | string, unit = '', digits = 1): string {
  if (typeof result === 'number') return unit ? `${formatNumber(result, digits)} ${unit}` : formatNumber(result, digits)
  return soilStates[result] ?? result
}
