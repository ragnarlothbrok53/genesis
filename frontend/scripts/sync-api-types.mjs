import { execFileSync } from "node:child_process"
import { writeFileSync, unlinkSync } from "node:fs"

const SCHEMA_URL = process.env.API_URL ?? "http://localhost:8000/api/openapi.json"
const TEMP_FILE = "openapi.json"
const OUTPUT = "src/lib/api-types.ts"

let schema
try {
  const response = await fetch(SCHEMA_URL)
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  schema = await response.text()
} catch (error) {
  console.warn(`api-types: backend unreachable at ${SCHEMA_URL} (${error.message}) — keeping committed types`)
  process.exit(0)
}

writeFileSync(TEMP_FILE, schema)
try {
  execFileSync("npx", ["openapi-typescript", TEMP_FILE, "-o", OUTPUT], {
    stdio: "inherit",
    shell: process.platform === "win32",
  })
} finally {
  unlinkSync(TEMP_FILE)
}
