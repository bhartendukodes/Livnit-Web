'use client'

import React, { useState, useEffect, useRef } from 'react'
import AnimatedSection from './AnimatedSection'
import { PipelineResult } from '../services/ApiClient'

interface ChatInterfaceProps {
  initialMessage?: string
  pipelineResult?: PipelineResult | null
  onDownloadUSDZ?: () => void
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ 
  initialMessage = '', 
  pipelineResult
}) => {
  const [message, setMessage] = useState('')
  const [chatHistory, setChatHistory] = useState<Array<{ type: 'user' | 'ai'; text: string; timestamp: Date }>>([])
  const [isTyping, setIsTyping] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const lastResultRunDir = useRef<string | null>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [chatHistory])

  useEffect(() => {
    if (initialMessage) {
      setChatHistory([{ type: 'user', text: initialMessage, timestamp: new Date() }])
    }
  }, [initialMessage])

  useEffect(() => {
    if (!pipelineResult?.run_dir) return
    // Only add the AI message once per pipeline result (same run_dir)
    if (lastResultRunDir.current === pipelineResult.run_dir) return
    lastResultRunDir.current = pipelineResult.run_dir

    setIsTyping(true)
    setTimeout(() => {
      const aiMessage = `🎉 Perfect! I've crafted a beautiful design for your space featuring ${pipelineResult.selected_uids.length} carefully selected pieces. The total investment comes to $${pipelineResult.total_cost.toFixed(2)}. 

Your design includes optimized furniture placement, realistic 3D visualization, and direct shopping links. Ready to bring your vision to life?`
      setChatHistory(prev => [...prev, { type: 'ai', text: aiMessage, timestamp: new Date() }])
      setIsTyping(false)
    }, 2000)
  }, [pipelineResult])

  const handleSend = () => {
    if (message.trim()) {
      setChatHistory(prev => [...prev, { type: 'user', text: message, timestamp: new Date() }])
      setMessage('')
      
      // Simulate AI response
      setIsTyping(true)
      setTimeout(() => {
        setChatHistory(prev => [...prev, { 
          type: 'ai', 
          text: "Thanks for your message! I&apos;m here to help you with any questions about your room design or furniture choices. What would you like to explore?", 
          timestamp: new Date() 
        }])
        setIsTyping(false)
      }, 1500)
    }
  }

  return (
    <div className="flex flex-col h-full overflow-hidden bg-white/80 backdrop-blur-sm rounded-2xl shadow-sm"
         style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
      {/* Header */}
      <AnimatedSection animation="fade-in" className="shrink-0 px-5 py-4 border-b border-surface-muted/80"
                       style={{ borderColor: 'rgb(var(--surface-muted))', background: 'linear-gradient(180deg, rgb(var(--primary-50)) 0%, white 100%)' }}>
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 shadow-sm"
               style={{ background: 'linear-gradient(135deg, rgb(var(--primary-500)) 0%, rgb(var(--primary-600)) 100%)' }}>
            <span className="text-white text-base font-bold">L</span>
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-base tracking-tight" style={{ color: 'rgb(var(--text-primary))' }}>
              Livi Assistant
            </h3>
            <div className="flex items-center gap-2 text-xs mt-0.5" style={{ color: 'rgb(var(--text-muted))' }}>
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>Online</span>
            </div>
          </div>
        </div>
      </AnimatedSection>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-5 space-y-4 scroll-smooth">
        {chatHistory.length === 0 && !initialMessage ? (
          <div className="text-center py-10 px-4">
            <div className="w-14 h-14 rounded-2xl mx-auto mb-4 flex items-center justify-center shadow-inner"
                 style={{ backgroundColor: 'rgb(var(--primary-100))' }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
                   style={{ color: 'rgb(var(--primary-500))' }}>
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            </div>
            <p className="font-medium text-sm mb-1" style={{ color: 'rgb(var(--text-primary))' }}>
              I&apos;m here to help with your design
            </p>
            <p className="text-xs max-w-[200px] mx-auto" style={{ color: 'rgb(var(--text-muted))' }}>
              Ask about furniture, layouts, or anything — or start a new design above.
            </p>
          </div>
        ) : (
          <>
            {chatHistory.map((chat, index) => (
              <div key={index} className={`flex ${chat.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`flex items-end gap-2 max-w-[92%] ${chat.type === 'user' ? 'flex-row-reverse' : ''}`}>
                  {chat.type === 'ai' && (
                    <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 mb-1 shadow-sm"
                         style={{ background: 'linear-gradient(135deg, rgb(var(--primary-400)) 0%, rgb(var(--primary-500)) 100%)' }}>
                      <span className="text-white text-sm font-bold">L</span>
                    </div>
                  )}
                  <div
                    className={`rounded-2xl px-4 py-3 shadow-sm ${
                      chat.type === 'user'
                        ? 'rounded-br-md'
                        : 'rounded-bl-md'
                    }`}
                    style={{
                      backgroundColor: chat.type === 'user'
                        ? 'rgb(var(--primary-500))'
                        : 'rgb(var(--surface-soft))',
                      color: chat.type === 'user' ? 'white' : 'rgb(var(--text-primary))',
                      border: chat.type === 'ai' ? '1px solid rgb(var(--surface-muted))' : 'none',
                    }}
                  >
                    <p className="text-sm leading-relaxed whitespace-pre-wrap">{chat.text}</p>
                    <p className={`text-xs mt-2 ${chat.type === 'user' ? 'text-white/80' : ''}`} style={chat.type === 'ai' ? { color: 'rgb(var(--text-muted))' } : undefined}>
                      {chat.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </p>
                  </div>
                  {chat.type === 'user' && (
                    <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 mb-1 border shadow-sm"
                         style={{ backgroundColor: 'rgb(var(--surface-soft))', borderColor: 'rgb(var(--surface-muted))' }}>
                      <span className="text-sm">👤</span>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {isTyping && (
              <div className="flex justify-start">
                <div className="flex items-end gap-2">
                  <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 mb-1 shadow-sm"
                       style={{ background: 'linear-gradient(135deg, rgb(var(--primary-400)) 0%, rgb(var(--primary-500)) 100%)' }}>
                    <span className="text-white text-sm font-bold">L</span>
                  </div>
                  <div className="rounded-2xl rounded-bl-md px-4 py-3 shadow-sm border"
                       style={{ backgroundColor: 'rgb(var(--surface-soft))', borderColor: 'rgb(var(--surface-muted))' }}>
                    <div className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full animate-bounce" style={{ backgroundColor: 'rgb(var(--primary-400))', animationDelay: '0ms' }} />
                      <span className="w-2 h-2 rounded-full animate-bounce" style={{ backgroundColor: 'rgb(var(--primary-400))', animationDelay: '150ms' }} />
                      <span className="w-2 h-2 rounded-full animate-bounce" style={{ backgroundColor: 'rgb(var(--primary-400))', animationDelay: '300ms' }} />
                    </div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input - no cost/items after preview */}
      <div className="shrink-0 p-4 pt-3 border-t border-surface-muted/80" style={{ borderColor: 'rgb(var(--surface-muted))', backgroundColor: 'rgb(var(--surface-soft))' }}>
        <div className="flex items-center gap-2 rounded-xl px-3 py-2 border transition-all duration-200 focus-within:ring-2 focus-within:ring-primary-400/40 focus-within:border-primary-400"
             style={{
               backgroundColor: 'white',
               borderColor: 'rgb(var(--surface-muted))',
             }}>
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Ask me anything..."
            className="flex-1 bg-transparent outline-none text-sm py-1 placeholder:text-muted"
            style={{ color: 'rgb(var(--text-primary))' }}
          />
          <button
            onClick={handleSend}
            disabled={!message.trim()}
            className="p-2.5 rounded-lg transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed hover:scale-105 active:scale-95"
            style={{
              backgroundColor: message.trim() ? 'rgb(var(--primary-500))' : 'rgb(var(--surface-muted))',
              color: message.trim() ? 'white' : 'rgb(var(--text-muted))',
            }}
            aria-label="Send message"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}

export default ChatInterface

