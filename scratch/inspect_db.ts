import { getDuckDB } from '../src/utils/duckdb'

async function main() {
  console.log('Initializing DuckDB...')
  const { conn } = await getDuckDB()
  
  // Since we run in node, we need to register the file with a local path
  // but wait, we can register it using a file URL or relative path if it's on disk!
  // Actually, we can run a simple query on the parquet file directly using its local path:
  const parquetPath = '/Users/tamagoasin/Documents/01 project/chrono-route/public/data/trips_sample.parquet'
  
  console.log('Querying columns from parquet file:', parquetPath)
  const query = `DESCRIBE SELECT * FROM '${parquetPath}'`
  const result = await conn.query(query)
  console.log('Columns:')
  console.log(result.toArray().map(r => r.toJSON()))
  
  process.exit(0)
}

main().catch(console.error)
