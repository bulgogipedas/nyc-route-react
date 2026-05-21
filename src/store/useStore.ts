import { create } from 'zustand'

export interface MapState {
  latitude: number
  longitude: number
  zoom: number
  pitch: number
  bearing: number
}

export type TripSegment = [number, number, number]

export interface TripDatum {
  vendor: number | string
  service_type?: string
  segments: TripSegment[]
}

export interface H3Datum {
  h3: string
  pickups: number
  dropoffs: number
  deadhead_metric: number
}

export interface ODFlowDatum {
  from: [number, number]
  to: [number, number]
  count: number
}

export interface MonthDatum {
  id: string
  service_type?: string
  label: string
  source: string
  source_url: string
  total_trips: number
  avg_distance: number
  peak_hour: number
  total_revenue: number
  source_file: string
}

export interface HourlyVolumeDatum {
  hour: number
  count: number
  total_distance: number
  total_revenue: number
}

export interface StatsDatum {
  total_trips: number
  avg_distance: number
  peak_hour: number
  total_revenue: number
}

export interface PipelineMetadata {
  project: string
  source: string
  generated_at: string
  pipeline_version: string
  available_services: string[]
  available_months_by_service: Record<string, string[]>
  layers: Record<string, string>
  airflow: {
    dag_id: string
    schedule: string
  }
  artifacts: {
    name: string
    path: string
    bytes?: number
  }[]
}

interface UIState {
  selectedService: string
  selectedMonth: string
  timeHour: number
  showTrips: boolean
  showH3: boolean
  showArc: boolean
  use3D: boolean
  selectedH3: H3Datum | null
  selectedTrip: TripDatum | null
  selectedArc: ODFlowDatum | null
}

interface DataState {
  availableMonths: MonthDatum[]
  stats: StatsDatum | null
  trips: TripDatum[]
  h3Data: H3Datum[]
  odFlows: ODFlowDatum[]
  hourlyVolume: HourlyVolumeDatum[]
  hourlyVolumeByMonth: Record<string, HourlyVolumeDatum[]>
  hourlyVolumeByServiceMonth: Record<string, Record<string, HourlyVolumeDatum[]>>
  metadata: PipelineMetadata | null
  isLoading: boolean
  error: string | null
}

type StoreState = UIState & DataState & {
  mapState: MapState
  setMapState: (mapState: Partial<MapState>) => void
  setSelectedMonth: (month: string) => void
  setSelectedService: (service: string) => void
  setTimeHour: (hour: number) => void
  toggleLayer: (layer: 'trips' | 'h3' | 'arc') => void
  toggle3D: () => void
  setSelectedH3: (h3: H3Datum | null) => void
  setSelectedTrip: (trip: TripDatum | null) => void
  setSelectedArc: (arc: ODFlowDatum | null) => void
  setAvailableMonths: (months: DataState['availableMonths']) => void
  setStats: (stats: StatsDatum) => void
  setTrips: (trips: TripDatum[]) => void
  setH3Data: (h3Data: H3Datum[]) => void
  setOdFlows: (odFlows: ODFlowDatum[]) => void
  setHourlyVolume: (hourlyVolume: HourlyVolumeDatum[]) => void
  setHourlyVolumeByMonth: (hourlyVolumeByMonth: DataState['hourlyVolumeByMonth']) => void
  setHourlyVolumeByServiceMonth: (hourlyVolumeByServiceMonth: DataState['hourlyVolumeByServiceMonth']) => void
  setMetadata: (metadata: PipelineMetadata | null) => void
  setLoading: (isLoading: boolean) => void
  setError: (error: string | null) => void
}

export const useStore = create<StoreState>((set) => ({
  // Map state focused on Manhattan
  mapState: {
    latitude: 40.758896,
    longitude: -73.985130,
    zoom: 11.5,
    pitch: 45,
    bearing: 0,
  },
  selectedMonth: '2026-03',
  selectedService: 'yellow',
  timeHour: 12, // Noon by default
  showTrips: true,
  showH3: true,
  showArc: false,
  use3D: true,
  selectedH3: null,
  selectedTrip: null,
  selectedArc: null,

  availableMonths: [],
  stats: null,
  trips: [],
  h3Data: [],
  odFlows: [],
  hourlyVolume: [],
  hourlyVolumeByMonth: {},
  hourlyVolumeByServiceMonth: {},
  metadata: null,
  isLoading: false,
  error: null,

  setMapState: (state) => set((s) => ({ mapState: { ...s.mapState, ...state } })),
  setSelectedMonth: (selectedMonth) => set({ selectedMonth }),
  setSelectedService: (selectedService) => set({ selectedService }),
  setTimeHour: (hour) => set({ timeHour: hour }),
  toggleLayer: (layer) => set((s) => {
    switch (layer) {
      case 'trips': return { showTrips: !s.showTrips }
      case 'h3': return { showH3: !s.showH3 }
      case 'arc': return { showArc: !s.showArc }
    }
  }),
  toggle3D: () => set((s) => ({ use3D: !s.use3D })),
  setSelectedH3: (selectedH3) => set({ selectedH3 }),
  setSelectedTrip: (selectedTrip) => set({ selectedTrip }),
  setSelectedArc: (selectedArc) => set({ selectedArc }),
  setAvailableMonths: (availableMonths) => set({ availableMonths }),
  setStats: (stats) => set({ stats }),
  setTrips: (trips) => set({ trips }),
  setH3Data: (h3Data) => set({ h3Data }),
  setOdFlows: (odFlows) => set({ odFlows }),
  setHourlyVolume: (hourlyVolume) => set({ hourlyVolume }),
  setHourlyVolumeByMonth: (hourlyVolumeByMonth) => set({ hourlyVolumeByMonth }),
  setHourlyVolumeByServiceMonth: (hourlyVolumeByServiceMonth) => set({ hourlyVolumeByServiceMonth }),
  setMetadata: (metadata) => set({ metadata }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
}))
