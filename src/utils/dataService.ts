import { getDuckDB } from './duckdb'
import { useStore, type H3Datum, type HourlyVolumeDatum, type MonthDatum, type ODFlowDatum, type PipelineMetadata, type StatsDatum, type TripDatum, type TripSegment } from '../store/useStore'
import { latLngToCell, cellToLatLng } from 'h3-js'
import { dataUrl } from './dataVersion'

interface TripRow {
  vendor: number | string
  service_type?: string
  path: string
}

interface ArrowRow<T> {
  toJSON: () => T
}

export async function loadStaticData() {
  const store = useStore.getState()
  store.setLoading(true)
  try {
    const [statsRes, h3Res, odRes, monthsRes, hourlyByMonthRes, metadataRes, monthsByServiceRes, hourlyByServiceMonthRes] = await Promise.all([
      fetch(dataUrl('/data/stats.json')).then((res) => {
        if (!res.ok) throw new Error('Failed to fetch stats')
        return res.json()
      }),
      fetch(dataUrl('/data/h3_deadhead.json')).then((res) => {
        if (!res.ok) throw new Error('Failed to fetch H3 deadhead')
        return res.json()
      }),
      fetch(dataUrl('/data/od_flows.json')).then((res) => {
        if (!res.ok) throw new Error('Failed to fetch OD flows')
        return res.json()
      }),
      fetch(dataUrl('/data/months.json')).then((res) => {
        if (!res.ok) throw new Error('Failed to fetch months')
        return res.json()
      }),
      fetch(dataUrl('/data/hourly_volume_by_month.json')).then((res) => {
        if (!res.ok) throw new Error('Failed to fetch hourly volume by month')
        return res.json()
      }),
      fetch(dataUrl('/data/metadata.json')).then((res) => res.ok ? res.json() : null).catch(() => null),
      fetch(dataUrl('/data/months_by_service.json')).then((res) => res.ok ? res.json() : null).catch(() => null),
      fetch(dataUrl('/data/hourly_volume_by_service_month.json')).then((res) => res.ok ? res.json() : null).catch(() => null),
    ])

    const metadata = metadataRes as PipelineMetadata | null
    const selectedService = metadata?.available_services?.[0] || store.selectedService
    const months = (monthsByServiceRes || monthsRes) as MonthDatum[]
    const hourlyByServiceMonth = (hourlyByServiceMonthRes || {}) as Record<string, Record<string, HourlyVolumeDatum[]>>
    const hourlyByMonth = hourlyByServiceMonthRes
      ? (hourlyByServiceMonth[selectedService] || {})
      : hourlyByMonthRes as Record<string, HourlyVolumeDatum[]>
    const serviceMonths = months.filter((month) => !month.service_type || month.service_type === selectedService)
    const latestMonth = serviceMonths[serviceMonths.length - 1]?.id || months[months.length - 1]?.id || store.selectedMonth
    store.setAvailableMonths(months)
    store.setSelectedService(selectedService)
    store.setSelectedMonth(latestMonth)
    store.setHourlyVolumeByMonth(hourlyByMonth)
    store.setHourlyVolumeByServiceMonth(hourlyByServiceMonth)
    store.setHourlyVolume(hourlyByMonth[latestMonth] || [])
    store.setStats(statsRes as StatsDatum)
    store.setH3Data(h3Res as H3Datum[])
    store.setOdFlows(odRes as ODFlowDatum[])
    store.setMetadata(metadata)
    store.setError(null)
  } catch (error: unknown) {
    console.error('Failed to load static configuration data:', error)
    store.setError('Failed to load static configuration: ' + (error instanceof Error ? error.message : String(error)))
  } finally {
    store.setLoading(false)
  }
}

function buildCumulativeStats(month: string, hour: number) {
  const store = useStore.getState()
  const hourlyVolume = store.hourlyVolumeByServiceMonth[store.selectedService]?.[month]
    || store.hourlyVolumeByMonth[month]
    || []
  const activeRows = hourlyVolume.filter((row) => row.hour <= hour)

  if (activeRows.length === 0) {
    return {
      total_trips: 0,
      avg_distance: 0,
      peak_hour: hour,
      total_revenue: 0,
    }
  }

  const totalTrips = activeRows.reduce((sum, row) => sum + Number(row.count || 0), 0)
  const totalDistance = activeRows.reduce((sum, row) => sum + Number(row.total_distance || 0), 0)
  const totalRevenue = activeRows.reduce((sum, row) => sum + Number(row.total_revenue || 0), 0)
  const peak = activeRows.reduce((max, row) => Number(row.count || 0) > Number(max.count || 0) ? row : max, activeRows[0])

  return {
    total_trips: totalTrips,
    avg_distance: totalTrips > 0 ? totalDistance / totalTrips : 0,
    peak_hour: Number(peak.hour),
    total_revenue: totalRevenue,
  }
}

export async function loadTripsForHour(hour: number, month?: string) {
  const store = useStore.getState()
  const activeMonth = month || store.selectedMonth
  const activeService = store.selectedService
  store.setLoading(true)
  try {
    const { conn } = await getDuckDB()
    const describeResult = await conn.query("DESCRIBE SELECT * FROM 'trip_paths.parquet'")
    const tripColumns = new Set((describeResult.toArray() as ArrowRow<{ column_name: string }>[]).map((row) => row.toJSON().column_name))
    const hasServiceType = tripColumns.has('service_type')
    const serviceFilter = hasServiceType ? `AND service_type = '${activeService}'` : ''
    
    // Query 1: Get trips for the current active hour (for maps)
    const tripsQuery = `
      SELECT ${hasServiceType ? 'service_type,' : ''} vendor, trip_distance, fare, path 
      FROM 'trip_paths.parquet' 
      WHERE month = '${activeMonth}' AND hour = ${hour} ${serviceFilter}
    `
    const tripsResult = await conn.query(tripsQuery)
    const tripsRows = tripsResult.toArray() as ArrowRow<TripRow>[]

    const parsedTrips: TripDatum[] = []
    const puCounts: Record<string, number> = {}
    const doCounts: Record<string, number> = {}
    const flowCounts: Record<string, number> = {}
    
    tripsRows.forEach((row) => {
      const rowObj = row.toJSON()
      const segments = JSON.parse(rowObj.path) as TripSegment[]
      
      parsedTrips.push({
        vendor: rowObj.vendor,
        service_type: rowObj.service_type,
        segments: segments,
      })
      
      if (segments && segments.length >= 2) {
        const [puLon, puLat] = segments[0]
        const [doLon, doLat] = segments[segments.length - 1]
        
        // H3 cell resolution 8 for deadhead hotspots (Manhattan resolution)
        const puHex = latLngToCell(puLat, puLon, 8)
        const doHex = latLngToCell(doLat, doLon, 8)
        
        puCounts[puHex] = (puCounts[puHex] || 0) + 1
        doCounts[doHex] = (doCounts[doHex] || 0) + 1
        
        // H3 cell resolution 7 for cleaner, aggregated visual flows
        const puHex7 = latLngToCell(puLat, puLon, 7)
        const doHex7 = latLngToCell(doLat, doLon, 7)
        const flowKey = `${puHex7}->${doHex7}`
        flowCounts[flowKey] = (flowCounts[flowKey] || 0) + 1
      }
    })
    
    // Generate H3 deadhead metrics (dropoffs - pickups)
    const uniqueH3 = new Set([...Object.keys(puCounts), ...Object.keys(doCounts)])
    const h3Data: H3Datum[] = Array.from(uniqueH3).map((h3) => {
      const pickups = puCounts[h3] || 0
      const dropoffs = doCounts[h3] || 0
      return {
        h3,
        pickups,
        dropoffs,
        deadhead_metric: dropoffs - pickups
      }
    })
    
    // Generate OD Flows from flow counts
    const odFlows: ODFlowDatum[] = Object.entries(flowCounts).map(([key, count]) => {
      const [fromHex, toHex] = key.split('->')
      const fromLatLng = cellToLatLng(fromHex)
      const toLatLng = cellToLatLng(toHex)
      return {
        from: [fromLatLng[1], fromLatLng[0]] as [number, number], // [lng, lat]
        to: [toLatLng[1], toLatLng[0]] as [number, number], // [lng, lat]
        count
      }
    }).sort((a, b) => b.count - a.count).slice(0, 400) // Keep top 400 flows for visual efficiency
    
    store.setTrips(parsedTrips)
    store.setH3Data(h3Data)
    store.setOdFlows(odFlows)
    store.setStats(buildCumulativeStats(activeMonth, hour))
    store.setError(null)
  } catch (error: unknown) {
    console.error(`Failed to load trips for ${activeMonth} hour ${hour}:`, error)
    store.setError(`Failed to query ${activeMonth} trips for hour ${hour}: ` + (error instanceof Error ? error.message : String(error)))
  } finally {
    store.setLoading(false)
  }
}

export async function loadHourlyVolume(month?: string) {
  const store = useStore.getState()
  const activeMonth = month || store.selectedMonth
  const activeService = store.selectedService
  const serviceRows = store.hourlyVolumeByServiceMonth[activeService]?.[activeMonth]
  store.setHourlyVolume(serviceRows || store.hourlyVolumeByMonth[activeMonth] || [])
}
