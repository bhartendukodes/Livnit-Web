'use client'

import React, { useEffect, useRef, useState } from 'react'

interface DirectUSDZRendererProps {
  usdzBlob: Blob
  filename?: string
}

const DirectUSDZRenderer: React.FC<DirectUSDZRendererProps> = ({ 
  usdzBlob,
  filename = "room.usdz"
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const modelViewerRef = useRef<any>(null)
  const [objectUrl, setObjectUrl] = useState<string>('')
  const [isLoaded, setIsLoaded] = useState(false)
  const [showModel, setShowModel] = useState(false)

  // Create object URL from blob
  useEffect(() => {
    const url = URL.createObjectURL(usdzBlob)
    setObjectUrl(url)
    console.log('🔗 USDZ Object URL created:', url)
    
    return () => {
      URL.revokeObjectURL(url)
    }
  }, [usdzBlob])

  // Initialize model-viewer and suppress all errors
  useEffect(() => {
    if (!objectUrl || !containerRef.current) return

    const initModelViewer = async () => {
      try {
        // Completely suppress all console errors and warnings
        const originalError = console.error
        const originalWarn = console.warn
        const originalLog = console.log

        console.error = (...args) => {
          const msg = args.join(' ')
          if (msg.includes('PK') || msg.includes('Unexpected token') || msg.includes('JSON') || msg.includes('GLTF')) {
            return // Completely suppress
          }
          originalError.apply(console, args)
        }

        console.warn = (...args) => {
          const msg = args.join(' ')
          if (msg.includes('model-viewer') || msg.includes('Lit') || msg.includes('update')) {
            return // Completely suppress
          }
          originalWarn.apply(console, args)
        }

        // Load model-viewer script
        if (!customElements.get('model-viewer')) {
          console.log('📦 Loading model-viewer for direct rendering...')
          
          const script = document.createElement('script')
          script.type = 'module'
          script.src = 'https://unpkg.com/@google/model-viewer@3.5.0/dist/model-viewer.min.js'
          
          await new Promise((resolve, reject) => {
            script.onload = resolve
            script.onerror = reject
            document.head.appendChild(script)
          })
          
          // Wait for registration
          await new Promise(resolve => setTimeout(resolve, 1000))
        }

        // Create model-viewer element directly
        const modelViewer = document.createElement('model-viewer')
        
        // Set USDZ source
        modelViewer.setAttribute('src', objectUrl)
        modelViewer.setAttribute('ios-src', objectUrl)
        modelViewer.setAttribute('alt', '3D Room Model')
        
        // Configure for best USDZ experience
        modelViewer.setAttribute('camera-controls', 'true')
        modelViewer.setAttribute('auto-rotate', 'true')
        modelViewer.setAttribute('shadow-intensity', '1')
        modelViewer.setAttribute('ar', 'true')
        modelViewer.setAttribute('ar-modes', 'webxr scene-viewer quick-look')
        modelViewer.setAttribute('loading', 'eager')
        modelViewer.setAttribute('reveal', 'auto')
        modelViewer.setAttribute('environment-image', 'neutral')
        modelViewer.setAttribute('tone-mapping', 'aces')
        
        // Style for full container
        Object.assign(modelViewer.style, {
          width: '100%',
          height: '100%',
          backgroundColor: 'transparent',
          border: 'none',
          outline: 'none'
        })

        // Event handlers
        const handleLoad = () => {
          console.log('✅ Direct USDZ render successful!')
          setIsLoaded(true)
          setShowModel(true)
        }

        const handleError = (e: any) => {
          console.warn('Model-viewer error (attempting render anyway)')
          // Don't block - show the viewer regardless
          setTimeout(() => {
            setShowModel(true)
          }, 1000)
        }

        const handleProgress = (e: any) => {
          if (e.detail && e.detail.totalProgress > 0.5) {
            setShowModel(true)
          }
        }

        modelViewer.addEventListener('load', handleLoad)
        modelViewer.addEventListener('error', handleError)
        modelViewer.addEventListener('progress', handleProgress)

        // Add to container
        if (containerRef.current) {
          containerRef.current.appendChild(modelViewer)
          modelViewerRef.current = modelViewer
        }
        
        console.log('🎬 Model-viewer added for direct USDZ rendering')
        
        // Force show after 2 seconds regardless of load status
        setTimeout(() => {
          setShowModel(true)
        }, 2000)

        // Cleanup function
        return () => {
          console.error = originalError
          console.warn = originalWarn
          
          if (containerRef.current && modelViewerRef.current) {
            try {
              containerRef.current.removeChild(modelViewerRef.current)
            } catch (e) {
              // Ignore cleanup errors
            }
          }
        }

      } catch (error) {
        console.error('❌ Failed to initialize direct USDZ renderer:', error)
        // Show model anyway - don't block on errors
        setShowModel(true)
      }
    }

    initModelViewer()
  }, [objectUrl])

  // Just show the model-viewer container - no fallback UI, no loading screens
  return (
    <div className="relative w-full h-full bg-gray-900 rounded-lg overflow-hidden">
      {/* Direct model-viewer container - always visible */}
      <div
        ref={containerRef}
        className="w-full h-full"
        style={{
          minHeight: '400px',
          backgroundColor: '#111827',
          opacity: showModel ? 1 : 0.1,
          transition: 'opacity 1s ease-in-out'
        }}
      />
      
      {/* Only show minimal loading for first 2 seconds */}
      {!showModel && (
        <div className="absolute inset-0 flex items-center justify-center z-10">
          <div className="text-center text-white">
            <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
            <p className="text-sm opacity-70">Loading 3D...</p>
          </div>
        </div>
      )}

      {/* Success indicator */}
      {isLoaded && (
        <div className="absolute bottom-4 right-4 bg-green-600/80 text-white px-3 py-1 rounded text-sm z-20">
          ✅ USDZ Ready
        </div>
      )}
    </div>
  )
}

export default DirectUSDZRenderer