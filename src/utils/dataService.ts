import { getDuckDB } from './duckdb'
import { useStore } from '../store/useStore'
import { latLngToCell, cellToLatLng } from 'h3-js'

export async function loadStaticData() {
  const store = useStore.getState()
  store.setLoading(true)
  try {
    const [statsRes, h3Res, odRes] = await Promise.all([
      fetch('/data/stats.json').then((res) => {
        if (!res.ok) throw new Error('Failed to fetch stats')
        return res.json()
      }),
      fetch('/data/h3_deadhead.json').then((res) => {
        if (!res.ok) throw new Error('Failed to fetch H3 deadhead')
        return res.json()
      }),
      fetch('/data/od_flows.json').then((res) => {
        if (!res.ok) throw new Error('Failed to fetch OD flows')
        return res.json()
      }),
    ])
    
    store.setStats(statsRes)
    store.setH3Data(h3Res)
    store.setOdFlows(odRes)
    store.setError(null)
  } catch (error: any) {
    console.error('Failed to load static configuration data:', error)
    store.setError('Failed to load static configuration: ' + error.message)
  } finally {
    store.setLoading(false)
  }
}

export async function loadTripsForHour(hour: number) {
  const store = useStore.getState()
  store.setLoading(true)
  try {
    const { conn } = await getDuckDB()
    
    // Query 1: Get trips for the current active hour (for maps)
    const tripsQuery = `
      SELECT vendor, trip_distance, fare, path 
      FROM 'trips_sample.parquet' 
      WHERE hour = ${hour}
    `
    const tripsResult = await conn.query(tripsQuery)
    const tripsRows = tripsResult.toArray()
    
    // Query 2: Get cumulative stats from hour 0 to activeHour (for KPIs)
    const statsQuery = `
      SELECT COUNT(*) as trip_count, SUM(trip_distance) as total_distance, SUM(fare) as total_fare 
      FROM 'trips_sample.parquet' 
      WHERE hour <= ${hour}
    `
    const statsResult = await conn.query(statsQuery)
    const statsRows = statsResult.toArray()
    
    const parsedTrips: any[] = []
    const puCounts: Record<string, number> = {}
    const doCounts: Record<string, number> = {}
    const flowCounts: Record<string, number> = {}
    
    tripsRows.forEach((row: any) => {
      const rowObj = row.toJSON()
      const segments = JSON.parse(rowObj.path)
      
      parsedTrips.push({
        vendor: rowObj.vendor,
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
    const h3Data = Array.from(uniqueH3).map((h3) => {
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
    const odFlows = Object.entries(flowCounts).map(([key, count]) => {
      const [fromHex, toHex] = key.split('->')
      const fromLatLng = cellToLatLng(fromHex)
      const toLatLng = cellToLatLng(toHex)
      return {
        from: [fromLatLng[1], fromLatLng[0]], // [lng, lat]
        to: [toLatLng[1], toLatLng[0]], // [lng, lat]
        count
      }
    }).sort((a, b) => b.count - a.count).slice(0, 400) // Keep top 400 flows for visual efficiency
    
    // Scale cumulative stats (trips_sample is a ~1% sample of the full 2.96M dataset)
    const scaleFactor = 100
    let totalTripsScaled = 0
    let avgDistance = 0
    let totalRevenueScaled = 0
    
    if (statsRows.length > 0) {
      const statsObj = statsRows[0].toJSON()
      const rawCount = Number(statsObj.trip_count || 0)
      const rawDistance = Number(statsObj.total_distance || 0)
      const rawFare = Number(statsObj.total_fare || 0)
      
      totalTripsScaled = rawCount * scaleFactor
      avgDistance = rawCount > 0 ? rawDistance / rawCount : 0
      totalRevenueScaled = rawFare * scaleFactor
    }
    
    // Find the peak hour between 0 and activeHour dynamically
    let peakHour = 18
    if (store.hourlyVolume && store.hourlyVolume.length > 0) {
      const activeVolume = store.hourlyVolume.filter(v => v.hour <= hour)
      if (activeVolume.length > 0) {
        const peak = activeVolume.reduce((max, curr) => curr.count > max.count ? curr : max, { hour: 0, count: 0 })
        peakHour = peak.hour
      }
    }
    
    const hourlyStats = {
      total_trips: totalTripsScaled,
      avg_distance: avgDistance,
      peak_hour: peakHour,
      total_revenue: totalRevenueScaled
    }
    
    store.setTrips(parsedTrips)
    store.setH3Data(h3Data)
    store.setOdFlows(odFlows)
    store.setStats(hourlyStats)
    store.setError(null)
  } catch (error: any) {
    console.error(`Failed to load trips for hour ${hour}:`, error)
    store.setError(`Failed to query trips data for hour ${hour}: ` + error.message)
  } finally {
    store.setLoading(false)
  }
}

export async function loadHourlyVolume() {
  const store = useStore.getState()
  try {
    const { conn } = await getDuckDB()
    const query = `
      SELECT hour, COUNT(*) as count 
      FROM 'trips_sample.parquet' 
      GROUP BY hour 
      ORDER BY hour
    `
    const result = await conn.query(query)
    const rows = result.toArray()
    
    const parsedVolume = rows.map((row: any) => {
      const rowObj = row.toJSON()
      return {
        hour: Number(rowObj.hour),
        count: Number(rowObj.count),
      }
    })
    
    store.setHourlyVolume(parsedVolume)
  } catch (error) {
    console.error('Failed to load hourly volume from DuckDB:', error)
  }
}

