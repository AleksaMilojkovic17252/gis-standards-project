import { useQueryClient } from '@tanstack/react-query'
import mqtt from 'mqtt'
import { useEffect, useState } from 'react'
import { fetchSnapshot, type Observation, type SnapshotStation } from '../api/sta'
import { LIVE_START, MQTT_URL } from '../config'
import { liveSnapshotKey } from './queries'

export type LiveStatus = { connected: boolean; messages: number; lastTime?: number }

const topicPattern = /Datastreams\((\d+)\)\/Observations$/

function withObservation(stations: SnapshotStation[], datastreamId: number, observation: Observation) {
  return stations.map((station) => ({
    ...station,
    Datastreams: station.Datastreams.map((datastream) =>
      datastream['@iot.id'] === datastreamId ? { ...datastream, Observations: [observation] } : datastream,
    ),
  }))
}

export function useLiveFeed(enabled: boolean): LiveStatus {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<LiveStatus>({ connected: false, messages: 0 })

  useEffect(() => {
    if (!enabled) return
    let closed = false
    const client = mqtt.connect(MQTT_URL)
    client.on('connect', () => setStatus((current) => ({ ...current, connected: true })))
    client.on('close', () => setStatus((current) => ({ ...current, connected: false })))
    client.on('message', (topic, payload) => {
      const match = topicPattern.exec(topic)
      if (!match) return
      const observation = JSON.parse(payload.toString()) as Observation
      queryClient.setQueryData<SnapshotStation[]>(
        liveSnapshotKey,
        (stations) => stations && withObservation(stations, Number(match[1]), observation),
      )
      setStatus((current) => ({
        connected: true,
        messages: current.messages + 1,
        lastTime: Math.max(current.lastTime ?? 0, Date.parse(observation.phenomenonTime)),
      }))
    })
    queryClient
      .fetchQuery({ queryKey: liveSnapshotKey, queryFn: () => fetchSnapshot(LIVE_START), staleTime: Infinity })
      .then((stations) => {
        if (closed) return
        client.subscribe(
          stations.flatMap((station) =>
            station.Datastreams.map((datastream) => `v1.1/Datastreams(${datastream['@iot.id']})/Observations`),
          ),
        )
      })
    return () => {
      closed = true
      client.end(true)
      setStatus({ connected: false, messages: 0 })
    }
  }, [enabled, queryClient])

  return status
}
