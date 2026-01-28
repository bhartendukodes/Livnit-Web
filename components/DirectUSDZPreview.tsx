'use client'

import React, { useState, useEffect, useRef } from 'react'

interface DirectUSDZPreviewProps {
  usdzUrl: string | Blob
  className?: string
  fileName?: string
}

const DirectUSDZPreview: React.FC<DirectUSDZPreviewProps> = ({ 
  usdzUrl,
  className = "w-full h-full",
  fileName = "room.usdz"
}) => {
  const [isModelLoaded, setIsModelLoaded] = useState(false)
  const [loadingProgress, setLoadingProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const modelViewerRef = useRef<any>(null)
  
  // Convert Blob to URL if needed
  const fileUrl = typeof usdzUrl === 'string' 
    ? usdzUrl 
    : URL.createObjectURL(usdzUrl)

  useEffect(() => {
    // Simulate loading progress
    const progressInterval = setInterval(() => {
      setLoadingProgress(prev => {
        if (prev >= 90) return prev
        return prev + Math.random() * 10
      })
    }, 200)

    // Auto-complete loading after 3 seconds if model doesn't load
    const fallbackTimeout = setTimeout(() => {
      setIsModelLoaded(true)
      setLoadingProgress(100)
    }, 3000)

    return () => {
      clearInterval(progressInterval)
      clearTimeout(fallbackTimeout)
    }
  }, [])

  const handleModelLoad = () => {
    console.log('✅ USDZ model loaded successfully!')
    setIsModelLoaded(true)
    setLoadingProgress(100)
    setError(null)
  }

  const handleModelError = (event: any) => {
    console.error('❌ USDZ model error:', event)
    setError('Failed to load USDZ model')
    setIsModelLoaded(true) // Show anyway
    setLoadingProgress(100)
  }

  return (
    <div className={`${className} relative bg-black rounded-lg overflow-hidden`}>
      {/* Model Viewer - Always render but hidden until loaded */}
      <div 
        className={`transition-opacity duration-500 ${isModelLoaded ? 'opacity-100' : 'opacity-0'}`}
        style={{ width: '100%', height: '100%' }}
      >
        <model-viewer
          ref={modelViewerRef}
          src={fileUrl}
          ios-src={fileUrl}
          alt="USDZ 3D Model"
          auto-rotate
          camera-controls
          shadow-intensity="1"
          loading="eager"
          reveal="auto"
          style={{ 
            width: '100%', 
            height: '100%',
            backgroundColor: '#000000',
            display: 'block'
          }}
          onLoad={handleModelLoad}
          onError={handleModelError}
        />
      </div>

      {/* Loading Overlay - Show until model loads */}
      {!isModelLoaded && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-900 z-10">
          <div className="text-center">
            {/* Animated Loading Icon */}
            <div className="relative mb-6">
              <div className="animate-spin rounded-full h-16 w-16 border-4 border-purple-600 border-t-transparent"></div>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-white text-xs font-medium">{Math.round(loadingProgress)}%</span>
              </div>
            </div>
            
            {/* Loading Text */}
            <h3 className="text-xl font-bold text-white mb-2">Loading 3D Model</h3>
            <p className="text-gray-400 text-sm mb-4">{fileName}</p>
            
            {/* Progress Bar */}
            <div className="w-64 bg-gray-700 rounded-full h-2 mb-4">
              <div 
                className="bg-purple-600 h-2 rounded-full transition-all duration-200"
                style={{ width: `${loadingProgress}%` }}
              />
            </div>
            
            {/* Loading Steps */}
            <div className="text-xs text-gray-500 space-y-1">
              <p className={loadingProgress > 20 ? 'text-green-400' : ''}>
                {loadingProgress > 20 ? '✓' : '◦'} Initializing 3D viewer...
              </p>
              <p className={loadingProgress > 50 ? 'text-green-400' : ''}>
                {loadingProgress > 50 ? '✓' : '◦'} Loading USDZ file...
              </p>
              <p className={loadingProgress > 80 ? 'text-green-400' : ''}>
                {loadingProgress > 80 ? '✓' : '◦'} Rendering 3D scene...
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Error State */}
      {error && isModelLoaded && (
        <div className="absolute top-4 left-4 bg-red-600/90 text-white px-4 py-2 rounded-lg text-sm">
          <p>⚠️ {error}</p>
          <p className="text-xs mt-1 opacity-75">Model may still be visible</p>
        </div>
      )}

      {/* Success Indicator */}
      {isModelLoaded && !error && (
        <div className="absolute top-4 right-4 bg-green-600/90 text-white px-3 py-2 rounded-lg text-sm flex items-center gap-2 z-20">
          <div className="w-2 h-2 bg-green-300 rounded-full animate-pulse"></div>
          <span>3D Model Ready</span>
        </div>
      )}

      {/* Controls Info */}
      {isModelLoaded && (
        <div className="absolute bottom-4 left-4 bg-black/70 backdrop-blur-sm text-white px-4 py-2 rounded-lg text-sm z-20">
          <div className="space-y-1">
            <p>🖱️ Click & drag to rotate</p>
            <p>🔍 Scroll to zoom</p>
            <p>📱 Tap for AR (iOS)</p>
          </div>
        </div>
      )}

      {/* iOS Quick Look - Hidden but functional */}
      <a
        href={fileUrl}
        rel="ar"
        className="absolute inset-0 opacity-0 pointer-events-none"
        style={{ zIndex: -1 }}
        aria-label="View in AR"
      >
        <span className="sr-only">Open in AR</span>
      </a>
    </div>
  )
}

export default DirectUSDZPreview