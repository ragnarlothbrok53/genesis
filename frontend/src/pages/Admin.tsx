import { ShieldCheck } from "lucide-react"

import { AdminLayout } from "@/admin/AdminLayout"

export const route = "/admin/*"
export const nav = { label: "Admin", icon: ShieldCheck, order: 6 }
export const requiredRole = "admin"

export default function Admin() {
  return <AdminLayout />
}
