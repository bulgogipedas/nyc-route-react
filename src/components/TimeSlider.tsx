import { useState, useEffect } from 'react'
import { useStore } from '../store/useStore'
import { Play, Pause, ChevronLeft, ChevronRight } from 'lucide-react'

export default function TimeSlider() {
  const { timeHour, setTimeHour } = useStore()
  const [isPlaying, setIsPlaying] = useState(false)

  // Auto-play interval
  useEffect(() => {
    if (!isPlaying) return

    const interval = setInterval(() => {
      setTimeHour((timeHour + 1) % 24)
    }, 4000) // Advance hour every 4 seconds

    return () => clearInterval(interval)
  }, [isPlaying, timeHour, setTimeHour])

  const formatHourLabel = (h: number) => {
    return `${String(h).padStart(2, '0')}:00`
  }

  const handlePrev = () => {
    setTimeHour(timeHour === 0 ? 23 : timeHour - 1)
  }

  const handleNext = () => {
    setTimeHour((timeHour + 1) % 24)
  }

  return (
    <div className="bg-primary/95 text-canvas border border-hairline/15 rounded-md p-6 shadow-2xl backdrop-blur-md flex flex-col space-y-4">
      {/* Time Header with controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          {/* Play/Pause Button */}
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="w-10 h-10 rounded-full bg-block-lime hover:bg-block-lime/90 active:scale-95 text-primary flex items-center justify-center transition-all shadow-lg"
          >
            {isPlaying ? <Pause size={18} fill="currentColor" /> : <Play size={18} className="ml-0.5" fill="currentColor" />}
          </button>

          {/* Navigation Seek buttons */}
          <div className="flex items-center space-x-1">
            <button
              onClick={handlePrev}
              className="p-1 rounded bg-canvas/10 hover:bg-canvas/20 active:scale-95 transition-all text-canvas"
            >
              <ChevronLeft size={16} />
            </button>
            <button
              onClick={handleNext}
              className="p-1 rounded bg-canvas/10 hover:bg-canvas/20 active:scale-95 transition-all text-canvas"
            >
              <ChevronRight size={16} />
            </button>
          </div>

          <div className="text-[12px] font-mono tracking-eyebrow text-canvas/50">
            ACTIVE ANALYTICAL WINDOW
          </div>
        </div>

        {/* Big Time Display */}
        <div className="text-[32px] font-340 tracking-display-lg leading-none font-bold text-block-lime">
          {formatHourLabel(timeHour)}
        </div>
      </div>

      {/* Range Slider */}
      <div className="relative pt-2">
        <input
          type="range"
          min="0"
          max="23"
          value={timeHour}
          onChange={(e) => setTimeHour(Number(e.target.value))}
          className="w-full h-1 bg-canvas/20 rounded-lg appearance-none cursor-pointer accent-block-lime transition-all focus:outline-none"
        />

        {/* Ticks */}
        <div className="flex justify-between text-[10px] font-mono text-canvas/40 mt-3 px-1 select-none">
          {[...Array(24)].map((_, i) => (
            <span
              key={i}
              onClick={() => setTimeHour(i)}
              className={`cursor-pointer transition-colors ${
                i === timeHour ? 'text-block-lime font-bold scale-110' : 'hover:text-canvas'
              }`}
            >
              {i % 4 === 0 ? `${i}h` : '•'}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
