import { useState, useEffect } from 'react'
import DeckGL from '@deck.gl/react'
import Map from 'react-map-gl/maplibre'
import { TripsLayer } from '@deck.gl/geo-layers'
import { H3HexagonLayer } from '@deck.gl/geo-layers'
import { ArcLayer } from '@deck.gl/layers'
import { useStore } from '../store/useStore'
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

interface HoverInfo {
  x: number
  y: number
  object: any
  layerId: string
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
    setCurrentTime(timeHour * 3600)
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

  // DeckGL Layers definition
  const layers = [
    showH3 && h3Data.length > 0 && new H3HexagonLayer({
      id: 'h3-layer',
      data: h3Data,
      pickable: true,
      wireframe: true,
      filled: true,
      extruded: use3D,
      elevationScale: 1,
      getHexagon: (d: any) => d.h3,
      // Normalize colors dynamically based on current hour's maximum metric
      getFillColor: (d: any) => {
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
      getElevation: (d: any) => {
        const val = Math.abs(d.deadhead_metric)
        return Math.pow(val / maxVal, 0.7) * 1200
      },
      onHover: (info: any) => {
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

    showArc && odFlows.length > 0 && new ArcLayer({
      id: 'arc-layer',
      data: odFlows,
      pickable: true,
      // Scale arc width dynamically between 1 and 6 pixels
      getWidth: (d: any) => 1 + (d.count / maxFlow) * 5,
      getSourcePosition: (d: any) => d.from,
      getTargetPosition: (d: any) => d.to,
      // Source color (pickup) is magenta, target (dropoff) is lime yellow
      getSourceColor: (d: any) => [255, 51, 204, Math.floor(80 + 175 * (d.count / maxFlow))],
      getTargetColor: (d: any) => [210, 255, 0, Math.floor(80 + 175 * (d.count / maxFlow))],
      getHeight: 0.5,
      tilt: 15,
      onHover: (info: any) => {
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

    showTrips && trips.length > 0 && new TripsLayer({
      id: 'trips-layer',
      data: trips,
      // Map path to [lng, lat] to prevent Deck.gl from treating the 3rd index (timestamp) as a Z-altitude coordinate
      getPath: (d: any) => d.segments.map((p: any) => [p[0], p[1]]),
      getTimestamps: (d: any) => d.segments.map((p: any) => p[2]),
      // CMT Vendor 1 = Electric Pink, Verifone Vendor 2 = Neon Mint
      getColor: (d: any) => d.vendor === 1 ? [255, 51, 204] : [0, 245, 212],
      opacity: 0.95,
      widthMinPixels: 2.5,
      trailLength: 180,
      currentTime: currentTime,
      shadowEnabled: false,
    })
  ].filter(Boolean) as any[]

  return (
    <div className="relative w-full h-full bg-block-navy overflow-hidden">
      <DeckGL
        viewState={mapState}
        onViewStateChange={(e: any) => setMapState(e.viewState)}
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
          className="absolute z-50 p-4 bg-primary/95 text-canvas rounded-sm border border-hairline/25 shadow-lg backdrop-blur-md pointer-events-none transition-all duration-75"
          style={{ left: hoverInfo.x + 15, top: hoverInfo.y + 15 }}
        >
          {hoverInfo.layerId === 'h3' && (
            <div className="space-y-2">
              <div className="text-[12px] font-mono text-block-pink font-400">H3 HEXAGON CELL</div>
              <div className="text-[14px] font-mono font-bold text-canvas">{hoverInfo.object.h3}</div>
              <div className="h-px bg-hairline/20 my-1"></div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm font-sans">
                <span className="text-canvas/60">Pickups:</span>
                <span className="text-right font-bold text-block-mint">{hoverInfo.object.pickups}</span>
                <span className="text-canvas/60">Dropoffs:</span>
                <span className="text-right font-bold text-block-lilac">{hoverInfo.object.dropoffs}</span>
              </div>
              <div className="h-px bg-hairline/20 my-1"></div>
              <div className="text-sm font-sans flex items-center justify-between gap-4">
                <span className="text-canvas/60">Deadhead Metric:</span>
                <span className={`font-bold ${hoverInfo.object.deadhead_metric >= 0 ? 'text-block-lime' : 'text-block-pink'}`}>
                  {hoverInfo.object.deadhead_metric > 0 ? `+${hoverInfo.object.deadhead_metric}` : hoverInfo.object.deadhead_metric}
                </span>
              </div>
              <div className="text-[10px] font-sans text-canvas/50 italic max-w-[200px] mt-1">
                {hoverInfo.object.deadhead_metric > 0 
                  ? 'Surplus supply. Taxis must deadhead out of this zone.'
                  : 'Surplus demand. Taxis need to deadhead into this zone.'}
              </div>
            </div>
          )}

          {hoverInfo.layerId === 'arc' && (
            <div className="space-y-2">
              <div className="text-[12px] font-mono text-block-pink font-400">ORIGIN-DESTINATION FLOW</div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm font-sans">
                <span className="text-canvas/60">Flow Count:</span>
                <span className="text-right font-bold text-block-lime">{hoverInfo.object.count} trips</span>
              </div>
              <div className="h-px bg-hairline/20 my-1"></div>
              <div className="text-[10px] font-sans text-canvas/50 italic max-w-[200px]">
                Showing high-density flow between Manhattan centroids.
              </div>
            </div>
          )}
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
