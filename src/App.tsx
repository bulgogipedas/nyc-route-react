import { useEffect } from 'react'
import MapContainer from './components/MapContainer'
import SidebarControls from './components/SidebarControls'
import KPIStats from './components/KPIStats'
import TimeSlider from './components/TimeSlider'
import { useStore } from './store/useStore'
import { loadStaticData, loadTripsForHour, loadHourlyVolume } from './utils/dataService'
import { initDuckDB } from './utils/duckdb'
import { ShieldAlert } from 'lucide-react'

export default function App() {
  const { selectedMonth, selectedService, timeHour, isLoading, error, setError, setLoading, trips } = useStore()

  // Initial load
  useEffect(() => {
    async function init() {
      setLoading(true)
      try {
        console.log('App mounting. Loading static geo datasets...')
        await loadStaticData()

        console.log('Initializing DuckDB-WASM...')
        await initDuckDB()

        const initialState = useStore.getState()
        console.log('Loading hourly volume distribution...')
        await loadHourlyVolume(initialState.selectedMonth)

        console.log(`Loading initial trips for ${initialState.selectedMonth} hour ${initialState.timeHour}...`)
        await loadTripsForHour(initialState.timeHour, initialState.selectedMonth)
      } catch (err: unknown) {
        console.error('Initialization error:', err)
        setError(err instanceof Error ? err.message : 'Failed to initialize ChronoRoute analytical sandbox.')
      } finally {
        setLoading(false)
      }
    }
    init()
  }, [setError, setLoading])

  // Sync trips when the selected month or hour changes
  useEffect(() => {
    let active = true
    async function sync() {
      if (!active) return
      await loadHourlyVolume(selectedMonth)
      await loadTripsForHour(timeHour, selectedMonth)
    }
    sync()
    return () => {
      active = false
    }
  }, [selectedMonth, selectedService, timeHour])

  return (
    <div className="flex w-screen h-screen bg-block-navy text-canvas font-sans select-none overflow-hidden">
      {/* Sidebar Controls */}
      <SidebarControls />

      {/* Main Dashboard Panel */}
      <div className="flex-1 flex flex-col h-full relative">
        {/* Top KPIs Bar */}
        <div className="absolute top-6 left-6 right-6 z-10 pointer-events-none">
          <div className="pointer-events-auto">
            <KPIStats />
          </div>
        </div>

        {/* Map Visualizer (takes full width/height of parent) */}
        <div className="w-full h-full">
          <MapContainer />
        </div>

        {/* Bottom Time Scrub Control */}
        <div className="absolute bottom-6 left-6 right-6 z-10 pointer-events-none">
          <div className="max-w-[800px] mx-auto pointer-events-auto">
            <TimeSlider />
          </div>
        </div>

        {/* Loading overlay - only display full-screen during initial setup */}
        {(isLoading && trips.length === 0) && (
          <div className="absolute inset-0 bg-primary/80 backdrop-blur-sm z-50 flex flex-col items-center justify-center space-y-4">
            <div className="w-12 h-12 rounded-full border-4 border-block-lime border-t-transparent animate-spin" />
            <div className="text-center">
              <div className="text-[14px] font-mono tracking-eyebrow text-block-lime font-bold">
                CHRONOROUTE ENGINE WORKING
              </div>
              <div className="text-sm text-canvas/60 mt-1 font-sans">
                Running in-browser analytical queries with DuckDB-WASM...
              </div>
            </div>
          </div>
        )}

        {/* Error overlay */}
        {error && (
          <div className="absolute inset-0 bg-primary/90 backdrop-blur-md z-50 flex flex-col items-center justify-center p-8 text-center space-y-4">
            <div className="p-4 bg-block-pink rounded-full text-primary border border-primary/20">
              <ShieldAlert size={48} />
            </div>
            <div className="max-w-md space-y-2">
              <h2 className="text-[24px] font-340 tracking-display-lg">Sandbox Execution Error</h2>
              <p className="text-sm text-canvas/75 font-sans leading-relaxed">
                {error}
              </p>
              <div className="pt-4">
                <button
                  onClick={() => window.location.reload()}
                  className="bg-block-lime text-primary px-5 py-2.5 rounded-pill font-bold active:scale-95 transition-all text-sm"
                >
                  Reload Sandbox
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
