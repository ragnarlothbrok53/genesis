import { useCallback, useEffect, useState } from "react"
import { LayoutGrid, Plus, Trash2 } from "lucide-react"

import { ApiError, api, type Schema } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

type Item = Schema<"ItemRead">

export const route = "/"
export const nav = { label: "Items", icon: LayoutGrid, order: 1 }

export default function Items() {
  const [items, setItems] = useState<Item[]>([])
  const [name, setName] = useState("")

  const load = useCallback(
    () =>
      api.get<Item[]>("/api/v1/items").then(setItems).catch((err) => {
        if (err instanceof ApiError && err.status === 403) return
        throw err
      }),
    []
  )
  useEffect(() => {
    load()
  }, [load])

  const add = async () => {
    if (!name.trim()) return
    await api.post("/api/v1/items", { name })
    setName("")
    load()
  }

  const remove = async (id: number) => {
    await api.del(`/api/v1/items/${id}`)
    load()
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Items</CardTitle>
        <CardDescription>Postgres CRUD via FastAPI + Peewee</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Input
            placeholder="New item name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && add()}
          />
          <Button onClick={add}>
            <Plus /> Add
          </Button>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Created</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.id}>
                <TableCell>{item.id}</TableCell>
                <TableCell>{item.name}</TableCell>
                <TableCell>{new Date(item.created_at).toLocaleString()}</TableCell>
                <TableCell>
                  <Button variant="ghost" size="icon" onClick={() => remove(item.id)}>
                    <Trash2 />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
