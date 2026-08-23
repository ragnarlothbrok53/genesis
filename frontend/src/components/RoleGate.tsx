import type { ReactNode } from "react"

import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useUser } from "@/hooks/useUser"

function AccessDenied() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Access denied</CardTitle>
        <CardDescription>You don't have permission to view this page.</CardDescription>
      </CardHeader>
    </Card>
  )
}

export function RoleGate({
  requiredRole,
  children,
}: {
  requiredRole?: string
  children: ReactNode
}) {
  const { user, loading } = useUser()

  if (!requiredRole) return <>{children}</>
  if (loading) return null
  if (!user || !user.roles.includes(requiredRole)) return <AccessDenied />
  return <>{children}</>
}
