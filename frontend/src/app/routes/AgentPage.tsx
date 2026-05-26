import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Send, Plus, Bot, User, Wrench, Loader2, Trash2 } from 'lucide-react'
import { api } from '../../lib/api'
import { qk } from '../../lib/queryKeys'
import { fmtDateTime } from '../../lib/formatters'
import { LoadingState, EmptyState } from '../../components/shared'
import type { Conversation, ChatMessage } from '../../types'
import { clsx } from 'clsx'

export default function AgentPage() {
  const [activeConv, setActiveConv] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const qc = useQueryClient()

  const { data: conversations, isLoading } = useQuery({
    queryKey: qk.conversations(),
    queryFn:  api.getConversations,
  })

  const { data: loadedMessages, isFetching: loadingMessages } = useQuery({
    queryKey: qk.conversationMsgs(activeConv?.thread_id ?? ''),
    queryFn:  () => api.getConversationMessages(activeConv!.thread_id),
    enabled:  !!activeConv,
    staleTime: Infinity,
  })

  useEffect(() => {
    if (loadedMessages) setMessages(loadedMessages)
  }, [loadedMessages])

  const createConv = useMutation({
    mutationFn: api.createConversation,
    onSuccess: (conv) => {
      qc.invalidateQueries({ queryKey: qk.conversations() })
      setActiveConv(conv)
      setMessages([])
    },
  })

  const deleteConv = useMutation({
    mutationFn: (id: string) => api.deleteConversation(id),
    onSuccess: (_, deletedId) => {
      qc.invalidateQueries({ queryKey: qk.conversations() })
      if (activeConv?.id === deletedId) {
        setActiveConv(null)
        setMessages([])
      }
    },
  })

  // Restore last conversation from localStorage
  useEffect(() => {
    if (conversations && conversations.length > 0 && !activeConv) {
      const savedId = localStorage.getItem('agent_thread_id')
      const conv = savedId ? conversations.find(c => c.thread_id === savedId) : conversations[0]
      if (conv) setActiveConv(conv)
    }
  }, [conversations])

  useEffect(() => {
    if (activeConv) localStorage.setItem('agent_thread_id', activeConv.thread_id)
  }, [activeConv])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streaming])

  const sendMessage = async () => {
    if (!input.trim() || !activeConv || streaming) return

    const userMsg: ChatMessage = { role: 'user', content: input }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setStreaming(true)

    const assistantMsg: ChatMessage = { role: 'assistant', content: '', tool_calls: [] }
    setMessages(prev => [...prev, assistantMsg])

    try {
      const res = await fetch('/api/agent/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ thread_id: activeConv.thread_id, message: userMsg.content }),
      })

      if (!res.ok || !res.body) throw new Error('Stream failed')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const text = decoder.decode(value)
        const lines = text.split('\n').filter(l => l.startsWith('data: '))

        for (const line of lines) {
          const raw = line.replace('data: ', '').trim()
          if (raw === '[DONE]') { setStreaming(false); break }
          try {
            const event = JSON.parse(raw)
            setMessages(prev => {
              const msgs = [...prev]
              const last = msgs[msgs.length - 1]
              if (!last || last.role !== 'assistant') return msgs
              const updated = { ...last }
              if (event.type === 'message') {
                updated.content = event.content
              } else if (event.type === 'tool') {
                updated.tool_calls = [...(updated.tool_calls ?? []), { name: event.name, content: event.content }]
              } else if (event.type === 'error') {
                updated.content = `Erro: ${event.content}`
              }
              msgs[msgs.length - 1] = updated
              return msgs
            })
          } catch { /* ignore parse errors */ }
        }
      }
    } catch (err) {
      setMessages(prev => {
        const msgs = [...prev]
        msgs[msgs.length - 1] = { role: 'assistant', content: 'Erro ao processar sua mensagem. Tente novamente.' }
        return msgs
      })
    } finally {
      setStreaming(false)
      qc.invalidateQueries({ queryKey: qk.conversations() })
    }
  }

  return (
    <div className="flex h-[calc(100vh-5rem)] gap-0 rounded-2xl overflow-hidden border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
      {/* Sidebar */}
      <aside className="w-64 shrink-0 flex flex-col border-r border-gray-100 dark:border-gray-800">
        <div className="p-4 border-b border-gray-100 dark:border-gray-800">
          <button
            onClick={() => createConv.mutate()}
            disabled={createConv.isPending}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium transition-colors"
          >
            <Plus className="w-4 h-4" />
            Nova conversa
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {isLoading && <LoadingState />}
          {!isLoading && (!conversations || conversations.length === 0) && (
            <EmptyState message="Nenhuma conversa." />
          )}
          {conversations?.map(conv => (
            <div key={conv.id} className="group relative mb-1">
              <button
                onClick={() => { setActiveConv(conv); setMessages([]) ; qc.invalidateQueries({ queryKey: qk.conversationMsgs(conv.thread_id) }) }}
                className={clsx(
                  'w-full text-left px-3 py-2.5 pr-8 rounded-lg text-sm transition-colors',
                  activeConv?.id === conv.id
                    ? 'bg-brand-50 dark:bg-brand-900/30 text-brand-700 dark:text-brand-400'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800',
                )}
              >
                <p className="truncate font-medium">{conv.title}</p>
                <p className="text-xs text-gray-400 mt-0.5">{fmtDateTime(conv.last_message_at)}</p>
              </button>
              <button
                onClick={e => { e.stopPropagation(); deleteConv.mutate(conv.id) }}
                disabled={deleteConv.isPending}
                title="Excluir conversa"
                className="absolute right-1.5 top-1/2 -translate-y-1/2 p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-red-100 dark:hover:bg-red-900/30 text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-all"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      </aside>

      {/* Chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {!activeConv ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-4 text-gray-400">
            <Bot className="w-12 h-12" />
            <p className="text-sm">Selecione uma conversa ou crie uma nova</p>
          </div>
        ) : (
          <>
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-4">
              {loadingMessages && messages.length === 0 && (
                <div className="flex flex-col items-center gap-3 py-8 text-gray-400">
                  <Loader2 className="w-8 h-8 animate-spin" />
                  <p className="text-sm">Carregando histórico...</p>
                </div>
              )}
              {!loadingMessages && messages.length === 0 && (
                <div className="flex flex-col items-center gap-3 py-8 text-gray-400">
                  <Bot className="w-8 h-8" />
                  <p className="text-sm text-center max-w-sm">
                    Pergunte sobre ofertas primárias, coordenadores, contexto macro ou qualquer dado disponível na aplicação.
                  </p>
                </div>
              )}
              {messages.map((msg, i) => (
                <div key={i} className={clsx('flex gap-3', msg.role === 'user' ? 'flex-row-reverse' : '')}>
                  <div className={clsx(
                    'w-8 h-8 rounded-full flex items-center justify-center shrink-0',
                    msg.role === 'user' ? 'bg-brand-100 dark:bg-brand-900/40' : 'bg-gray-100 dark:bg-gray-800',
                  )}>
                    {msg.role === 'user' ? <User className="w-4 h-4 text-brand-600" /> : <Bot className="w-4 h-4 text-gray-500" />}
                  </div>
                  <div className={clsx('flex flex-col gap-1 max-w-[75%]', msg.role === 'user' ? 'items-end' : '')}>
                    {msg.tool_calls && msg.tool_calls.length > 0 && (
                      <div className="flex flex-col gap-1">
                        {msg.tool_calls.map((tc, ti) => (
                          <details key={ti} className="text-xs bg-gray-50 dark:bg-gray-800 rounded-lg p-2 cursor-pointer">
                            <summary className="flex items-center gap-1.5 font-medium text-gray-600 dark:text-gray-400">
                              <Wrench className="w-3 h-3" />
                              {tc.name}
                            </summary>
                            <p className="mt-1 text-gray-500 font-mono whitespace-pre-wrap">{tc.content}</p>
                          </details>
                        ))}
                      </div>
                    )}
                    {msg.content && (
                      <div className={clsx(
                        'px-4 py-3 rounded-2xl text-sm leading-relaxed',
                        msg.role === 'user'
                          ? 'bg-brand-600 text-white rounded-tr-sm'
                          : 'bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-tl-sm',
                      )}>
                        <p className="whitespace-pre-wrap">{msg.content}</p>
                      </div>
                    )}
                    {msg.role === 'assistant' && streaming && i === messages.length - 1 && !msg.content && (
                      <div className="px-4 py-3 rounded-2xl bg-gray-100 dark:bg-gray-800">
                        <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
                      </div>
                    )}
                  </div>
                </div>
              ))}
              <div ref={bottomRef} />
            </div>

            {/* Disclaimer */}
            <div className="px-4 py-1.5 bg-amber-50 dark:bg-amber-900/10 border-t border-amber-100 dark:border-amber-900/20">
              <p className="text-xs text-amber-700 dark:text-amber-400 text-center">
                ⚠️ Este agente não faz recomendação de investimento. Dados são informativos.
              </p>
            </div>

            {/* Input */}
            <div className="p-4 border-t border-gray-100 dark:border-gray-800">
              <div className="flex gap-2">
                <textarea
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() } }}
                  placeholder="Pergunte sobre ofertas, coordenadores, macro... (Enter para enviar, Shift+Enter para nova linha)"
                  rows={2}
                  className="flex-1 resize-none rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 dark:text-gray-200 placeholder-gray-400"
                />
                <button
                  onClick={sendMessage}
                  disabled={!input.trim() || streaming}
                  className="px-4 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-700 text-white disabled:opacity-50 transition-colors self-end"
                >
                  {streaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
