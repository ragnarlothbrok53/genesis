import { useEffect, useState } from "react"

import { api, type Schema } from "@/lib/api"

export type Service = Schema<"ServiceStatus">

export function useServices(pollMs?: number) {
  const [services, setServices] = useState<Service[] | null>(null)

  useEffect(() => {
    const load = () =>
      api
        .get<Schema<"Status">>("/api/status")
        .then((data) => setServices(data.services))
        .catch(() => setServices([]))
    load()
    if (!pollMs) return
    const timer = setInterval(load, pollMs)
    return () => clearInterval(timer)
  }, [pollMs])

  return services
}
