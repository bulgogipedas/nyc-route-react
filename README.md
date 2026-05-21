# ChronoRoute

ChronoRoute is an interactive visual analytics dashboard for NYC Yellow Taxi movement in Manhattan. It helps users inspect hourly taxi activity, identify areas that need more taxis, spot areas where taxis are accumulating, and understand major passenger movement corridors.

The app runs fully in the browser. Trip samples are queried locally with DuckDB-WASM, while the map experience is rendered with Deck.gl and MapLibre.

## Features

- Interactive Manhattan taxi map with animated trip paths.
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
  data/                   Preprocessed sample datasets
scripts/
  preprocess.py           Data preprocessing helper
```

## Data Notes

The included data is a compact sample prepared for browser-based exploration. Values shown in the dashboard are intended for product demonstration and visual analysis, not official transportation reporting.
