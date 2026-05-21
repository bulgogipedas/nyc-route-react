import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
} from 'recharts'
import { useStore } from '../store/useStore'
import { Layers, Cuboid as Cube, HelpCircle, Activity, MapPinned } from 'lucide-react'

const formatCompact = (value: number) => new Intl.NumberFormat('en-US').format(Math.round(value))

const describeDemandLevel = (count: number, maxCount: number) => {
  if (!maxCount) return 'No baseline yet'
  const ratio = count / maxCount
  if (ratio >= 0.78) return 'Very busy hour'
  if (ratio >= 0.55) return 'Steady demand'
  if (ratio >= 0.32) return 'Moderate demand'
  return 'Quiet period'
}

const getPressureTone = (deficitZones: number, surplusZones: number) => {
  if (deficitZones > surplusZones) return 'Passenger demand is ahead of available taxi supply.'
  if (surplusZones > deficitZones) return 'Taxi supply is building up faster than pickup demand.'
  return 'Supply and demand are relatively balanced across active zones.'
}

export default function SidebarControls() {
  const {
    timeHour,
    showTrips,
    showH3,
    showArc,
    use3D,
    toggleLayer,
    toggle3D,
    hourlyVolume,
    h3Data,
    odFlows,
    setTimeHour,
    isLoading,
  } = useStore()

  // Format hour for display
  const formatHour = (hour: number) => {
    return `${String(hour).padStart(2, '0')}:00`
  }

  // Handle chart click to select hour
  const handleChartClick = (state: any) => {
    if (state && state.activePayload && state.activePayload.length > 0) {
      const activeHour = state.activePayload[0].payload.hour
      setTimeHour(activeHour)
    }
  }

  const currentHourVolume = hourlyVolume.find((item) => item.hour === timeHour)?.count || 0
  const maxHourVolume = hourlyVolume.reduce((max, item) => Math.max(max, item.count), 0)
  const deficitZones = h3Data.filter((item) => item.deadhead_metric < 0).length
  const surplusZones = h3Data.filter((item) => item.deadhead_metric > 0).length
  const strongestFlow = odFlows[0]?.count || 0

  return (
    <div className="w-[380px] bg-primary text-canvas flex flex-col h-full border-r border-hairline/15 p-6 space-y-6 overflow-y-auto">
      {/* Brand Header */}
      <div>
        <h1 className="text-[40px] font-340 tracking-display-lg leading-[1.05] mt-1">
          Chrono<span className="text-block-lime font-bold">Route</span>
        </h1>
        <p className="text-[13px] text-canvas/75 font-sans leading-relaxed mt-2">
          Visual analytics dashboard for NYC Yellow Taxi fleet distribution and transit flows in Manhattan.
        </p>
      </div>

      <div className="h-px bg-hairline/15" />

      {/* Layer Control Panel */}
      <div className="space-y-4">
        <div className="flex items-center space-x-2 text-[12px] font-mono text-canvas/60">
          <Layers size={14} className="text-block-lime" />
          <span>VISUALIZATION LAYERS</span>
        </div>

        <div className="space-y-2">
          {/* Trips Layer Toggle */}
          <button
            onClick={() => toggleLayer('trips')}
            className={`w-full flex items-center justify-between p-3 rounded-md transition-all border ${
              showTrips 
                ? 'bg-canvas text-primary border-canvas' 
                : 'bg-transparent text-canvas border-hairline/20 hover:border-hairline/40'
            }`}
          >
            <div className="flex flex-col items-start text-left">
              <span className="text-[15px] font-bold">Animated Trip Paths</span>
              <span className={`text-[11px] ${showTrips ? 'text-primary/70' : 'text-canvas/50'}`}>
                Moving taxi trips during the selected hour
              </span>
            </div>
            <div className={`w-4 h-4 rounded-full border flex items-center justify-center ${showTrips ? 'bg-primary border-primary' : 'border-canvas/30'}`}>
              {showTrips && <div className="w-1.5 h-1.5 bg-canvas rounded-full" />}
            </div>
          </button>

          {/* H3 Grid Toggle */}
          <button
            onClick={() => toggleLayer('h3')}
            className={`w-full flex items-center justify-between p-3 rounded-md transition-all border ${
              showH3 
                ? 'bg-canvas text-primary border-canvas' 
                : 'bg-transparent text-canvas border-hairline/20 hover:border-hairline/40'
            }`}
          >
            <div className="flex flex-col items-start text-left">
              <span className="text-[15px] font-bold">H3 Deadhead Hotspots</span>
              <span className={`text-[11px] ${showH3 ? 'text-primary/70' : 'text-canvas/50'}`}>
                Where taxis are needed or piling up
              </span>
            </div>
            <div className={`w-4 h-4 rounded-full border flex items-center justify-center ${showH3 ? 'bg-primary border-primary' : 'border-canvas/30'}`}>
              {showH3 && <div className="w-1.5 h-1.5 bg-canvas rounded-full" />}
            </div>
          </button>

          {/* OD Flow Toggle */}
          <button
            onClick={() => toggleLayer('arc')}
            className={`w-full flex items-center justify-between p-3 rounded-md transition-all border ${
              showArc 
                ? 'bg-canvas text-primary border-canvas' 
                : 'bg-transparent text-canvas border-hairline/20 hover:border-hairline/40'
            }`}
          >
            <div className="flex flex-col items-start text-left">
              <span className="text-[15px] font-bold">Origin-Destination Flows</span>
              <span className={`text-[11px] ${showArc ? 'text-primary/70' : 'text-canvas/50'}`}>
                Strong passenger movement corridors
              </span>
            </div>
            <div className={`w-4 h-4 rounded-full border flex items-center justify-center ${showArc ? 'bg-primary border-primary' : 'border-canvas/30'}`}>
              {showArc && <div className="w-1.5 h-1.5 bg-canvas rounded-full" />}
            </div>
          </button>
        </div>
      </div>

      {/* 3D Option for H3 Hex */}
      {showH3 && (
        <div className="flex items-center justify-between p-3 bg-canvas/5 rounded-md border border-hairline/10">
          <div className="flex items-center space-x-2">
            <Cube size={14} className="text-block-pink" />
            <span className="text-[14px] font-sans">Show hotspot height</span>
          </div>
          <button
            onClick={toggle3D}
            className={`w-10 h-6 rounded-pill transition-colors flex items-center p-0.5 ${
              use3D ? 'bg-block-lime' : 'bg-canvas/20'
            }`}
          >
            <div
              className={`w-5 h-5 rounded-full bg-primary shadow-md transform transition-transform ${
                use3D ? 'translate-x-4' : 'translate-x-0'
              }`}
            />
          </button>
        </div>
      )}

      {/* H3 Legend */}
      {showH3 && (
        <div className="p-4 bg-canvas/5 rounded-md border border-hairline/10 space-y-3">
          <div className="text-[11px] font-mono tracking-eyebrow text-canvas/50 flex items-center justify-between">
            <span>TAXI SUPPLY BALANCE</span>
            <div className="group relative cursor-pointer">
              <HelpCircle size={12} />
              <div className="absolute right-0 bottom-6 hidden group-hover:block w-[240px] bg-primary border border-hairline/25 p-3 rounded-md shadow-2xl text-[12px] leading-relaxed z-50 text-canvas">
                Compares dropoffs and pickups in each small map area. Pink means riders are outpacing nearby taxis; lime means taxis are accumulating after dropoffs.
              </div>
            </div>
          </div>
          <div className="w-full h-3 rounded-full bg-gradient-to-r from-block-pink via-canvas/20 to-block-lime" />
          <div className="flex justify-between text-[11px] font-mono text-canvas/60">
            <span>NEEDS TAXIS</span>
            <span>BALANCED</span>
            <span>EXCESS TAXIS</span>
          </div>
        </div>
      )}

      {/* Current Hour Brief */}
      <div className="p-4 bg-canvas text-primary rounded-md border border-canvas space-y-3">
        <div className="flex items-center justify-between">
          <div className="text-[11px] font-mono tracking-eyebrow text-primary/55">CURRENT HOUR BRIEF</div>
          <div className="text-[11px] font-mono bg-primary text-canvas rounded-pill px-2 py-1">
            {formatHour(timeHour)}
          </div>
        </div>

        <div>
          <div className="flex items-center gap-2">
            <Activity size={16} />
            <div className="text-[20px] font-540 tracking-headline leading-none">
              {describeDemandLevel(currentHourVolume, maxHourVolume)}
            </div>
          </div>
          <div className="text-[12px] text-primary/60 mt-2 leading-relaxed">
            {formatCompact(currentHourVolume)} sampled trips this hour. {getPressureTone(deficitZones, surplusZones)}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <div className="bg-block-pink rounded-sm p-2.5 border border-primary/10">
            <div className="text-[10px] text-primary/55">Need taxis</div>
            <div className="text-[24px] font-540 leading-none mt-1">{deficitZones}</div>
          </div>
          <div className="bg-block-lime rounded-sm p-2.5 border border-primary/10">
            <div className="text-[10px] text-primary/55">Excess taxis</div>
            <div className="text-[24px] font-540 leading-none mt-1">{surplusZones}</div>
          </div>
          <div className="bg-block-mint rounded-sm p-2.5 border border-primary/10">
            <div className="text-[10px] text-primary/55">Top corridor</div>
            <div className="text-[24px] font-540 leading-none mt-1">{formatCompact(strongestFlow)}</div>
          </div>
        </div>

        <div className="flex items-start gap-2 text-[12px] leading-relaxed text-primary/65">
          <MapPinned size={14} className="mt-0.5 shrink-0" />
          <span>Hover the pink or lime map areas for plain-language dispatch guidance. Turn on flows to inspect the busiest passenger corridors.</span>
        </div>
      </div>

      <div className="h-px bg-hairline/15" />

      {/* Map Interpretation Guide */}
      <div className="p-4 bg-canvas/5 rounded-md border border-hairline/10 space-y-3">
        <div className="text-[11px] font-mono tracking-eyebrow text-canvas/50">
          MAP INTERPRETATION
        </div>
        <div className="text-[12px] font-sans text-canvas/75 leading-relaxed space-y-2">
          <p>
            Read the map as an operations board:
          </p>
          <div className="space-y-2 text-[11px] font-mono">
            <div className="flex items-start space-x-2.5">
              <span className="w-2 h-2 rounded-full bg-block-lime mt-1.5 shrink-0 shadow-[0_0_6px_rgba(210,255,0,0.6)]" />
              <div>
                <span className="text-block-lime font-bold">EXCESS TAXIS:</span> More dropoffs than pickups. Vehicles may need to relocate.
              </div>
            </div>
            <div className="flex items-start space-x-2.5">
              <span className="w-2 h-2 rounded-full bg-block-pink mt-1.5 shrink-0 shadow-[0_0_6px_rgba(255,51,204,0.6)]" />
              <div>
                <span className="text-block-pink font-bold">NEEDS TAXIS:</span> More pickups than dropoffs. Send available vehicles here.
              </div>
            </div>
            <div className="flex items-start space-x-2.5">
              <span className="w-2.5 h-0.5 bg-block-mint mt-2.5 shrink-0 shadow-[0_0_6px_rgba(0,245,212,0.6)]" />
              <div>
                <span className="text-block-mint font-bold">FLOW LINES:</span> Passenger corridors showing where riders are pulling vehicles next.
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="h-px bg-hairline/15" />

      {/* Hourly Analytics chart */}
      <div className="flex flex-col min-h-[220px] shrink-0">
        <div className="text-[12px] font-mono tracking-eyebrow text-canvas/60 mb-3 flex items-center justify-between">
          <span>HOURLY TRIP DISTRIBUTION</span>
          {isLoading && (
            <span className="text-block-lime text-[10px] font-mono animate-pulse tracking-normal">
              ● SYNCING DATABASE...
            </span>
          )}
        </div>
        <div className="h-[185px] w-full bg-canvas/5 rounded-md p-3 border border-hairline/10 relative">
          <div className="absolute top-2 right-2 text-[10px] font-mono text-block-lime">
            CLICK TO CHANGE HOUR
          </div>
          {hourlyVolume.length > 0 ? (
            <AreaChart
              width={306}
              height={155}
              data={hourlyVolume}
              margin={{ top: 18, right: 8, left: -24, bottom: 0 }}
              onClick={handleChartClick}
            >
              <XAxis
                dataKey="hour"
                stroke="rgba(255,255,255,0.4)"
                fontSize={10}
                tickLine={false}
                tickFormatter={(val) => `${val}h`}
              />
              <YAxis
                stroke="rgba(255,255,255,0.4)"
                fontSize={10}
                tickLine={false}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload
                    return (
                      <div className="bg-primary/95 text-canvas p-2 rounded-sm border border-hairline/25 text-[11px] font-mono">
                        <div className="font-540">Hour starting {formatHour(data.hour)}</div>
                        <div>{data.count.toLocaleString()} sampled trips</div>
                      </div>
                    )
                  }
                  return null
                }}
              />
              <Area
                type="monotone"
                dataKey="count"
                stroke="#D2FF00"
                fill="rgba(210, 255, 0, 0.15)"
                strokeWidth={2}
              />
              <ReferenceLine
                x={timeHour}
                stroke="#FF33CC"
                strokeWidth={1.5}
                strokeDasharray="3 3"
              />
            </AreaChart>
          ) : (
            <div className="w-full h-full flex items-center justify-center text-[13px] text-canvas/50 font-mono">
              Loading trip volume...
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
