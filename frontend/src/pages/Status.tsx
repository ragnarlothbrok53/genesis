import { HeartPulse } from "lucide-react"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useServices } from "@/hooks/useServices"
import { cn } from "@/lib/utils"

const labels: Record<string, string> = {
  database: "Database",
  observability: "Observability",
  llm: "LLM",
  jobs: "Background jobs",
}

const labelFor = (name: string) => labels[name] ?? name[0].toUpperCase() + name.slice(1)

export const route = "/status"
export const nav = { label: "Status", icon: HeartPulse, order: 5 }

export default function Status() {
  const services = useServices(3000) ?? []

  return (
    <Card>
      <CardHeader>
        <CardTitle>Service Status</CardTitle>
        <CardDescription>Live health of platform dependencies, polled every 3s</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {services.map(({ name, up }) => (
          <div key={name} className="flex items-center justify-between text-sm">
            <span>{labelFor(name)}</span>
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">{up ? "Up" : "Down"}</span>
              <span
                className={cn("h-2.5 w-2.5 rounded-full", up ? "bg-green-500" : "bg-red-500")}
              />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
