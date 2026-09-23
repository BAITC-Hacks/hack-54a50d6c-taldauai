import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import * as ToastPrimitive from '@radix-ui/react-toast'
import { CheckCircle2, X } from 'lucide-react'

type ToastContextValue = { toast: (title: string, description?: string) => void }
const ToastContext = createContext<ToastContextValue>({ toast: () => undefined })

export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<{ title: string; description?: string } | null>(null)
  const toast = useCallback((title: string, description?: string) => setMessage({ title, description }), [])
  return <ToastContext.Provider value={{ toast }}><ToastPrimitive.Provider swipeDirection="right">{children}<ToastPrimitive.Root open={Boolean(message)} onOpenChange={(open) => !open && setMessage(null)} duration={3500} className="fixed bottom-5 right-5 z-[100] flex w-[calc(100%-2rem)] max-w-sm items-start gap-3 rounded-lg border bg-white p-4 shadow-xl"><CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" /><div className="flex-1"><ToastPrimitive.Title className="text-sm font-semibold">{message?.title}</ToastPrimitive.Title>{message?.description && <ToastPrimitive.Description className="mt-1 text-sm text-muted-foreground">{message.description}</ToastPrimitive.Description>}</div><ToastPrimitive.Close><X className="h-4 w-4 text-muted-foreground" /></ToastPrimitive.Close></ToastPrimitive.Root><ToastPrimitive.Viewport /></ToastPrimitive.Provider></ToastContext.Provider>
}

export const useToast = () => useContext(ToastContext)
