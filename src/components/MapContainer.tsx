import { useState, useEffect } from 'react'
import DeckGL from '@deck.gl/react'
import Map from 'react-map-gl/maplibre'
import { TripsLayer } from '@deck.gl/geo-layers'
import { H3HexagonLayer } from '@deck.gl/geo-layers'
import { ArcLayer } from '@deck.gl/layers'
import type { Layer, PickingInfo } from '@deck.gl/core'
import { cellToLatLng } from 'h3-js'
import { useStore, type H3Datum, type MapState, type ODFlowDatum, type TripDatum, type TripSegment } from '../store/useStore'
import {
  ZoomIn,
  ZoomOut,
  RotateCw,
  RotateCcw,
  Compass,
  ChevronUp,
  ChevronDown
} from 'lucide-react'
import 'maplibre-gl/dist/maplibre-gl.css'

const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

const formatCompact = (value: number) => new Intl.NumberFormat('en-US').format(Math.round(value))

const formatHour = (hour: number) => `${String(hour).padStart(2, '0')}:00`

const describeManhattanArea = (position: [number, number]) => {
  const [lng, lat] = position
  const northSouth =
    lat >= 40.82 ? 'Upper Manhattan' :
    lat >= 40.785 ? 'Upper Manhattan edge' :
    lat >= 40.745 ? 'Midtown Manhattan' :
    lat >= 40.715 ? 'Lower Manhattan' :
    'Downtown edge'
  const eastWest = lng <= -73.99 ? 'west side' : lng >= -73.955 ? 'east side' : 'central corridor'
  return `${northSouth}, ${eastWest}`
}

const getHotspotPriority = (value: number, maxValue: number) => {
  const ratio = maxValue > 0 ? Math.abs(value) / maxValue : 0
  if (ratio >= 0.66) return { label: 'High priority', tone: 'text-block-pink', bar: 'w-full' }
  if (ratio >= 0.33) return { label: 'Medium priority', tone: 'text-block-lime', bar: 'w-2/3' }
  return { label: 'Low priority', tone: 'text-canvas/70', bar: 'w-1/3' }
}

type HoverInfo =
  | {
  x: number
  y: number
      object: H3Datum
      layerId: 'h3'
    }
  | {
      x: number
      y: number
      object: ODFlowDatum
      layerId: 'arc'
    }

export default function MapContainer() {
  const {
    mapState,
    setMapState,
    timeHour,
    showTrips,
    showH3,
    showArc,
    use3D,
    trips,
    h3Data,
    odFlows,
  } = useStore()

  const [currentTime, setCurrentTime] = useState(timeHour * 3600)
  const [hoverInfo, setHoverInfo] = useState<HoverInfo | null>(null)

  // Reset time to start of hour when the hour changes
  useEffect(() => {
    const frame = requestAnimationFrame(() => setCurrentTime(timeHour * 3600))
    return () => cancelAnimationFrame(frame)
  }, [timeHour])

  // Animation loop for TripsLayer
  useEffect(() => {
    let animation: number
    const animate = () => {
      setCurrentTime((t) => {
        const start = timeHour * 3600
        const end = (timeHour + 1) * 3600
        // Speed up the trip animation (8 seconds per frame for lively flow)
        const next = t + 8
        return next > end ? start : next
      })
      animation = requestAnimationFrame(animate)
    }
    animation = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(animation)
  }, [timeHour])

  // Calculate dynamic maximums for scaling visuals based on the current hour's active data
  const maxVal = h3Data.reduce((max, d) => Math.max(max, Math.abs(d.deadhead_metric)), 1)
  const maxFlow = odFlows.reduce((max, d) => Math.max(max, d.count), 1)

  const renderTooltip = () => {
    if (!hoverInfo) return null

    if (hoverInfo.layerId === 'h3') {
      const metric = Number(hoverInfo.object.deadhead_metric || 0)
      const pickups = Number(hoverInfo.object.pickups || 0)
      const dropoffs = Number(hoverInfo.object.dropoffs || 0)
      const gap = Math.abs(metric)
      const center = cellToLatLng(hoverInfo.object.h3)
      const areaLabel = describeManhattanArea([center[1], center[0]])
      const isDeficit = metric < 0
      const isBalanced = metric === 0
      const priority = getHotspotPriority(metric, maxVal)
      const title = isBalanced
        ? 'Balanced taxi activity'
        : isDeficit
          ? 'Area needs more taxis'
          : 'Excess taxis accumulating'
      const action = isBalanced
        ? 'Keep monitoring. Pickup and dropoff activity are currently matched.'
        : isDeficit
          ? 'Dispatch available taxis toward this area before wait times rise.'
          : 'Route idle taxis out toward nearby demand zones.'

      return (
        <div className="space-y-3">
          <div>
            <div className={`text-[12px] font-mono tracking-eyebrow ${isDeficit ? 'text-block-pink' : 'text-block-lime'}`}>
              {isDeficit ? 'DEMAND GAP' : isBalanced ? 'BALANCED AREA' : 'SUPPLY BUILDUP'}
            </div>
            <div className="text-[18px] font-540 leading-tight mt-1">{title}</div>
            <div className="text-[12px] text-canvas/55 mt-1">{areaLabel} • {formatHour(timeHour)}</div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div className="bg-canvas/8 border border-hairline/15 rounded-sm p-2">
              <div className="text-[10px] text-canvas/45">Pickups</div>
              <div className="text-[18px] font-540 text-block-pink">{formatCompact(pickups)}</div>
            </div>
            <div className="bg-canvas/8 border border-hairline/15 rounded-sm p-2">
              <div className="text-[10px] text-canvas/45">Dropoffs</div>
              <div className="text-[18px] font-540 text-block-lime">{formatCompact(dropoffs)}</div>
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex justify-between text-[12px]">
              <span className="text-canvas/55">{isDeficit ? 'Taxi shortfall' : isBalanced ? 'Net gap' : 'Taxi surplus'}</span>
              <span className={priority.tone}>{isBalanced ? '0' : formatCompact(gap)} trips</span>
            </div>
            <div className="h-1.5 bg-canvas/15 rounded-full overflow-hidden">
              <div className={`h-full ${isDeficit ? 'bg-block-pink' : 'bg-block-lime'} ${priority.bar}`} />
            </div>
            <div className={`text-[11px] font-540 ${priority.tone}`}>{priority.label}</div>
          </div>

          <div className="bg-canvas text-primary rounded-sm p-3 text-[12px] leading-relaxed">
            <span className="font-540">Suggested action:</span> {action}
          </div>
        </div>
      )
    }

    if (hoverInfo.layerId === 'arc') {
      const count = Number(hoverInfo.object.count || 0)
      const ratio = Math.min(1, count / maxFlow)
      const fromLabel = describeManhattanArea(hoverInfo.object.from)
      const toLabel = describeManhattanArea(hoverInfo.object.to)

      return (
        <div className="space-y-3">
          <div>
            <div className="text-[12px] font-mono tracking-eyebrow text-block-mint">PASSENGER CORRIDOR</div>
            <div className="text-[18px] font-540 leading-tight mt-1">Strong origin-to-destination flow</div>
            <div className="text-[12px] text-canvas/55 mt-1">{formatHour(timeHour)} passenger movement</div>
          </div>

          <div className="space-y-2 text-[12px]">
            <div>
              <div className="text-canvas/45">Pickup area</div>
              <div className="font-540">{fromLabel}</div>
            </div>
            <div>
              <div className="text-canvas/45">Dropoff area</div>
              <div className="font-540">{toLabel}</div>
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex justify-between text-[12px]">
              <span className="text-canvas/55">Observed trips</span>
              <span className="text-block-lime">{formatCompact(count)}</span>
            </div>
            <div className="h-1.5 bg-canvas/15 rounded-full overflow-hidden">
              <div className="h-full bg-block-mint" style={{ width: `${Math.max(12, ratio * 100)}%` }} />
            </div>
          </div>

          <div className="bg-canvas text-primary rounded-sm p-3 text-[12px] leading-relaxed">
            Use this corridor to understand where riders are pulling vehicles next.
          </div>
        </div>
      )
    }

    return null
  }

  // DeckGL Layers definition
  const layers = [
    showH3 && h3Data.length > 0 && new H3HexagonLayer<H3Datum>({
      id: 'h3-layer',
      data: h3Data,
      pickable: true,
      wireframe: true,
      filled: true,
      extruded: use3D,
      elevationScale: 1,
      getHexagon: (d) => d.h3,
      // Normalize colors dynamically based on current hour's maximum metric
      getFillColor: (d) => {
        const val = d.deadhead_metric
        const ratio = Math.abs(val) / maxVal
        // Apply power scaling so low values remain visible but high values stand out
        const alpha = Math.floor(40 + 200 * Math.pow(ratio, 0.5))
        
        if (val > 0) {
          // Surplus (Supply) -> Lime-Yellow
          return [210, 255, 0, alpha]
        } else if (val < 0) {
          // Deficit (Demand) -> Magenta-Pink
          return [255, 51, 204, alpha]
        }
        return [255, 255, 255, 10]
      },
      getLineColor: [255, 255, 255, 25],
      lineWidthMinPixels: 0.8,
      // Power-scale elevation to create a beautiful 3D skyline (capped at 1.5km)
      getElevation: (d) => {
        const val = Math.abs(d.deadhead_metric)
        return Math.pow(val / maxVal, 0.7) * 1200
      },
      onHover: (info: PickingInfo<H3Datum>) => {
        if (info.object) {
          setHoverInfo({
            x: info.x,
            y: info.y,
            object: info.object,
            layerId: 'h3'
          })
        } else {
          setHoverInfo(null)
        }
      },
      updateTriggers: {
        extruded: use3D,
        getFillColor: [h3Data, maxVal],
        getElevation: [h3Data, maxVal]
      }
    }),

    showArc && odFlows.length > 0 && new ArcLayer<ODFlowDatum>({
      id: 'arc-layer',
      data: odFlows,
      pickable: true,
      // Scale arc width dynamically between 1 and 6 pixels
      getWidth: (d) => 1 + (d.count / maxFlow) * 5,
      getSourcePosition: (d) => d.from,
      getTargetPosition: (d) => d.to,
      // Source color (pickup) is magenta, target (dropoff) is lime yellow
      getSourceColor: (d) => [255, 51, 204, Math.floor(80 + 175 * (d.count / maxFlow))],
      getTargetColor: (d) => [210, 255, 0, Math.floor(80 + 175 * (d.count / maxFlow))],
      getHeight: 0.5,
      onHover: (info: PickingInfo<ODFlowDatum>) => {
        if (info.object) {
          setHoverInfo({
            x: info.x,
            y: info.y,
            object: info.object,
            layerId: 'arc'
          })
        } else {
          setHoverInfo(null)
        }
      },
      updateTriggers: {
        getWidth: [odFlows, maxFlow],
        getSourceColor: [odFlows, maxFlow],
        getTargetColor: [odFlows, maxFlow]
      }
    }),

    showTrips && trips.length > 0 && new TripsLayer<TripDatum>({
      id: 'trips-layer',
      data: trips,
      // Map path to [lng, lat] to prevent Deck.gl from treating the 3rd index (timestamp) as a Z-altitude coordinate
      getPath: (d) => d.segments.map((p: TripSegment) => [p[0], p[1]]) as unknown as number[],
      getTimestamps: (d) => d.segments.map((p: TripSegment) => p[2]),
      // CMT Vendor 1 = Electric Pink, Verifone Vendor 2 = Neon Mint
      getColor: (d) => d.vendor === 1 ? [255, 51, 204] : [0, 245, 212],
      opacity: 0.95,
      widthMinPixels: 2.5,
      trailLength: 180,
      currentTime: currentTime,
    })
  ].filter(Boolean) as Layer[]

  return (
    <div className="relative w-full h-full bg-block-navy overflow-hidden">
      <DeckGL
        viewState={mapState}
        onViewStateChange={(e) => setMapState(e.viewState as Partial<MapState>)}
        controller={true}
        layers={layers}
        getCursor={({ isHovering }) => (isHovering ? 'pointer' : 'default')}
      >
        <Map
          mapStyle={MAP_STYLE}
          reuseMaps
        />
      </DeckGL>

      {/* Tooltip Overlay */}
      {hoverInfo && (
        <div
          className="absolute z-50 w-[320px] p-4 bg-primary/95 text-canvas rounded-md border border-hairline/25 shadow-2xl backdrop-blur-md pointer-events-none transition-all duration-75"
          style={{ left: hoverInfo.x + 15, top: hoverInfo.y + 15 }}
        >
          {renderTooltip()}
        </div>
      )}

      {/* Floating Map Navigation Controls */}
      <div className="absolute right-6 top-[200px] z-20 flex flex-col space-y-2 bg-primary/80 border border-hairline/25 p-1.5 rounded-md shadow-2xl backdrop-blur-md pointer-events-auto">
        <button
          onClick={() => setMapState({ zoom: mapState.zoom + 0.5 })}
          title="Zoom In"
          className="w-8 h-8 flex items-center justify-center rounded bg-canvas/5 hover:bg-canvas/15 active:scale-95 transition-all text-canvas cursor-pointer"
        >
          <ZoomIn size={15} />
        </button>
        <button
          onClick={() => setMapState({ zoom: mapState.zoom - 0.5 })}
          title="Zoom Out"
          className="w-8 h-8 flex items-center justify-center rounded bg-canvas/5 hover:bg-canvas/15 active:scale-95 transition-all text-canvas cursor-pointer"
        >
          <ZoomOut size={15} />
        </button>
        <div className="h-px bg-hairline/15 my-0.5" />
        <button
          onClick={() => setMapState({ pitch: Math.min(85, mapState.pitch + 10) })}
          title="Tilt Down (3D View Mode)"
          className="w-8 h-8 flex items-center justify-center rounded bg-canvas/5 hover:bg-canvas/15 active:scale-95 transition-all text-canvas cursor-pointer"
        >
          <ChevronUp size={15} />
        </button>
        <button
          onClick={() => setMapState({ pitch: Math.max(0, mapState.pitch - 10) })}
          title="Tilt Up (2D View Mode)"
          className="w-8 h-8 flex items-center justify-center rounded bg-canvas/5 hover:bg-canvas/15 active:scale-95 transition-all text-canvas cursor-pointer"
        >
          <ChevronDown size={15} />
        </button>
        <div className="h-px bg-hairline/15 my-0.5" />
        <button
          onClick={() => setMapState({ bearing: (mapState.bearing - 15 + 360) % 360 })}
          title="Rotate Left"
          className="w-8 h-8 flex items-center justify-center rounded bg-canvas/5 hover:bg-canvas/15 active:scale-95 transition-all text-canvas cursor-pointer"
        >
          <RotateCcw size={15} />
        </button>
        <button
          onClick={() => setMapState({ bearing: (mapState.bearing + 15) % 360 })}
          title="Rotate Right"
          className="w-8 h-8 flex items-center justify-center rounded bg-canvas/5 hover:bg-canvas/15 active:scale-95 transition-all text-canvas cursor-pointer"
        >
          <RotateCw size={15} />
        </button>
        <div className="h-px bg-hairline/15 my-0.5" />
        <button
          onClick={() => setMapState({ latitude: 40.758896, longitude: -73.985130, zoom: 11.5, pitch: 45, bearing: 0 })}
          title="Reset Camera view"
          className="w-8 h-8 flex items-center justify-center rounded bg-block-lime text-primary hover:bg-block-lime/90 active:scale-95 transition-all cursor-pointer"
        >
          <Compass size={15} />
        </button>
      </div>
    </div>
  )
}
