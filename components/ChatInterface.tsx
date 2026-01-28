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
  pipelineResult,
  onDownloadUSDZ 
}) => {
  const [message, setMessage] = useState('')
  const [chatHistory, setChatHistory] = useState<Array<{ type: 'user' | 'ai'; text: string; timestamp: Date }>>([])
  const [isTyping, setIsTyping] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

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
    if (pipelineResult) {
      setIsTyping(true)
      // Simulate typing delay
      setTimeout(() => {
        const aiMessage = `🎉 Perfect! I've crafted a beautiful design for your space featuring ${pipelineResult.selected_uids.length} carefully selected pieces. The total investment comes to $${pipelineResult.total_cost.toFixed(2)}. 

Your design includes optimized furniture placement, realistic 3D visualization, and direct shopping links. Ready to bring your vision to life?`
        setChatHistory(prev => [...prev, { type: 'ai', text: aiMessage, timestamp: new Date() }])
        setIsTyping(false)
      }, 2000)
    }
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
    <div className="flex flex-col h-full overflow-hidden">
      {/* Compact Header */}
      <AnimatedSection animation="fade-in" className="p-4 border-b border-surface-muted"
                       style={{ borderColor: 'rgb(var(--surface-muted))' }}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-primary-500 rounded-lg flex items-center justify-center flex-shrink-0"
               style={{ backgroundColor: 'rgb(var(--primary-500))' }}>
            <span className="text-white text-sm font-bold">L</span>
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-primary-900 text-sm" style={{ color: 'rgb(var(--text-primary))' }}>
              Livi Assistant
            </h3>
            <div className="flex items-center gap-1.5 text-xs text-muted" style={{ color: 'rgb(var(--text-muted))' }}>
              <div className="w-1.5 h-1.5 bg-green-500 rounded-full"></div>
              <span>Online</span>
            </div>
          </div>
        </div>
      </AnimatedSection>

      {/* Chat Content */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {chatHistory.length === 0 && !initialMessage ? (
          <div className="text-center py-6">
            <div className="w-12 h-12 bg-primary-100 rounded-xl mx-auto mb-3 flex items-center justify-center"
                 style={{ backgroundColor: 'rgb(var(--primary-100))' }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="text-primary-600">
                <path d="M21 15C21 15.5304 20.7893 16.0391 20.4142 16.4142C20.0391 16.7893 19.5304 17 19 17H7L3 21V5C3 4.46957 3.21071 3.96086 3.58579 3.58579C3.96086 3.21071 4.46957 3 5 3H19C19.5304 3 20.0391 3.21071 20.4142 3.58579C20.7893 3.96086 21 4.46957 21 5V15Z" 
                      stroke="currentColor" strokeWidth="1.5"/>
              </svg>
            </div>
            <p className="text-secondary text-sm" style={{ color: 'rgb(var(--text-secondary))' }}>
              I&apos;m here to help with your design!
              <br />
              <span className="text-xs text-muted" style={{ color: 'rgb(var(--text-muted))' }}>
                Ask about furniture, layouts, or anything
              </span>
            </p>
          </div>
        ) : (
          <>
            {chatHistory.map((chat, index) => (
              <div key={index} className={`flex ${chat.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className="flex items-start gap-2 max-w-[90%]">
                  {chat.type === 'ai' && (
                    <div className="w-6 h-6 bg-primary-500 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
                         style={{ backgroundColor: 'rgb(var(--primary-500))' }}>
                      <span className="text-white text-xs font-bold">L</span>
                    </div>
                  )}
                  
                  <div className={`rounded-xl px-3 py-2 ${
                    chat.type === 'user'
                      ? 'bg-primary-500 text-white'
                      : 'bg-surface-soft text-primary-900 border border-surface-muted'
                  }`} style={{
                    backgroundColor: chat.type === 'user' 
                      ? 'rgb(var(--primary-500))' 
                      : 'rgb(var(--surface-soft))',
                    color: chat.type === 'user' 
                      ? 'white' 
                      : 'rgb(var(--text-primary))',
                    borderColor: chat.type === 'ai' ? 'rgb(var(--surface-muted))' : 'transparent'
                  }}>
                    <p className="text-sm leading-relaxed whitespace-pre-wrap">{chat.text}</p>
                    <p className="text-xs mt-1 opacity-60">
                      {chat.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </p>
                  </div>

                  {chat.type === 'user' && (
                    <div className="w-6 h-6 bg-surface-soft rounded-lg border border-surface-muted flex items-center justify-center flex-shrink-0 mt-0.5"
                         style={{ 
                           backgroundColor: 'rgb(var(--surface-soft))',
                           borderColor: 'rgb(var(--surface-muted))'
                         }}>
                      <span className="text-xs">👤</span>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {isTyping && (
              <div className="flex justify-start">
                <div className="flex items-start gap-2">
                  <div className="w-6 h-6 bg-primary-500 rounded-lg flex items-center justify-center flex-shrink-0"
                       style={{ backgroundColor: 'rgb(var(--primary-500))' }}>
                    <span className="text-white text-xs font-bold">L</span>
                  </div>
                  <div className="bg-surface-soft border border-surface-muted rounded-xl px-3 py-2" 
                       style={{ 
                         backgroundColor: 'rgb(var(--surface-soft))',
                         borderColor: 'rgb(var(--surface-muted))'
                       }}>
                    <div className="flex items-center gap-1">
                      <div className="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce"
                           style={{ backgroundColor: 'rgb(var(--primary-400))' }}></div>
                      <div className="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" 
                           style={{ backgroundColor: 'rgb(var(--primary-400))', animationDelay: '0.2s' }}></div>
                      <div className="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" 
                           style={{ backgroundColor: 'rgb(var(--primary-400))', animationDelay: '0.4s' }}></div>
                    </div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Compact Actions */}
      {pipelineResult && (
        <div className="px-4 pb-2">
          <div className="flex gap-2 text-xs">
            <button 
              onClick={onDownloadUSDZ}
              className="primary-button px-3 py-1.5 flex items-center gap-1.5"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                <path d="M21 15V19C21 20.1 20.1 21 19 21H5C3.9 21 3 20.1 3 19V15M7 10L12 15L17 10M12 15V3" 
                      stroke="currentColor" strokeWidth="2"/>
              </svg>
              <span>Download</span>
            </button>
            <div className="bg-green-50 text-green-700 px-2 py-1.5 rounded-lg font-medium border border-green-200">
              💰 ${pipelineResult.total_cost.toFixed(0)}
            </div>
            <div className="bg-blue-50 text-blue-700 px-2 py-1.5 rounded-lg font-medium border border-blue-200">
              📦 {pipelineResult.selected_uids.length} items
            </div>
          </div>
        </div>
      )}

      {/* Compact Input */}
      <div className="p-4 pt-2 border-t border-surface-muted" style={{ borderColor: 'rgb(var(--surface-muted))' }}>
        <div className="flex items-center gap-2 bg-surface-soft rounded-lg px-3 py-2 border border-surface-muted focus-within:border-primary-400 transition-all duration-200"
             style={{ 
               backgroundColor: 'rgb(var(--surface-soft))',
               borderColor: 'rgb(var(--surface-muted))'
             }}>
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Ask me anything..."
            className="flex-1 bg-transparent outline-none text-sm"
            style={{ color: 'rgb(var(--text-primary))' }}
          />
          
          <button className="icon-button p-1.5"
                  style={{ color: 'rgb(var(--text-muted))' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M12 1C10.9 1 10 1.9 10 3V11C10 12.1 10.9 13 12 13C13.1 13 14 12.1 14 11V3C14 1.9 13.1 1 12 1Z" 
                    stroke="currentColor" strokeWidth="2"/>
            </svg>
          </button>
          
          <button
            onClick={handleSend}
            disabled={!message.trim()}
            className={`p-1.5 rounded-md transition-all duration-200 ${
              message.trim() 
                ? 'bg-primary-500 text-white hover:bg-primary-600' 
                : 'bg-surface-muted text-muted cursor-not-allowed'
            }`}
            style={{
              backgroundColor: message.trim() 
                ? 'rgb(var(--primary-500))' 
                : 'rgb(var(--surface-muted))',
              color: message.trim() 
                ? 'white' 
                : 'rgb(var(--text-muted))'
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M5 12H19M19 12L12 5M19 12L12 19" stroke="currentColor" strokeWidth="1.5"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}

export default ChatInterface

