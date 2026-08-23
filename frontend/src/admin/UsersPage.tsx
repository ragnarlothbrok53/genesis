import { useCallback, useEffect, useState } from "react"
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table"

import { ApiError, api, type Schema } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

type AdminUser = Schema<"UserAdminRead">

const columnHelper = createColumnHelper<AdminUser>()

function RolesCell({ user, onSave }: { user: AdminUser; onSave: (roles: string[]) => void }) {
  const [value, setValue] = useState(user.roles.join(","))

  return (
    <div className="flex items-center gap-2">
      <Input
        className="h-8 w-40"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="admin,staff"
      />
      <Button
        size="sm"
        variant="outline"
        onClick={() =>
          onSave(
            value
              .split(",")
              .map((role) => role.trim())
              .filter(Boolean)
          )
        }
      >
        Save
      </Button>
    </div>
  )
}

export function UsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([])

  const load = useCallback(
    () =>
      api
        .get<AdminUser[]>("/api/v1/admin/users")
        .then(setUsers)
        .catch((err) => {
          if (err instanceof ApiError && err.status === 403) return
          throw err
        }),
    []
  )
  useEffect(() => {
    load()
  }, [load])

  const saveRoles = async (id: number, roles: string[]) => {
    await api.patch(`/api/v1/admin/users/${id}`, { roles })
    load()
  }

  const deactivate = async (id: number) => {
    await api.post(`/api/v1/admin/users/${id}/deactivate`)
    load()
  }

  const remove = async (id: number) => {
    if (!window.confirm("Delete this user? This cannot be undone.")) return
    await api.del(`/api/v1/admin/users/${id}`)
    load()
  }

  const columns = [
    columnHelper.accessor("id", { header: "ID" }),
    columnHelper.accessor("email", { header: "Email" }),
    columnHelper.accessor("name", { header: "Name" }),
    columnHelper.display({
      id: "roles",
      header: "Roles",
      cell: ({ row }) => (
        <RolesCell user={row.original} onSave={(roles) => saveRoles(row.original.id, roles)} />
      ),
    }),
    columnHelper.accessor("active", {
      header: "Active",
      cell: ({ getValue }) => (getValue() ? "yes" : "no"),
    }),
    columnHelper.display({
      id: "actions",
      header: "",
      cell: ({ row }) => (
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="outline" onClick={() => deactivate(row.original.id)}>
            Deactivate
          </Button>
          <Button size="sm" variant="outline" onClick={() => remove(row.original.id)}>
            Delete
          </Button>
        </div>
      ),
    }),
  ]

  const table = useReactTable({
    data: users,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Users</CardTitle>
        <CardDescription>Manage roles, deactivate or delete accounts</CardDescription>
      </CardHeader>
      <CardContent>
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
