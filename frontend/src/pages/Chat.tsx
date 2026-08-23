import { useState } from "react"
import { Loader2, Sparkles } from "lucide-react"

import { api, type Schema } from "@/lib/api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"

function isLlmKeyError(text: string) {
  const lower = text.toLowerCase()
  return lower.includes("llm") || lower.includes("401") || lower.includes("not-set")
}

export const route = "/chat"
export const nav = { label: "Chat", icon: Sparkles, order: 3 }

export default function Chat() {
  const [prompt, setPrompt] = useState("")
  const [reply, setReply] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const send = async () => {
    if (!prompt.trim()) return
    setLoading(true)
    setReply("")
    setError("")
    try {
      const res = await api.post<Schema<"ChatResponse">>("/api/v1/ai/chat", { prompt })
      setReply(res.reply)
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>LLM Chat</CardTitle>
        <CardDescription>Multi-provider LLM call via LiteLLM</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex gap-2">
          <Input
            placeholder="Ask something"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
          />
          <Button onClick={send} disabled={loading}>
            {loading && <Loader2 className="animate-spin" />} Send
          </Button>
        </div>
        {reply && <p className="text-sm text-muted-foreground">{reply}</p>}
        {error && (
          <div className="space-y-2">
            <Badge variant="destructive">Error</Badge>
            <p className="text-sm text-destructive">{error}</p>
            {isLlmKeyError(error) && (
              <p className="text-sm text-destructive">
                No LLM key configured — add LLM_API_KEY to .env
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
