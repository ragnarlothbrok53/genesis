import type { ReactNode } from "react"
import { Link, useLocation } from "react-router-dom"
import type { LucideIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { useUser } from "@/hooks/useUser"

type NavMeta = { label: string; icon: LucideIcon; order?: number }
type PageModule = { route?: string; nav?: NavMeta; requiredRole?: string }
type NavItem = { to: string; label: string; icon: LucideIcon; external: boolean; requiredRole?: string }

const pageModules = import.meta.glob<PageModule>("/src/pages/*.tsx", { eager: true })

const coreNavItems: NavItem[] = Object.values(pageModules)
  .filter((m): m is { route: string; nav: NavMeta; requiredRole?: string } => Boolean(m.route && m.nav))
  .sort((a, b) => (a.nav.order ?? 99) - (b.nav.order ?? 99))
  .map((m) => ({
    to: m.route,
    label: m.nav.label,
    icon: m.nav.icon,
    external: false,
    requiredRole: m.requiredRole,
  }))

function NavLink({ item, pathname }: { item: NavItem; pathname: string }) {
  const Icon = item.icon
  const active = !item.external && (pathname === item.to || pathname.startsWith(`${item.to}/`))
  const className = cn(
    "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm text-muted-foreground hover:bg-accent hover:text-foreground",
    active && "bg-accent text-foreground"
  )
  return item.external ? (
    <a href={item.to} className={className}>
      <Icon /> {item.label}
    </a>
  ) : (
    <Link to={item.to} className={className}>
      <Icon /> {item.label}
    </Link>
  )
}

export function Layout({ children }: { children: ReactNode }) {
  const location = useLocation()
  const { user, logout } = useUser()
  const visibleNavItems = coreNavItems.filter(
    (item) => !item.requiredRole || (user && user.roles.includes(item.requiredRole))
  )

  return (
    <div className="min-h-screen">
      <header className="border-b">
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
          <div className="flex items-center gap-6">
            <span className="text-lg font-semibold">Genesis</span>
            <nav className="flex items-center gap-1">
              {visibleNavItems.map((item) => (
                <NavLink key={item.to} item={item} pathname={location.pathname} />
              ))}
            </nav>
          </div>
          {user && (
            <div className="flex items-center gap-3">
              <span className="text-sm text-muted-foreground">{user.email}</span>
              <Button variant="outline" size="sm" onClick={() => logout()}>
                Log out
              </Button>
            </div>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
    </div>
  )
}
