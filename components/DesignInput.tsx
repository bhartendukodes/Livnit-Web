'use client'

import React, { useState, useRef, useEffect } from 'react'
import AnimatedSection from './AnimatedSection'

interface DesignInputProps {
  onGenerate: (prompt: string) => void
}

const DesignInput: React.FC<DesignInputProps> = ({ onGenerate }) => {
  const [prompt, setPrompt] = useState('')
  const [showSuggestions, setShowSuggestions] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const suggestions = [
    "Modern Scandinavian living room with beige curved sofa, oak coffee table, and white walls",
    "Cozy boho bedroom with rattan headboard, warm lighting, and macrame wall hangings",
    "Industrial loft kitchen with exposed brick, black metal stools, and marble countertops", 
    "Minimalist home office with standing desk, ergonomic chair, and built-in shelving",
    "Luxe dining room with velvet chairs, crystal chandelier, and dark wood table",
    "Zen meditation space with floor cushions, bamboo screens, and natural lighting"
  ]

  const handleGenerate = (e?: React.MouseEvent) => {
    if (e) {
      e.preventDefault()
      e.stopPropagation()
    }
    
    const cleanPrompt = prompt.trim()
    if (cleanPrompt) {
      onGenerate(cleanPrompt)
    }
  }

  const handleSuggestionClick = (suggestion: string) => {
    setPrompt(suggestion)
    setShowSuggestions(false)
    textareaRef.current?.focus()
  }

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = `${Math.max(textarea.scrollHeight, 120)}px`
    }
  }, [prompt])

  return (
    <div className="max-w-3xl mx-auto">
      {/* Compact Header */}
      <AnimatedSection animation="slide-up" className="text-center mb-8">
        <div className="inline-flex items-center gap-3 mb-4">
          <div className="w-12 h-12 bg-primary-500 rounded-xl flex items-center justify-center"
               style={{ backgroundColor: 'rgb(var(--primary-500))' }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="text-white">
              <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" strokeWidth="2"/>
              <path d="M2 17L12 22L22 17" stroke="currentColor" strokeWidth="2"/>
              <path d="M2 12L12 17L22 12" stroke="currentColor" strokeWidth="2"/>
            </svg>
          </div>
          <div className="text-left">
            <h1 className="text-3xl font-bold text-gradient">Design Your Space</h1>
            <p className="text-sm text-muted -mt-0.5" style={{ color: 'rgb(var(--text-muted))' }}>
              AI-powered interior design
            </p>
          </div>
        </div>
        
        <p className="text-base text-secondary max-w-xl mx-auto leading-relaxed"
           style={{ color: 'rgb(var(--text-secondary))' }}>
          Describe your vision and let <span className="font-semibold text-primary-600" style={{ color: 'rgb(var(--primary-600))' }}>Livi</span> create 
          a personalized design with real furniture and 3D visualization.
        </p>
      </AnimatedSection>

      {/* Input Section */}
      <AnimatedSection animation="slide-up" delay={300} className="w-full mb-6">
        <div className="relative rounded-xl border shadow-sm bg-white"
             style={{ borderColor: 'rgb(var(--surface-muted))' }}>
          <textarea
            ref={textareaRef}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onFocus={() => setShowSuggestions(true)}
            className="w-full min-h-[120px] resize-none p-4 rounded-xl bg-transparent border-none outline-none text-base leading-relaxed focus:ring-2 focus:ring-primary-300/50"
            placeholder="Describe your dream room with specific details..."
            style={{ 
              color: 'rgb(var(--text-primary))',
              transition: 'all 0.2s ease'
            }}
          />
        </div>

        {/* Design Inspiration Cards */}
        {showSuggestions && !prompt && (
          <div className="mt-4">
            <p className="text-sm font-medium mb-3" style={{ color: 'rgb(var(--text-primary))' }}>
              ✨ Popular Design Styles
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {suggestions.map((suggestion, index) => (
                <button
                  key={index}
                  onClick={() => handleSuggestionClick(suggestion)}
                  className="text-left p-4 rounded-xl border hover:shadow-md transition-all duration-200 bg-white hover:border-primary-300 group"
                  style={{
                    backgroundColor: 'white',
                    borderColor: 'rgb(var(--surface-muted))'
                  }}
                >
                  <div className="text-sm font-medium text-primary-800 mb-1 group-hover:text-primary-600 transition-colors"
                       style={{ color: 'rgb(var(--primary-800))' }}>
                    {suggestion.split(' ').slice(0, 3).join(' ')}
                  </div>
                  <div className="text-xs text-muted line-clamp-2"
                       style={{ color: 'rgb(var(--text-muted))' }}>
                    {suggestion}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </AnimatedSection>

      {/* Action Button - no surprise, just generate */}
      <AnimatedSection animation="slide-up" delay={500} className="w-full mb-4">
        <div className="flex justify-center">
          <button
            onClick={handleGenerate}
            disabled={!prompt.trim()}
            className={`primary-button px-8 py-3 flex items-center justify-center gap-2 font-semibold rounded-xl shadow-md hover:shadow-lg transition-all duration-200 ${
              !prompt.trim() ? 'opacity-50 cursor-not-allowed' : 'hover:scale-105 active:scale-95'
            }`}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" strokeWidth="2"/>
              <path d="M2 17L12 22L22 17" stroke="currentColor" strokeWidth="2"/>
            </svg>
            <span>Generate Design</span>
          </button>
        </div>
      </AnimatedSection>

      {/* Compact Status */}
      <AnimatedSection animation="fade-in" delay={600}>
        <div className="flex items-center justify-center gap-2 text-sm">
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span className="text-green-600 font-medium">AI Ready</span>
          </div>
          <span className="text-muted" style={{ color: 'rgb(var(--text-muted))' }}>•</span>
          <span className="text-muted text-xs" style={{ color: 'rgb(var(--text-muted))' }}>
            12K+ designs created
          </span>
        </div>
      </AnimatedSection>
    </div>
  )
}

export default DesignInput

