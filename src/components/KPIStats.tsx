import { useStore } from '../store/useStore'

export default function KPIStats() {
  const { stats, isLoading } = useStore()

  if (isLoading && !stats) {
    return (
      <div className="grid grid-cols-4 gap-4 w-full h-[120px] animate-pulse">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-primary/10 rounded-sm border border-hairline/10 h-full" />
        ))}
      </div>
    )
  }

  // Format currency helper
  const formatRevenue = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0,
    }).format(value)
  }

  const kpis = [
    {
      title: 'TOTAL TRIP VOLUME',
      value: stats ? `${(stats.total_trips / 1000000).toFixed(2)}M` : '2.96M',
      valueClass: 'text-[34px]',
      bgColor: 'bg-block-lime',
      textColor: 'text-primary',
    },
    {
      title: 'AVG TRIP DISTANCE',
      value: stats ? `${stats.avg_distance.toFixed(2)} mi` : '4.53 mi',
      valueClass: 'text-[34px]',
      bgColor: 'bg-block-mint',
      textColor: 'text-primary',
    },
    {
      title: 'PEAK PICKUP HOUR',
      value: stats ? `${String(stats.peak_hour).padStart(2, '0')}:00` : '18:00',
      valueClass: 'text-[34px]',
      bgColor: 'bg-block-lilac',
      textColor: 'text-primary',
    },
    {
      title: 'TOTAL REVENUE',
      value: stats ? formatRevenue(stats.total_revenue) : '$69.08M',
      valueClass: 'text-[26px] xl:text-[30px]',
      bgColor: 'bg-block-pink',
      textColor: 'text-primary',
    },
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 w-full">
      {kpis.map((kpi, idx) => (
        <div
          key={idx}
          className={`${kpi.bgColor} ${kpi.textColor} p-5 rounded-md border border-primary/10 flex flex-col justify-between h-[120px] min-w-0 transition-transform hover:-translate-y-0.5`}
        >
          <div className="text-[11px] font-mono tracking-eyebrow font-400 uppercase opacity-75">
            {kpi.title}
          </div>
          <div className={`${kpi.valueClass} font-340 leading-none mt-2 whitespace-nowrap tracking-normal`}>
            {kpi.value}
          </div>
        </div>
      ))}
    </div>
  )
}
