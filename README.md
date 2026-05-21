# ChronoRoute

ChronoRoute is an interactive visual analytics dashboard for NYC Yellow Taxi movement in Manhattan. It helps users inspect hourly taxi activity, identify areas that need more taxis, spot areas where taxis are accumulating, and understand major passenger movement corridors.

The app uses official NYC Taxi & Limousine Commission Yellow Taxi Trip Record Data for January, February, and March 2026, with March 2026 selected by default as the latest available month. It runs fully in the browser: compact TLC-derived trip path extracts are queried locally with DuckDB-WASM, while full-month aggregates are precomputed for the analytics panels.

## Features

- Interactive Manhattan taxi map with animated trip paths.
- Month selector for January, February, and March 2026 data.
- Hotspot layer showing where taxis are needed or where excess taxis are building up.
- Plain-language hover tooltips with pickup count, dropoff count, priority, and suggested dispatch action.
- Optional 3D hotspot height to make stronger imbalances easier to see.
- Passenger corridor layer for high-volume origin-to-destination flows.
- Current-hour analytics brief with demand level, zone counts, and strongest corridor volume.
- KPI cards for cumulative trip volume, average trip distance, peak pickup hour, and revenue.
- Timeline control for scrubbing or autoplaying through the 24-hour cycle.

## Tech Stack

- React 19
- TypeScript
- Vite
- Bun
- Tailwind CSS
- DuckDB-WASM
- Deck.gl
- MapLibre GL
- H3 spatial indexing
- Zustand
- Recharts
- Lucide React

## Getting Started

Install dependencies:

```bash
bun install
```

Run the development server:

```bash
bun run dev
```

Open the local URL printed by Vite, usually:

```text
http://localhost:5173/
```

Build for production:

```bash
bun run build
```

Preview the production build:

```bash
bun run preview
```

## Deploy

This is a Vite static app and can be deployed to Vercel or Netlify.

Vercel:

- Framework preset: Vite
- Build command: `bun run build`
- Output directory: `dist`
- SPA rewrites and cache headers are configured in `vercel.json`.

Netlify:

- Build command: `bun run build`
- Publish directory: `dist`
- SPA redirects and cache headers are configured in `netlify.toml` and `public/_redirects`.

After choosing the final production domain, add an absolute canonical URL and sitemap URL for stronger search indexing.

## How To Read The Dashboard

Pink map areas mean pickups are outpacing nearby dropoffs. These areas likely need more taxis.

Lime map areas mean dropoffs are outpacing pickups. These areas may have excess taxis that should relocate toward demand.

Flow lines show strong passenger movement corridors. Use them to understand where riders are pulling vehicles next.

The current-hour brief in the sidebar summarizes the selected hour so users do not need to interpret every map layer manually.

## Project Structure

```text
src/
  components/
    KPIStats.tsx          Top KPI cards
    MapContainer.tsx      Map, Deck.gl layers, hover tooltips
    SidebarControls.tsx   Layer controls, legend, analytics brief, hourly chart
    TimeSlider.tsx        Hour controls and autoplay
  store/
    useStore.ts           Global UI and data state
  utils/
    dataService.ts        Data loading and hourly aggregation
    duckdb.ts             DuckDB-WASM setup
public/
  data/                   TLC-derived monthly path extracts and aggregate datasets
scripts/
  preprocess.py           Data preprocessing helper
```

## Data Source

The source data comes from the official [NYC TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) page. TLC publishes trip record datasets monthly in Parquet format. The files used here are:

- `yellow_tripdata_2026-01.parquet`
- `yellow_tripdata_2026-02.parquet`
- `yellow_tripdata_2026-03.parquet`

Only Yellow Taxi trips with both pickup and dropoff locations in Manhattan are retained for this dashboard.

TLC notes that yellow and green taxi trip records include pickup/dropoff dates and times, pickup/dropoff locations, trip distances, fares, rate types, payment types, and passenger counts. TLC also notes that the trip data is collected from authorized technology providers and is not created by TLC.

## Data Pipeline

The raw TLC Parquet files are batch-processed into browser-ready artifacts:

- `trip_paths.parquet`: TLC-derived trip path extract for interactive map animation and hover analysis.
- `months.json`: available month metadata.
- `hourly_volume_by_month.json`: full-month hourly aggregates for the analytics chart and KPI calculations.
- `stats.json`: latest-month startup stats.
- `h3_deadhead.json` and `od_flows.json`: latest-month startup map layers before interactive filtering runs.

The animated map uses the compact path extract so the browser stays responsive. KPI cards and hourly volume analytics use precomputed aggregates from the full filtered monthly TLC datasets.
