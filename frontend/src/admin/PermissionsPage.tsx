import { useCallback, useEffect, useState } from "react"
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table"
import { Plus, Trash2 } from "lucide-react"

import { ApiError, api, type Schema } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

type PermissionRule = Schema<"PermissionRuleRead">

const METHODS = ["*", "GET", "POST", "PATCH", "DELETE"]

const columnHelper = createColumnHelper<PermissionRule>()

export function PermissionsPage() {
  const [rules, setRules] = useState<PermissionRule[]>([])
  const [routes, setRoutes] = useState<string[]>([])
  const [method, setMethod] = useState(METHODS[0])
  const [path, setPath] = useState("")
  const [role, setRole] = useState("")

  const load = useCallback(
    () =>
      api
        .get<PermissionRule[]>("/api/v1/admin/permissions")
        .then(setRules)
        .catch((err) => {
          if (err instanceof ApiError && err.status === 403) return
          throw err
        }),
    []
  )
  useEffect(() => {
    load()
    api.get<string[]>("/api/v1/admin/permissions/routes").then(setRoutes)
  }, [load])

  const addRule = async () => {
    if (!path.trim() || !role.trim()) return
    await api.post("/api/v1/admin/permissions", { method, path, role })
    setRole("")
    load()
  }

  const removeRule = async (id: number) => {
    await api.del(`/api/v1/admin/permissions/${id}`)
    load()
  }

  const columns = [
    columnHelper.accessor("method", { header: "Method" }),
    columnHelper.accessor("path", { header: "Path" }),
    columnHelper.accessor("role", { header: "Role" }),
    columnHelper.display({
      id: "actions",
      header: "",
      cell: ({ row }) => (
        <Button size="sm" variant="ghost" onClick={() => removeRule(row.original.id)}>
          <Trash2 />
        </Button>
      ),
    }),
  ]

  const table = useReactTable({ data: rules, columns, getCoreRowModel: getCoreRowModel() })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Permissions</CardTitle>
        <CardDescription>
          Restrict an endpoint to specific roles. No rule means everyone can call it.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <select
            className="h-9 rounded-md border bg-background px-2 text-sm"
            value={method}
            onChange={(e) => setMethod(e.target.value)}
          >
            {METHODS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <select
            className="h-9 flex-1 rounded-md border bg-background px-2 text-sm"
            value={path}
            onChange={(e) => setPath(e.target.value)}
          >
            <option value="">Select a route…</option>
            {routes.map((route) => (
              <option key={route} value={route}>
                {route}
              </option>
            ))}
          </select>
          <Input
            className="w-40"
            placeholder="Required role"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addRule()}
          />
          <Button onClick={addRule}>
            <Plus /> Add rule
          </Button>
        </div>
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((group) => (
              <TableRow key={group.id}>
                {group.headers.map((header) => (
                  <TableHead key={header.id}>
                    {flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.map((row) => (
              <TableRow key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
