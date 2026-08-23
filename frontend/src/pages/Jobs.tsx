import { useEffect, useState } from "react"
import { Loader2, Workflow } from "lucide-react"

import { api, type Schema } from "@/lib/api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

type JobStatus = Schema<"JobStatus">

export const route = "/jobs"
export const nav = { label: "Jobs", icon: Workflow, order: 2 }

export default function Jobs() {
  const [job, setJob] = useState<JobStatus | null>(null)
  const [running, setRunning] = useState(false)

  useEffect(() => {
    if (!job || !running) return
    const timer = setInterval(async () => {
      const status = await api.get<JobStatus>(`/api/v1/jobs/${job.workflow_id}`)
      setJob(status)
      if (status.status === "COMPLETED" || status.status === "FAILED") setRunning(false)
    }, 1000)
    return () => clearInterval(timer)
  }, [job, running])

  const start = async () => {
    const status = await api.post<JobStatus>("/api/v1/jobs", { seconds: 3 })
    setJob(status)
    setRunning(true)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Background Job</CardTitle>
        <CardDescription>Durable Temporal workflow, polled for status</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Button onClick={start} disabled={running}>
          {running && <Loader2 className="animate-spin" />} Run 3s workflow
        </Button>
        {job && (
          <div className="flex items-center gap-2 text-sm">
            <Badge variant={job.status === "COMPLETED" ? "default" : "secondary"}>
              {job.status}
            </Badge>
            <span className="text-muted-foreground">{job.result ?? job.workflow_id}</span>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
