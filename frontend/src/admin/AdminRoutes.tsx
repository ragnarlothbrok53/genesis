import { Navigate, Route, Routes } from "react-router-dom"

import { DevToolsPage } from "@/admin/DevToolsPage"
import { PermissionsPage } from "@/admin/PermissionsPage"
import { UsersPage } from "@/admin/UsersPage"

export function AdminRoutes() {
  return (
    <Routes>
      <Route index element={<Navigate to="users" replace />} />
      <Route path="users" element={<UsersPage />} />
      <Route path="permissions" element={<PermissionsPage />} />
      <Route path="dev-tools" element={<DevToolsPage />} />
    </Routes>
  )
}
