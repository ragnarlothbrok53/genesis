import { useCallback, useEffect, useState } from "react"
import { BarChart3 } from "lucide-react"

import { api, type Schema } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

type Summary = Schema<"ItemsSummary">

export const route = "/analytics"
export const nav = { label: "Analytics", icon: BarChart3, order: 4 }

export default function Analytics() {
  const [summary, setSummary] = useState<Summary | null>(null)

  const load = useCallback(
    () =>
      api
        .get<Summary>("/api/v1/analytics/items-summary")
        .then(setSummary)
        .catch(() => setSummary(null)),
    []
  )

  useEffect(() => {
    load()
  }, [load])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Analytics</CardTitle>
        <CardDescription>DuckDB querying Postgres via the postgres extension</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <Button variant="outline" size="sm" onClick={load}>
          Refresh
        </Button>
        <p className="text-2xl font-semibold">{summary?.total ?? "—"}</p>
        <p className="text-sm text-muted-foreground">total items (aggregated by DuckDB)</p>
      </CardContent>
    </Card>
  )
}
