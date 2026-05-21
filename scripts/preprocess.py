import pandas as pd
import json
import h3
import os
import numpy as np
from datetime import datetime

# Paths
DATA_DIR = 'data'
OUTPUT_DIR = 'public/data'
ZONE_LOOKUP = os.path.join(DATA_DIR, 'taxi_zone_lookup.csv')
ZONES_GEOJSON = os.path.join(DATA_DIR, 'taxi_zones.json')
TRIP_DATA = os.path.join(DATA_DIR, 'yellow_tripdata_2026-01.parquet')

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
    print("Loading data...")
    df = pd.read_parquet(TRIP_DATA)
    lookup = pd.read_csv(ZONE_LOOKUP)
    
    # Filter for Manhattan
    manhattan_zones = lookup[lookup['Borough'] == 'Manhattan']['LocationID'].tolist()
    df = df[df['PULocationID'].isin(manhattan_zones) & df['DOLocationID'].isin(manhattan_zones)].copy()
    
    print(f"Filtered to {len(df)} Manhattan trips.")
    
    centroids = get_centroids()
    
    # 1. Trips Sample for TripsLayer (Parquet output for DuckDB-WASM)
    print("Generating trips data for trips_sample.parquet...")
    sample_df = df.sample(min(30000, len(df))).copy()
    
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

    sample_df['path'] = sample_df.apply(get_coords_json, axis=1)
    sample_df = sample_df.dropna(subset=['path'])
    
    # Extract hour of day
    sample_df['hour'] = sample_df['tpep_pickup_datetime'].dt.hour
    
    # Prepare parquet columns
    export_df = sample_df[[
        'VendorID', 
        'hour', 
        'trip_distance', 
        'fare_amount', 
        'path'
    ]].copy()
    export_df.columns = ['vendor', 'hour', 'trip_distance', 'fare', 'path']
    
    export_df.to_parquet(os.path.join(OUTPUT_DIR, 'trips_sample.parquet'), index=False)
    print(f"Exported {len(export_df)} sample trips to parquet.")

    # 2. OD Flows (ArcLayer)
    print("Generating OD flows...")
    od_counts = df.groupby(['PULocationID', 'DOLocationID']).size().reset_index(name='count')
    od_counts = od_counts.sort_values('count', ascending=False).head(1500)
    
    od_data = []
    for _, row in od_counts.iterrows():
        pu = centroids.get(row['PULocationID'])
        do = centroids.get(row['DOLocationID'])
        if pu and do:
            od_data.append({
                'from': pu,
                'to': do,
                'count': int(row['count'])
            })
            
    with open(os.path.join(OUTPUT_DIR, 'od_flows.json'), 'w') as f:
        json.dump(od_data, f)
    print(f"Exported {len(od_data)} OD flow arcs.")

    # 3. H3 Aggregation (H3HexagonLayer for Deadhead Density)
    print("Generating H3 deadhead aggregation...")
    # Map coordinates to H3 cells for pickups and dropoffs (optimized dictionary map)
    zone_to_h3 = {loc_id: h3.latlng_to_cell(coords[1], coords[0], 8) for loc_id, coords in centroids.items()}
    df['pu_h3'] = df['PULocationID'].map(zone_to_h3)
    df['do_h3'] = df['DOLocationID'].map(zone_to_h3)

    
    # Pickups count per H3 cell
    pu_counts = df['pu_h3'].value_counts().reset_index(name='pickups')
    pu_counts.columns = ['h3', 'pickups']
    
    # Dropoffs count per H3 cell
    do_counts = df['do_h3'].value_counts().reset_index(name='dropoffs')
    do_counts.columns = ['h3', 'dropoffs']
    
    # Merge and calculate deadhead index (dropoffs - pickups)
    h3_df = pd.merge(pu_counts, do_counts, on='h3', how='outer').fillna(0)
    h3_df['pickups'] = h3_df['pickups'].astype(int)
    h3_df['dropoffs'] = h3_df['dropoffs'].astype(int)
    h3_df['deadhead_metric'] = h3_df['dropoffs'] - h3_df['pickups']
    h3_df = h3_df.dropna(subset=['h3'])
    
    h3_data = h3_df.to_dict(orient='records')
    with open(os.path.join(OUTPUT_DIR, 'h3_deadhead.json'), 'w') as f:
        json.dump(h3_data, f)
    print(f"Exported H3 data for {len(h3_data)} cells.")

    # 4. Stats
    print("Generating stats...")
    stats = {
        'total_trips': len(df),
        'avg_distance': float(df['trip_distance'].mean()),
        'peak_hour': int(df['tpep_pickup_datetime'].dt.hour.mode()[0]),
        'total_revenue': float(df['total_amount'].sum())
    }
    with open(os.path.join(OUTPUT_DIR, 'stats.json'), 'w') as f:
        json.dump(stats, f)
    print(f"Exported stats: {stats}")

    print("Preprocessing complete!")

if __name__ == "__main__":
    preprocess()
