import { createContext, useCallback, useContext, useEffect, useState } from "react"
import type { ReactNode } from "react"

import { api, type Schema } from "@/lib/api"

export type User = Schema<"CurrentUser">

type AuthState = {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  signup: (email: string, name: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(
    () => api.get<User>("/api/me").then(setUser).catch(() => setUser(null)),
    []
  )

  useEffect(() => {
    refresh().finally(() => setLoading(false))
  }, [refresh])

  const login = useCallback(
    async (email: string, password: string) => {
      await api.post("/api/v1/auth/login", { email, password })
      await refresh()
    },
    [refresh]
  )

  const signup = useCallback(
    async (email: string, name: string, password: string) => {
      await api.post("/api/v1/auth/signup", { email, name, password })
      await refresh()
    },
    [refresh]
  )

  const logout = useCallback(async () => {
    await api.post("/api/v1/auth/logout")
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useUser() {
  const context = useContext(AuthContext)
  if (!context) throw new Error("useUser must be used within an AuthProvider")
  return context
}
