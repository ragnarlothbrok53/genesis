import { NavLink } from "react-router-dom"
import { Activity, ShieldCheck, Users } from "lucide-react"

import { cn } from "@/lib/utils"
import { AdminRoutes } from "@/admin/AdminRoutes"

const sections = [
  { to: "/admin/users", label: "Users", icon: Users },
  { to: "/admin/permissions", label: "Permissions", icon: ShieldCheck },
  { to: "/admin/dev-tools", label: "Dev tools", icon: Activity },
]

export function AdminLayout() {
  return (
    <div className="flex gap-8">
      <aside className="w-48 shrink-0 space-y-1">
        <p className="px-3 pb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Admin
        </p>
        {sections.map((section) => {
          const Icon = section.icon
          return (
            <NavLink
              key={section.to}
              to={section.to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm text-muted-foreground hover:bg-accent hover:text-foreground",
                  isActive && "bg-accent text-foreground"
                )
              }
            >
              <Icon className="size-4" /> {section.label}
            </NavLink>
          )
        })}
      </aside>
      <div className="min-w-0 flex-1">
        <AdminRoutes />
      </div>
    </div>
  )
}
