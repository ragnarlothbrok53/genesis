import { useState } from "react"
import { Navigate } from "react-router-dom"
import { LogIn } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { useUser } from "@/hooks/useUser"

export const route = "/auth"
export const nav = { label: "Sign in", icon: LogIn, order: 99 }

export default function Auth() {
  const { user, login, signup } = useUser()
  const [mode, setMode] = useState<"login" | "signup">("login")
  const [email, setEmail] = useState("")
  const [name, setName] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")

  if (user) return <Navigate to="/" replace />

  const submit = async () => {
    setError("")
    try {
      if (mode === "signup") {
        await signup(email, name, password)
      } else {
        await login(email, password)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong")
    }
  }

  return (
    <Card className="mx-auto max-w-sm">
      <CardHeader>
        <CardTitle>{mode === "login" ? "Sign in" : "Create an account"}</CardTitle>
        <CardDescription>Email/password auth via bcrypt + JWT session cookie</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {mode === "signup" && (
          <Input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
        )}
        <Input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button className="w-full" onClick={submit}>
          {mode === "login" ? "Sign in" : "Sign up"}
        </Button>
        <button
          type="button"
          className="w-full text-center text-sm text-muted-foreground hover:underline"
          onClick={() => setMode(mode === "login" ? "signup" : "login")}
        >
          {mode === "login" ? "Need an account? Sign up" : "Already have an account? Sign in"}
        </button>
      </CardContent>
    </Card>
  )
}
