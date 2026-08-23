import { Activity, Database } from "lucide-react"
import { Workflow } from "lucide-react" // module:jobs

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useServices } from "@/hooks/useServices"

const devTools = [
  { service: "dbgate", to: "/db", label: "Database", icon: Database },
  { service: "jobs", to: "/temporal/", label: "Workflows", icon: Workflow }, // module:jobs
  { service: "observability", to: "/o11y/web", label: "Telemetry", icon: Activity },
]

export function DevToolsPage() {
  const services = useServices()
  const up = new Set(services?.filter((s) => s.up).map((s) => s.name))
  const available = devTools.filter((tool) => up.has(tool.service))

  return (
    <Card>
      <CardHeader>
        <CardTitle>Dev tools</CardTitle>
        <CardDescription>Links to backing service dashboards, when reachable</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {available.length === 0 && (
          <p className="text-sm text-muted-foreground">No dev-tool services are reachable.</p>
        )}
        {available.map((tool) => {
          const Icon = tool.icon
          return (
            <a
              key={tool.to}
              href={tool.to}
              className="flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-accent"
            >
              <Icon className="size-4" /> {tool.label}
            </a>
          )
        })}
      </CardContent>
    </Card>
  )
}
