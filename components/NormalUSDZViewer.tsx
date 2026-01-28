'use client'

import React, { useEffect, useRef, useState } from 'react'

interface NormalUSDZViewerProps {
  usdzBlob: Blob
}

const NormalUSDZViewer: React.FC<NormalUSDZViewerProps> = ({ usdzBlob }) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const [objectUrl, setObjectUrl] = useState<string>('')
  const [isReady, setIsReady] = useState(false)

  // Create object URL immediately
  useEffect(() => {
    if (usdzBlob && usdzBlob.size > 0) {
      const url = URL.createObjectURL(usdzBlob)
      setObjectUrl(url)
      console.log('🔗 NormalUSDZViewer: Object URL created, size:', (usdzBlob.size / 1024 / 1024).toFixed(1), 'MB')
      
      return () => {
        URL.revokeObjectURL(url)
      }
    }
  }, [usdzBlob])

  // Setup model-viewer when URL is ready
  useEffect(() => {
    if (!objectUrl || !containerRef.current) {
      console.log('⏸️ NormalUSDZViewer: Waiting for URL or container', { hasUrl: !!objectUrl, hasContainer: !!containerRef.current })
      return
    }

    console.log('🎬 NormalUSDZViewer: Starting setup...')

    const setupViewer = async () => {
      try {
        // Load model-viewer script if needed
        if (!customElements.get('model-viewer')) {
          console.log('📦 Loading model-viewer script...')
          const script = document.createElement('script')
          script.type = 'module'
          script.src = 'https://unpkg.com/@google/model-viewer@3.5.0/dist/model-viewer.min.js'
          
          await new Promise<void>((resolve) => {
            script.onload = () => {
              console.log('✅ Model-viewer script loaded')
              resolve()
            }
            script.onerror = () => {
              console.error('❌ Failed to load model-viewer script')
              resolve() // Continue anyway
            }
            document.head.appendChild(script)
            // Fallback timeout
            setTimeout(resolve, 3000)
          })
          
          // Wait for custom element registration
          let attempts = 0
          while (!customElements.get('model-viewer') && attempts < 20) {
            await new Promise(resolve => setTimeout(resolve, 100))
            attempts++
          }
        }

        if (!containerRef.current) {
          console.error('❌ Container not available')
          return
        }

        console.log('🎨 Creating model-viewer element...')

        // Create model-viewer element
        const modelViewer = document.createElement('model-viewer')
        
        // Set USDZ source
        modelViewer.setAttribute('src', objectUrl)
        modelViewer.setAttribute('ios-src', objectUrl)
        modelViewer.setAttribute('alt', '3D Room Model')
        modelViewer.setAttribute('camera-controls', '')
        modelViewer.setAttribute('auto-rotate', '')
        modelViewer.setAttribute('loading', 'eager')
        modelViewer.setAttribute('reveal', 'auto')
        modelViewer.setAttribute('shadow-intensity', '1')
        
        // Full size styling
        modelViewer.style.cssText = `
          width: 100%;
          height: 100%;
          min-height: 400px;
          background-color: #1f2937;
          border: none;
          outline: none;
        `

        // Event handlers
        modelViewer.addEventListener('load', () => {
          console.log('✅ NormalUSDZViewer: Model loaded successfully!')
          setIsReady(true)
        })

        modelViewer.addEventListener('error', (e) => {
          console.warn('⚠️ NormalUSDZViewer: Model error (may be expected for USDZ):', e)
          // Still show the viewer
          setIsReady(true)
        })

        // Clear container and add viewer
        containerRef.current.innerHTML = ''
        containerRef.current.appendChild(modelViewer)
        
        console.log('✅ NormalUSDZViewer: Model-viewer element added to DOM')

      } catch (error) {
        console.error('❌ NormalUSDZViewer setup error:', error)
      }
    }

    setupViewer()
  }, [objectUrl])

  if (!objectUrl) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gray-900 rounded-lg">
        <div className="text-white">Loading USDZ...</div>
      </div>
    )
  }

  return (
    <div className="relative w-full h-full bg-gray-900 rounded-lg overflow-hidden">
      <div 
        ref={containerRef}
        className="w-full h-full"
        style={{
          minHeight: '400px',
          backgroundColor: '#1f2937'
        }}
      />
      
      {!isReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-900/80 z-10">
          <div className="text-center text-white">
            <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
            <p className="text-sm">Loading 3D model...</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default NormalUSDZViewer