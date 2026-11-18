import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { fetchTrainsOfDay } from '../api/mf'
import { fetchEdrParameterIds, fetchRailLines, fetchRailStations } from '../api/ogc'
import { fetchSnapshot, fetchStationLocations } from '../api/sta'
import { LIVE_START } from '../config'
import { floorTo } from './time'

const forever = { staleTime: Infinity, gcTime: Infinity }

export const useRailLines = () => useQuery({ queryKey: ['rail-lines'], queryFn: fetchRailLines, ...forever })
export const useRailStations = () => useQuery({ queryKey: ['rail-stations'], queryFn: fetchRailStations, ...forever })
export const useStationLocations = () =>
  useQuery({ queryKey: ['station-locations'], queryFn: fetchStationLocations, ...forever })
export const useEdrParameterIds = () =>
  useQuery({ queryKey: ['edr-parameters'], queryFn: fetchEdrParameterIds, ...forever })

export const liveSnapshotKey = ['snapshot', 'live']

export function useSnapshot(time: number, live = false) {
  const snapshotTime = floorTo(time, 10)
  return useQuery({
    queryKey: live ? liveSnapshotKey : ['snapshot', snapshotTime],
    queryFn: () => fetchSnapshot(live ? LIVE_START : snapshotTime),
    placeholderData: keepPreviousData,
    staleTime: Infinity,
  })
}

export function useTrainsOfDay(time: number) {
  const dayStart = floorTo(time, 24 * 60)
  return useQuery({
    queryKey: ['trains', dayStart],
    queryFn: () => fetchTrainsOfDay(dayStart),
    placeholderData: keepPreviousData,
    ...forever,
  })
}
