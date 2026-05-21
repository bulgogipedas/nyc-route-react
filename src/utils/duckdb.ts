import * as duckdb from '@duckdb/duckdb-wasm'

let db: duckdb.AsyncDuckDB | null = null
let conn: duckdb.AsyncDuckDBConnection | null = null

export async function initDuckDB() {
  if (db && conn) return { db, conn }

  try {
    const JSDELIVR_BUNDLES = duckdb.getJsDelivrBundles()
    const bundle = await duckdb.selectBundle(JSDELIVR_BUNDLES)

    const worker_url = URL.createObjectURL(
      new Blob([`importScripts("${bundle.mainWorker}");`], { type: 'text/javascript' })
    )

    const worker = new Worker(worker_url)
    const logger = new duckdb.ConsoleLogger()

    db = new duckdb.AsyncDuckDB(logger, worker)
    await db.instantiate(bundle.mainModule, bundle.pthreadWorker)

    conn = await db.connect()
    
    // Register the parquet file in the DB virtual filesystem
    console.log('DuckDB initialized. Registering trips Parquet file...')
    await db.registerFileURL(
      'trips_sample.parquet',
      `${window.location.origin}/data/trips_sample.parquet`,
      duckdb.DuckDBDataProtocol.HTTP,
      false
    )
    console.log('Parquet file registered successfully in DuckDB!')
    
    return { db, conn }
  } catch (error) {
    console.error('Failed to initialize DuckDB-WASM:', error)
    throw error
  }
}

export async function getDuckDB() {
  if (!conn) {
    const res = await initDuckDB()
    return res
  }
  return { db, conn }
}
