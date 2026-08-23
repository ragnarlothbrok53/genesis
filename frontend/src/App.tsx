import type { ComponentType } from "react"
import { Route, Routes } from "react-router-dom"

import { Layout } from "@/components/Layout"
import { RoleGate } from "@/components/RoleGate"

type PageModule = { default: ComponentType; route?: string; requiredRole?: string }

const modules = import.meta.glob<PageModule>("/src/pages/*.tsx", { eager: true })
const pages = Object.values(modules).filter((m) => m.route)

function NotFound() {
  return (
    <div className="space-y-2">
      <h1 className="text-lg font-semibold">Page not found</h1>
      <p className="text-sm text-muted-foreground">
        Add a file to <code>src/pages/</code> that exports a <code>route</code> to create this page.
      </p>
    </div>
  )
}

export default function App() {
  return (
    <Layout>
      <Routes>
        {pages.map((page) => (
          <Route
            key={page.route}
            path={page.route}
            element={
              <RoleGate requiredRole={page.requiredRole}>
                <page.default />
              </RoleGate>
            }
          />
        ))}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Layout>
  )
}
