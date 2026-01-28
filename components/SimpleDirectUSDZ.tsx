'use client'

import React, { useEffect, useRef, useState } from 'react'

interface SimpleDirectUSDZProps {
  usdzBlob: Blob
}

const SimpleDirectUSDZ: React.FC<SimpleDirectUSDZProps> = ({ usdzBlob }) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const [objectUrl, setObjectUrl] = useState<string>('')

  // Create URL from blob
  useEffect(() => {
    const url = URL.createObjectURL(usdzBlob)
    setObjectUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [usdzBlob])

  // Create model-viewer immediately
  useEffect(() => {
    if (!objectUrl || !containerRef.current) return

    // Suppress ALL errors globally
    const originalError = window.onerror
    window.onerror = () => true // Block all errors

    const init = async () => {
      // Load model-viewer if needed
      if (!customElements.get('model-viewer')) {
        const script = document.createElement('script')
        script.type = 'module'
        script.src = 'https://unpkg.com/@google/model-viewer@3.5.0/dist/model-viewer.min.js'
        document.head.appendChild(script)
        await new Promise(resolve => {
          script.onload = resolve
          setTimeout(resolve, 2000) // Fallback timeout
        })
      }

      // Create model-viewer element
      const mv = document.createElement('model-viewer')
      
      // Set USDZ source
      mv.setAttribute('src', objectUrl)
      mv.setAttribute('ios-src', objectUrl)
      mv.setAttribute('camera-controls', '')
      mv.setAttribute('auto-rotate', '')
      mv.setAttribute('loading', 'eager')
      mv.setAttribute('reveal', 'auto')
      
      // Full size styling
      mv.style.width = '100%'
      mv.style.height = '100%'
      mv.style.minHeight = '400px'
      mv.style.backgroundColor = '#1f2937'
      
      // Add to container
      if (containerRef.current) {
        containerRef.current.innerHTML = '' // Clear any existing content
        containerRef.current.appendChild(mv)
      }
    }

    init().catch(() => {
      // Even if init fails, still try to show something
      if (containerRef.current) {
        containerRef.current.innerHTML = `
          <div style="width: 100%; height: 100%; background: #1f2937; display: flex; align-items: center; justify-content: center; color: white;">
            <a href="${objectUrl}" download="model.usdz" style="color: #a855f7; text-decoration: none;">
              📥 Download USDZ (${(usdzBlob.size / 1024 / 1024).toFixed(1)} MB)
            </a>
          </div>
        `
      }
    })

    return () => {
      window.onerror = originalError
    }
  }, [objectUrl, usdzBlob.size])

  return (
    <div 
      ref={containerRef}
      style={{
        width: '100%',
        height: '100%',
        minHeight: '400px',
        backgroundColor: '#1f2937',
        borderRadius: '8px',
        overflow: 'hidden'
      }}
    />
  )
}

export default SimpleDirectUSDZ