'use client'

import React, { useState, useRef, useEffect } from 'react'
import AnimatedSection from './AnimatedSection'

interface DesignInputProps {
  onGenerate: (prompt: string) => void
  hasUploadedRoom?: boolean
}

const DesignInput: React.FC<DesignInputProps> = ({
  onGenerate,
  hasUploadedRoom = false
}) => {
  const [prompt, setPrompt] = useState('')
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [isFocused, setIsFocused] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const suggestions = [
    "Warm Scandinavian living room: soft gray sectional, light oak coffee table, cream armchairs",
    "Relaxed boho living room: velvet sofa in terracotta, rattan side tables, round jute rug",
    "Clean minimalist living room: low white sofa, slim black metal coffee table",
    "Classic mid-century: tufted olive sofa, walnut credenza, tapered-leg coffee table",
    "Industrial loft: leather sofa, metal and wood coffee table, exposed-frame armchair",
    "Soft modern: curved bouclé sofa, marble-top coffee table, velvet accent chair"
  ]

  const handleGenerate = (e?: React.MouseEvent) => {
    if (e) {
      e.preventDefault()
      e.stopPropagation()
    }
    const cleanPrompt = prompt.trim()
    if (cleanPrompt) onGenerate(cleanPrompt)
  }

  const handleSuggestionClick = (suggestion: string) => {
    setPrompt(suggestion)
    textareaRef.current?.focus()
  }

  useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = `${Math.max(textarea.scrollHeight, 100)}px`
    }
  }, [prompt])

  return (
    <div className="space-y-6">
      {/* Title */}
      <AnimatedSection animation="slide-up" delay={0} className="text-center mb-8">
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight mb-2"
            style={{ color: 'rgb(var(--text-primary))' }}>
          Design Your Space
        </h1>
        <p className="text-sm max-w-md mx-auto"
           style={{ color: 'rgb(var(--text-muted))' }}>
          Upload your room, describe your style, and let AI create your perfect layout
        </p>
      </AnimatedSection>

      {/* Describe your design — no step number */}
      <AnimatedSection animation="slide-up" delay={200}>
        <div>
          <div className="mb-3">
            <p className="font-semibold text-sm" style={{ color: 'rgb(var(--text-primary))' }}>
              Describe your design
            </p>
            <p className="text-xs mt-0.5" style={{ color: 'rgb(var(--text-muted))' }}>
              Style, furniture, colors — tell us what you want
            </p>
          </div>

          <div
            className="card-premium transition-all duration-200 overflow-hidden"
            style={{
              boxShadow: isFocused 
                ? '0 0 0 2px rgba(var(--primary-500), 0.25), 0 8px 32px rgba(0,0,0,0.08), 0 1px 0 0 rgba(255,255,255,0.8) inset' 
                : undefined
            }}
          >
            <textarea
              ref={textareaRef}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onFocus={() => { setIsFocused(true); setShowSuggestions(true) }}
              onBlur={() => setIsFocused(false)}
              placeholder="e.g. Modern Scandinavian living room with gray sectional and oak coffee table..."
              className="w-full min-h-[100px] resize-none p-5 rounded-2xl border-0 outline-none text-[15px] leading-relaxed bg-transparent placeholder:text-gray-400"
              style={{ color: 'rgb(var(--text-primary))' }}
            />
          </div>

          {showSuggestions && (
            <div className="mt-5">
              <p className="text-xs font-semibold mb-3 uppercase tracking-wider" style={{ color: 'rgb(var(--text-muted))' }}>
                Quick picks
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {suggestions.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => handleSuggestionClick(s)}
                    className="card-premium px-4 py-3.5 rounded-2xl text-left text-sm transition-all hover:scale-[1.01] active:scale-[0.99] line-clamp-2"
                    style={{ color: 'rgb(var(--text-secondary))' }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </AnimatedSection>

      {/* Generate */}
      <AnimatedSection animation="slide-up" delay={300}>
        <div className="flex flex-col items-center gap-3 pt-2">
          {!hasUploadedRoom && (
            <p className="text-xs" style={{ color: 'rgb(var(--text-muted))' }}>
              Upload room first to continue
            </p>
          )}
          <button
            onClick={handleGenerate}
            disabled={!hasUploadedRoom || !prompt.trim()}
            className="w-full sm:w-auto px-10 py-4 rounded-2xl font-semibold text-[15px] flex items-center justify-center gap-2.5 transition-all disabled:opacity-40 disabled:cursor-not-allowed enabled:hover:scale-[1.02] enabled:active:scale-[0.98]"
            style={{
              background: 'linear-gradient(135deg, rgb(var(--primary-500)) 0%, rgb(var(--primary-600)) 100%)',
              color: 'white',
              boxShadow: '0 8px 24px rgba(var(--primary-500), 0.4)'
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2L2 7L12 12L22 7L12 2Z" />
              <path d="M2 17L12 22L22 17" />
            </svg>
            Generate Design
          </button>
          <p className="text-[11px]" style={{ color: 'rgb(var(--text-muted))' }}>
            AI Ready · 12K+ designs
          </p>
        </div>
      </AnimatedSection>
    </div>
  )
}

export default DesignInput
