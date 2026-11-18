import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { DEFAULT_TIME, PERIOD_END, PERIOD_START } from '../config'

type TimeState = {
  time: number
  setTime: (time: number) => void
  playing: boolean
  setPlaying: (playing: boolean) => void
  speed: number
  setSpeed: (speed: number) => void
}

const TimeContext = createContext<TimeState | null>(null)
const tickMs = 100

export function TimeProvider({ children }: { children: ReactNode }) {
  const [time, setTimeState] = useState(DEFAULT_TIME)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(300)

  useEffect(() => {
    if (!playing) return
    const timer = window.setInterval(() => {
      setTimeState((current) => {
        const next = current + speed * tickMs
        if (next >= PERIOD_END) {
          setPlaying(false)
          return PERIOD_END
        }
        return next
      })
    }, tickMs)
    return () => window.clearInterval(timer)
  }, [playing, speed])

  const value = useMemo(
    () => ({
      time,
      setTime: (next: number) => setTimeState(Math.min(PERIOD_END, Math.max(PERIOD_START, next))),
      playing,
      setPlaying,
      speed,
      setSpeed,
    }),
    [time, playing, speed],
  )
  return <TimeContext.Provider value={value}>{children}</TimeContext.Provider>
}

export function useTime(): TimeState {
  const state = useContext(TimeContext)
  if (!state) throw new Error('useTime must be used inside TimeProvider')
  return state
}

export function floorTo(time: number, stepMinutes: number): number {
  const step = stepMinutes * 60 * 1000
  return Math.floor(time / step) * step
}

function pad(value: number): string {
  return String(value).padStart(2, '0')
}

export function formatUtcDate(time: number): string {
  const date = new Date(time)
  return `${pad(date.getUTCDate())}.${pad(date.getUTCMonth() + 1)}.${date.getUTCFullYear()}.`
}

export function formatUtcTime(time: number): string {
  const date = new Date(time)
  return `${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}`
}

export function formatUtc(time: number): string {
  return `${formatUtcDate(time)} ${formatUtcTime(time)} UTC`
}
