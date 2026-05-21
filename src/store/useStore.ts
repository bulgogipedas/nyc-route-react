import { create } from 'zustand'

interface MapState {
  latitude: number
  longitude: number
  zoom: number
  pitch: number
  bearing: number
}

interface UIState {
  timeHour: number
  showTrips: boolean
  showH3: boolean
  showArc: boolean
  use3D: boolean
  selectedH3: any | null
  selectedTrip: any | null
  selectedArc: any | null
}

interface DataState {
  stats: {
    total_trips: number
    avg_distance: number
    peak_hour: number
    total_revenue: number
  } | null
  trips: any[]
  h3Data: any[]
  odFlows: any[]
  hourlyVolume: { hour: number; count: number }[]
  isLoading: boolean
  error: string | null
}

type StoreState = UIState & DataState & {
  mapState: MapState
  setMapState: (mapState: Partial<MapState>) => void
  setTimeHour: (hour: number) => void
  toggleLayer: (layer: 'trips' | 'h3' | 'arc') => void
  toggle3D: () => void
  setSelectedH3: (h3: any | null) => void
  setSelectedTrip: (trip: any | null) => void
  setSelectedArc: (arc: any | null) => void
  setStats: (stats: any) => void
  setTrips: (trips: any[]) => void
  setH3Data: (h3Data: any[]) => void
  setOdFlows: (odFlows: any[]) => void
  setHourlyVolume: (hourlyVolume: { hour: number; count: number }[]) => void
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
  timeHour: 12, // Noon by default
  showTrips: true,
  showH3: true,
  showArc: false,
  use3D: true,
  selectedH3: null,
  selectedTrip: null,
  selectedArc: null,

  stats: null,
  trips: [],
  h3Data: [],
  odFlows: [],
  hourlyVolume: [],
  isLoading: false,
  error: null,

  setMapState: (state) => set((s) => ({ mapState: { ...s.mapState, ...state } })),
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
  setStats: (stats) => set({ stats }),
  setTrips: (trips) => set({ trips }),
  setH3Data: (h3Data) => set({ h3Data }),
  setOdFlows: (odFlows) => set({ odFlows }),
  setHourlyVolume: (hourlyVolume) => set({ hourlyVolume }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
}))
