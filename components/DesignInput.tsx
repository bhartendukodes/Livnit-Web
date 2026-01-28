'use client'

import React, { useState, useRef, useEffect } from 'react'
import AnimatedSection from './AnimatedSection'

interface DesignInputProps {
  onGenerate: (prompt: string) => void
  onSurprise: () => void
}

const DesignInput: React.FC<DesignInputProps> = ({ onGenerate, onSurprise }) => {
  const [prompt, setPrompt] = useState('')
  const [isRecording, setIsRecording] = useState(false)
  const [showSuggestions, setShowSuggestions] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const suggestions = [
    "Modern minimalist living room with Scandinavian furniture",
    "Cozy bedroom with warm lighting and natural textures", 
    "Industrial kitchen with exposed brick and metal accents",
    "Bohemian dining room with vibrant colors and plants"
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
        <div className="relative">
          <textarea
            ref={textareaRef}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onFocus={() => setShowSuggestions(true)}
            className="modern-input w-full min-h-[100px] resize-none"
            placeholder="Describe your dream room... (e.g., Modern living room with beige sofa, mint green chair, glass coffee table)"
          />
          
          {/* Voice Input Button */}
          <button 
            className={`absolute right-3 bottom-3 p-2 rounded-lg transition-all duration-200 ${
              isRecording 
                ? 'bg-red-500 text-white' 
                : 'icon-button'
            }`}
            onMouseDown={() => setIsRecording(true)}
            onMouseUp={() => setIsRecording(false)}
            onMouseLeave={() => setIsRecording(false)}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M12 1C10.9 1 10 1.9 10 3V11C10 12.1 10.9 13 12 13C13.1 13 14 12.1 14 11V3C14 1.9 13.1 1 12 1Z" 
                    stroke="currentColor" strokeWidth="2"/>
              <path d="M19 10V11C19 14.9 15.9 18 12 18C8.1 18 5 14.9 5 11V10" 
                    stroke="currentColor" strokeWidth="2"/>
            </svg>
          </button>
        </div>

        {/* Quick Suggestions */}
        {showSuggestions && !prompt && (
          <div className="mt-3">
            <p className="text-xs text-muted mb-2" style={{ color: 'rgb(var(--text-muted))' }}>
              💡 Quick ideas:
            </p>
            <div className="flex flex-wrap gap-2">
              {suggestions.map((suggestion, index) => (
                <button
                  key={index}
                  onClick={() => handleSuggestionClick(suggestion)}
                  className="px-3 py-1.5 rounded-lg bg-primary-50 text-primary-700 hover:bg-primary-100 transition-colors text-xs border border-primary-100"
                  style={{
                    backgroundColor: 'rgb(var(--primary-50))',
                    color: 'rgb(var(--primary-700))',
                    borderColor: 'rgb(var(--primary-100))'
                  }}
                >
                  {suggestion.split(' ').slice(0, 4).join(' ')}...
                </button>
              ))}
            </div>
          </div>
        )}
      </AnimatedSection>

      {/* Action Buttons */}
      <AnimatedSection animation="slide-up" delay={500} className="w-full mb-4">
        <div className="flex gap-3">
          <button
            onClick={onSurprise}
            className="secondary-button px-4 py-2.5 flex items-center gap-2 text-sm font-medium"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M13 2L3 14H12L11 22L21 10H12L13 2Z" stroke="currentColor" strokeWidth="2"/>
            </svg>
            Surprise Me
          </button>
          
          <button
            onClick={handleGenerate}
            disabled={!prompt.trim()}
            className={`primary-button flex-1 px-6 py-2.5 flex items-center justify-center gap-2 text-sm font-semibold ${
              !prompt.trim() ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
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

