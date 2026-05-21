# ChronoRoute Data Contract

## Supported Services

- `yellow`
- `green`
- `fhv`
- `fhvhv`

## Canonical Silver Columns

`service_type`, `pickup_datetime`, `dropoff_datetime`, `pickup_location_id`, `dropoff_location_id`, `trip_distance`, `fare_amount`, `passenger_count`, `base_license_number`, `dispatching_base_num`, `originating_base_num`, `month`, `pickup_date`, `pickup_hour`, `day_of_week`, `day_type`, `temporal_segment`, `duration_minutes`.

## Cross-Service Caveats

Yellow and Green taxi records include richer fare, passenger count, and distance fields. FHV and HVFHV files use different schemas, and some optional columns may be unavailable.

Use these metrics for safer cross-service comparison:

- Trip volume.
- Pickup and dropoff geography.
- Hourly and temporal-segment demand.
- OD spatial flow.
- Service share by trip count.

Treat fare and passenger-count comparisons as service-specific unless the source fields are verified for the target month.

## Existing Frontend Contract

The current dashboard expects:

- `public/data/trip_paths.parquet`
- `public/data/months.json`
- `public/data/hourly_volume_by_month.json`
- `public/data/stats.json`
- `public/data/h3_deadhead.json`
- `public/data/od_flows.json`

The new pipeline adds `public/data/metadata.json` without breaking these files.
