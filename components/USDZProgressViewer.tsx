'use client'

import React, { useEffect, useRef, useState } from 'react'

interface USDZProgressViewerProps {
  usdzBlob: Blob
  isDownloading?: boolean
  downloadProgress?: number
}

const USDZProgressViewer: React.FC<USDZProgressViewerProps> = ({ 
  usdzBlob,
  isDownloading = false,
  downloadProgress = 0
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const [objectUrl, setObjectUrl] = useState<string>('')
  const [renderAttempt, setRenderAttempt] = useState<'loading' | 'model-viewer' | 'fallback'>('loading')
  const [modelLoaded, setModelLoaded] = useState(false)

  // Create object URL immediately when blob is available
  useEffect(() => {
    if (usdzBlob) {
      const url = URL.createObjectURL(usdzBlob)
      setObjectUrl(url)
      console.log('🔗 USDZ URL created:', url, 'Size:', (usdzBlob.size / 1024 / 1024).toFixed(1), 'MB')
      
      // Start rendering attempt
      setRenderAttempt('model-viewer')
      
      return () => URL.revokeObjectURL(url)
    }
  }, [usdzBlob])

  // Attempt model-viewer rendering
  useEffect(() => {
    if (renderAttempt !== 'model-viewer' || !objectUrl || !containerRef.current) return

    console.log('🎬 Attempting model-viewer render...')
    
    const attemptRender = async () => {
      try {
        // Clear any existing content
        containerRef.current!.innerHTML = ''
        
        // Suppress ALL console errors during model-viewer attempt
        const originalError = console.error
        console.error = () => {}
        
        // Load model-viewer script if needed
        if (!customElements.get('model-viewer')) {
          const script = document.createElement('script')
          script.type = 'module' 
          script.src = 'https://unpkg.com/@google/model-viewer@3.5.0/dist/model-viewer.min.js'
          document.head.appendChild(script)
          
          // Wait for script to load
          await new Promise(resolve => {
            script.onload = resolve
            setTimeout(resolve, 3000) // Max wait 3 seconds
          })
        }

        // Create model-viewer element
        const modelViewer = document.createElement('model-viewer')
        
        // Configure for USDZ
        modelViewer.setAttribute('src', objectUrl)
        modelViewer.setAttribute('ios-src', objectUrl) 
        modelViewer.setAttribute('alt', '3D Room Model')
        modelViewer.setAttribute('camera-controls', '')
        modelViewer.setAttribute('auto-rotate', '')
        modelViewer.setAttribute('loading', 'eager')
        modelViewer.setAttribute('reveal', 'auto')
        
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
        let loadTimeout: NodeJS.Timeout
        
        const onLoad = () => {
          console.log('✅ Model-viewer loaded successfully!')
          setModelLoaded(true)
          clearTimeout(loadTimeout)
          console.error = originalError
        }
        
        const onError = (e: any) => {
          console.warn('⚠️ Model-viewer failed, switching to fallback')
          console.log('Error details:', e)
          clearTimeout(loadTimeout)
          console.error = originalError
          // Force fallback immediately
          setTimeout(() => setRenderAttempt('fallback'), 100)
        }
        
        modelViewer.addEventListener('load', onLoad)
        modelViewer.addEventListener('error', onError)
        
        // Add to container
        containerRef.current!.appendChild(modelViewer)
        
        // Fallback timeout - if no load event in 3 seconds, show fallback
        loadTimeout = setTimeout(() => {
          console.warn('⏰ Model-viewer timeout, switching to fallback')
          console.error = originalError
          setRenderAttempt('fallback')
        }, 3000)
        
      } catch (error) {
        console.error('❌ Model-viewer setup failed:', error)
        // Force fallback immediately on setup failure
        setTimeout(() => setRenderAttempt('fallback'), 100)
      }
    }

    attemptRender()
  }, [renderAttempt, objectUrl])

  // Show download progress while downloading
  if (isDownloading) {
    return (
      <div className="relative w-full h-full bg-gray-900 rounded-lg flex items-center justify-center">
        <div className="text-center text-white">
          <div className="relative w-20 h-20 mx-auto mb-6">
            <svg className="w-20 h-20 animate-spin text-purple-500" fill="none" viewBox="0 0 24 24">
              <circle
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="2"
                strokeDasharray="60"
                strokeDashoffset="15"
                strokeLinecap="round"
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center text-lg font-bold">
              {downloadProgress}%
            </div>
          </div>
          
          <h3 className="text-xl font-bold mb-2">🏗️ Processing Room</h3>
          <p className="text-gray-300">Downloading 3D model...</p>
          
          <div className="w-64 h-2 bg-gray-700 rounded-full mx-auto mt-4">
            <div 
              className="h-full bg-purple-500 rounded-full transition-all duration-300"
              style={{ width: `${downloadProgress}%` }}
            />
          </div>
        </div>
      </div>
    )
  }

  // Show loading state while setting up viewer
  if (renderAttempt === 'loading') {
    return (
      <div className="relative w-full h-full bg-gray-900 rounded-lg flex items-center justify-center">
        <div className="text-center text-white">
          <div className="w-12 h-12 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p>Setting up 3D viewer...</p>
        </div>
      </div>
    )
  }

  // Show model-viewer container
  if (renderAttempt === 'model-viewer') {
    return (
      <div className="relative w-full h-full bg-gray-900 rounded-lg overflow-hidden">
        <div 
          ref={containerRef}
          className="w-full h-full"
          style={{ minHeight: '400px' }}
        />
        
        {/* Show loading overlay until model loads */}
        {!modelLoaded && (
          <div className="absolute inset-0 bg-gray-900/80 flex items-center justify-center">
            <div className="text-center text-white">
              <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
              <p className="text-sm">Loading 3D model...</p>
            </div>
          </div>
        )}
        
        {/* Model loaded indicator */}
        {modelLoaded && (
          <div className="absolute bottom-4 right-4 bg-green-600/90 text-white px-3 py-2 rounded-lg text-sm">
            ✅ 3D Model Ready
          </div>
        )}
      </div>
    )
  }

  // Fallback: Direct download interface (ALWAYS show if we have objectUrl)
  if (renderAttempt === 'fallback' && objectUrl) {
    return (
      <div className="relative w-full h-full bg-gray-900 rounded-lg flex items-center justify-center">
        <div className="text-center text-white p-8">
          <div className="text-6xl mb-6">🏠</div>
          <h3 className="text-2xl font-bold mb-4">USDZ Room Model Ready</h3>
          <p className="text-gray-300 mb-6">
            {(usdzBlob.size / 1024 / 1024).toFixed(1)} MB • Generated successfully
          </p>
          
          <div className="space-y-4">
            <a
              href={objectUrl}
              download="generated_room.usdz"
              className="inline-block px-8 py-4 bg-purple-600 hover:bg-purple-700 text-white rounded-xl font-bold text-lg transition-colors shadow-lg"
            >
              📥 Download USDZ File
            </a>
            
            <div className="bg-gray-800/50 rounded-lg p-4 text-sm max-w-md mx-auto">
              <h4 className="font-semibold mb-2 text-purple-200">🎯 How to View:</h4>
              <ul className="text-gray-300 text-left space-y-1">
                <li>📱 <strong>iOS Safari:</strong> Tap file → View in AR</li>
                <li>🖥️ <strong>Blender:</strong> File → Import → Universal Scene Description</li>
                <li>🎮 <strong>Reality Composer:</strong> Import for AR editing</li>
                <li>💻 <strong>USD View:</strong> Pixar&apos;s official USDZ viewer</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Default fallback - if we have objectUrl but no render attempt, force fallback
  if (objectUrl) {
    console.log('🚨 Default fallback triggered - forcing download interface')
    return (
      <div className="relative w-full h-full bg-gray-900 rounded-lg flex items-center justify-center">
        <div className="text-center text-white p-8">
          <div className="text-6xl mb-6">🏠</div>
          <h3 className="text-2xl font-bold mb-4">USDZ Room Model</h3>
          <p className="text-gray-300 mb-6">
            {(usdzBlob.size / 1024 / 1024).toFixed(1)} MB • Ready for download
          </p>
          
          <a
            href={objectUrl}
            download="generated_room.usdz"
            className="inline-block px-8 py-4 bg-purple-600 hover:bg-purple-700 text-white rounded-xl font-bold text-lg transition-colors shadow-lg"
          >
            📥 Download USDZ File
          </a>
          
          <p className="text-gray-400 text-sm mt-4">
            Open in iOS Safari for AR preview or import into 3D software
          </p>
        </div>
      </div>
    )
  }

  // Final fallback
  return (
    <div className="relative w-full h-full bg-gray-900 rounded-lg flex items-center justify-center">
      <div className="text-white text-center">
        <p>Setting up USDZ viewer...</p>
      </div>
    </div>
  )
}

export default USDZProgressViewer