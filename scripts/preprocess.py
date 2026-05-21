import pandas as pd
import json
import h3
import os
import numpy as np
from calendar import month_name

# Paths
DATA_DIR = 'data'
OUTPUT_DIR = 'public/data'
ZONE_LOOKUP = os.path.join(DATA_DIR, 'taxi_zone_lookup.csv')
ZONES_GEOJSON = os.path.join(DATA_DIR, 'taxi_zones.json')
TRIP_FILES = [
    os.path.join(DATA_DIR, 'yellow_tripdata_2026-01.parquet'),
    os.path.join(DATA_DIR, 'yellow_tripdata_2026-02.parquet'),
    os.path.join(DATA_DIR, 'yellow_tripdata_2026-03.parquet'),
]
TLC_TRIP_RECORD_DATA_URL = 'https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page'
INTERACTIVE_RECORDS_PER_MONTH = 30000

os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_centroids():
    with open(ZONES_GEOJSON) as f:
        geojson = json.load(f)
    
    centroids = {}
    for feature in geojson['features']:
        props = feature['properties']
        loc_id = props.get('location_id') or props.get('objectid')
        
        if not loc_id:
            continue
            
        geom = feature['geometry']
        if geom['type'] == 'Polygon':
            coords = np.array(geom['coordinates'][0])
        elif geom['type'] == 'MultiPolygon':
            coords = np.array(geom['coordinates'][0][0])
        else:
            continue
            
        centroid = coords.mean(axis=0)
        centroids[int(loc_id)] = centroid.tolist()
    return centroids

def preprocess():
    print("Loading taxi zone lookup...")
    lookup = pd.read_csv(ZONE_LOOKUP)
    manhattan_zones = lookup[lookup['Borough'] == 'Manhattan']['LocationID'].tolist()
    centroids = get_centroids()

    interactive_exports = []
    months = []
    monthly_stats = {}
    hourly_volume_by_month = {}

    def get_coords_json(row):
        pu = centroids.get(row['PULocationID'])
        do = centroids.get(row['DOLocationID'])
        if pu and do:
            # timestamp in seconds from midnight
            t1 = row['tpep_pickup_datetime'].hour * 3600 + row['tpep_pickup_datetime'].minute * 60 + row['tpep_pickup_datetime'].second
            t2 = row['tpep_dropoff_datetime'].hour * 3600 + row['tpep_dropoff_datetime'].minute * 60 + row['tpep_dropoff_datetime'].second
            if t2 <= t1: t2 = t1 + 600  # default 10 mins if error
            return json.dumps([[pu[0], pu[1], t1], [do[0], do[1], t2]])
        return None

    for path in TRIP_FILES:
        month_id = os.path.basename(path).replace('yellow_tripdata_', '').replace('.parquet', '')
        year, month_num = month_id.split('-')
        month_label = f"{month_name[int(month_num)]} {year}"

        print(f"Loading {month_label}...")
        df = pd.read_parquet(path)
        df = df[df['PULocationID'].isin(manhattan_zones) & df['DOLocationID'].isin(manhattan_zones)].copy()
        df['hour'] = df['tpep_pickup_datetime'].dt.hour
        print(f"Filtered {month_label} to {len(df)} Manhattan trips.")

        hourly = df.groupby('hour').agg(
            trip_count=('VendorID', 'size'),
            total_distance=('trip_distance', 'sum'),
            total_revenue=('total_amount', 'sum'),
        ).reindex(range(24), fill_value=0).reset_index()

        hourly_volume_by_month[month_id] = [
            {
                'hour': int(row.hour),
                'count': int(row.trip_count),
                'total_distance': float(row.total_distance),
                'total_revenue': float(row.total_revenue),
            }
            for row in hourly.itertuples(index=False)
        ]

        stats = {
            'total_trips': int(len(df)),
            'avg_distance': float(df['trip_distance'].mean()),
            'peak_hour': int(hourly.sort_values('trip_count', ascending=False).iloc[0]['hour']),
            'total_revenue': float(df['total_amount'].sum()),
        }
        monthly_stats[month_id] = stats
        months.append({
            'id': month_id,
            'label': month_label,
            'source': 'NYC Taxi & Limousine Commission Yellow Taxi Trip Records',
            'source_url': TLC_TRIP_RECORD_DATA_URL,
            'source_file': os.path.basename(path),
            **stats,
        })

        print(f"Generating {month_label} browser-ready trip path extract...")
        interactive_df = df.sample(min(INTERACTIVE_RECORDS_PER_MONTH, len(df)), random_state=int(month_num)).copy()
        interactive_df['path'] = interactive_df.apply(get_coords_json, axis=1)
        interactive_df = interactive_df.dropna(subset=['path'])

        export_df = interactive_df[[
            'VendorID',
            'hour',
            'trip_distance',
            'fare_amount',
            'path',
        ]].copy()
        export_df.columns = ['vendor', 'hour', 'trip_distance', 'fare', 'path']
        export_df.insert(0, 'month', month_id)
        interactive_exports.append(export_df)

    interactive_records = pd.concat(interactive_exports, ignore_index=True)
    interactive_records.to_parquet(os.path.join(OUTPUT_DIR, 'trip_paths.parquet'), index=False)
    print(f"Exported {len(interactive_records)} browser-ready trip paths across {len(months)} months.")

    latest_month = months[-1]['id']
    latest_interactive_records = interactive_records[interactive_records['month'] == latest_month]

    # Legacy/static startup files use the latest available month. Interactive views
    # recalculate hotspots and flows by month/hour from trip_paths.parquet.
    print(f"Generating latest-month startup layers for {latest_month}...")
    pu_counts = {}
    do_counts = {}
    od_counts = {}
    for row in latest_interactive_records.itertuples(index=False):
        segments = json.loads(row.path)
        if not segments or len(segments) < 2:
            continue
        pu_lon, pu_lat = segments[0][0], segments[0][1]
        do_lon, do_lat = segments[-1][0], segments[-1][1]
        pu_h3 = h3.latlng_to_cell(pu_lat, pu_lon, 8)
        do_h3 = h3.latlng_to_cell(do_lat, do_lon, 8)
        pu_counts[pu_h3] = pu_counts.get(pu_h3, 0) + 1
        do_counts[do_h3] = do_counts.get(do_h3, 0) + 1

        pu_h3_7 = h3.latlng_to_cell(pu_lat, pu_lon, 7)
        do_h3_7 = h3.latlng_to_cell(do_lat, do_lon, 7)
        flow_key = f"{pu_h3_7}->{do_h3_7}"
        od_counts[flow_key] = od_counts.get(flow_key, 0) + 1

    h3_data = []
    for cell in sorted(set(pu_counts.keys()) | set(do_counts.keys())):
        pickups = int(pu_counts.get(cell, 0))
        dropoffs = int(do_counts.get(cell, 0))
        h3_data.append({
            'h3': cell,
            'pickups': pickups,
            'dropoffs': dropoffs,
            'deadhead_metric': dropoffs - pickups,
        })

    od_data = []
    for key, count in sorted(od_counts.items(), key=lambda item: item[1], reverse=True)[:400]:
        from_h3, to_h3 = key.split('->')
        from_lat_lng = h3.cell_to_latlng(from_h3)
        to_lat_lng = h3.cell_to_latlng(to_h3)
        od_data.append({
            'from': [from_lat_lng[1], from_lat_lng[0]],
            'to': [to_lat_lng[1], to_lat_lng[0]],
            'count': int(count),
        })

    with open(os.path.join(OUTPUT_DIR, 'months.json'), 'w') as f:
        json.dump(months, f)
    with open(os.path.join(OUTPUT_DIR, 'monthly_stats.json'), 'w') as f:
        json.dump(monthly_stats, f)
    with open(os.path.join(OUTPUT_DIR, 'hourly_volume_by_month.json'), 'w') as f:
        json.dump(hourly_volume_by_month, f)
    with open(os.path.join(OUTPUT_DIR, 'h3_deadhead.json'), 'w') as f:
        json.dump(h3_data, f)
    with open(os.path.join(OUTPUT_DIR, 'od_flows.json'), 'w') as f:
        json.dump(od_data, f)
    with open(os.path.join(OUTPUT_DIR, 'stats.json'), 'w') as f:
        json.dump(monthly_stats[latest_month], f)
    print(f"Latest month is {latest_month}: {monthly_stats[latest_month]}")

    print("Preprocessing complete!")

if __name__ == "__main__":
    preprocess()
