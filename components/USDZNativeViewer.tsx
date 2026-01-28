'use client'

import React, { useEffect, useState, useRef } from 'react'

interface USDZNativeViewerProps {
  usdzUrl: string | Blob
  fileName?: string
}

const USDZNativeViewer: React.FC<USDZNativeViewerProps> = ({ 
  usdzUrl,
  fileName = "room.usdz"
}) => {
  const [objectUrl, setObjectUrl] = useState<string>('')
  const [isIOS, setIsIOS] = useState(false)
  const [isSafari, setIsSafari] = useState(false)
  const [showARButton, setShowARButton] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Create object URL from blob
    const url = typeof usdzUrl === 'string' ? usdzUrl : URL.createObjectURL(usdzUrl)
    setObjectUrl(url)
    
    // Detect iOS and Safari
    const userAgent = navigator.userAgent.toLowerCase()
    const iosDevice = /iphone|ipad|ipod/.test(userAgent)
    const safariBrowser = /safari/.test(userAgent) && !/chrome|crios|fxios/.test(userAgent)
    
    setIsIOS(iosDevice)
    setIsSafari(safariBrowser || iosDevice)
    setShowARButton(iosDevice)
    
    return () => {
      if (typeof usdzUrl !== 'string') {
        URL.revokeObjectURL(url)
      }
    }
  }, [usdzUrl])

  const fileSize = typeof usdzUrl === 'object' 
    ? `${(usdzUrl.size / 1024 / 1024).toFixed(1)} MB`
    : 'Unknown'

  // For iOS: Use AR Quick Look
  if (isIOS && objectUrl) {
    return (
      <div className="relative w-full h-full bg-gradient-to-br from-gray-900 via-purple-900 to-gray-900 rounded-lg overflow-hidden">
        <a
          href={objectUrl}
          rel="ar"
          className="flex flex-col items-center justify-center h-full text-center p-8 text-white hover:bg-purple-800/20 transition-colors"
        >
          <div className="mb-8">
            <div className="relative w-32 h-32 mx-auto">
              <div className="absolute inset-0 flex items-center justify-center">
                <svg className="w-24 h-24 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
                </svg>
              </div>
              <div className="absolute -top-2 -right-2 bg-purple-600 text-white text-xs px-3 py-1 rounded-full font-bold">
                3D
              </div>
            </div>
          </div>
          
          <h2 className="text-4xl font-bold mb-4 text-purple-200">✨ Tap to View in AR</h2>
          <p className="text-purple-200 text-xl mb-2">{fileName}</p>
          <p className="text-purple-300 text-sm mb-8">{fileSize}</p>
          
          <div className="bg-purple-600/90 backdrop-blur-sm px-10 py-5 rounded-2xl shadow-2xl border-2 border-purple-400">
            <p className="font-bold text-2xl mb-2">🍎 AR Quick Look</p>
            <p className="text-purple-100 text-sm">Tap anywhere to open in 3D AR viewer</p>
          </div>
        </a>

        <div className="absolute top-4 right-4 bg-green-600/90 text-white px-4 py-2 rounded-lg text-sm z-20">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-green-300 rounded-full animate-pulse"></div>
            <span>AR Ready</span>
          </div>
        </div>
      </div>
    )
  }

  // For Desktop: Show model-viewer with error suppression
  return (
    <div className="relative w-full h-full bg-gray-900 rounded-lg overflow-hidden">
      {/* Model Viewer Container */}
      <div
        ref={containerRef}
        className="w-full h-full"
      />

      {/* Model Viewer Script and Setup */}
      <ModelViewerSetup 
        containerRef={containerRef}
        objectUrl={objectUrl}
        fileName={fileName}
        fileSize={fileSize}
      />
    </div>
  )
}

// Separate component to handle model-viewer setup
const ModelViewerSetup: React.FC<{
  containerRef: React.RefObject<HTMLDivElement>
  objectUrl: string
  fileName: string
  fileSize: string
}> = ({ containerRef, objectUrl, fileName, fileSize }) => {
  const [isLoading, setIsLoading] = useState(true)
  const [progress, setProgress] = useState(0)
  const [modelReady, setModelReady] = useState(false)
  const [hasError, setHasError] = useState(false)

  useEffect(() => {
    if (!objectUrl || !containerRef.current) return

    const initModelViewer = async () => {
      try {
        // Load model-viewer dynamically
        if (typeof window !== 'undefined' && !customElements.get('model-viewer')) {
          const script = document.createElement('script')
          script.type = 'module'
          script.src = 'https://unpkg.com/@google/model-viewer@3.4.0/dist/model-viewer.min.js'
          
          await new Promise((resolve, reject) => {
            script.onload = () => resolve(true)
            script.onerror = () => reject(new Error('Failed to load model-viewer'))
            document.head.appendChild(script)
          })
          
          await new Promise(resolve => setTimeout(resolve, 500))
        }

        // Create model-viewer element
        const modelViewer = document.createElement('model-viewer') as any
        
        // Configure for USDZ - suppress GLTF parsing errors
        modelViewer.src = objectUrl
        modelViewer.setAttribute('ios-src', objectUrl)
        modelViewer.alt = "3D Room Model"
        modelViewer.setAttribute('camera-controls', 'true')
        modelViewer.setAttribute('auto-rotate', 'true')
        modelViewer.setAttribute('shadow-intensity', '1')
        modelViewer.setAttribute('ar', 'true')
        modelViewer.setAttribute('ar-modes', 'webxr scene-viewer quick-look')
        modelViewer.setAttribute('loading', 'eager')
        modelViewer.setAttribute('reveal', 'interaction')
        
        // Suppress GLTF parsing errors by catching them
        const originalErrorHandler = window.onerror
        window.onerror = (msg, url, line, col, error) => {
          // Suppress USDZ/GLTF parsing errors
          if (msg && typeof msg === 'string' && (
            msg.includes('PK') || 
            msg.includes('Unexpected token') ||
            msg.includes('is not valid JSON')
          )) {
            console.warn('⚠️ USDZ parsing warning (expected):', msg)
            return true // Suppress error
          }
          if (originalErrorHandler) {
            return originalErrorHandler(msg, url, line, col, error)
          }
          return false
        }
        
        // Set size
        modelViewer.style.width = '100%'
        modelViewer.style.height = '100%'
        modelViewer.style.backgroundColor = '#1f2937'
        
        // Event listeners
        modelViewer.addEventListener('load', () => {
          console.log('✅ USDZ model loaded successfully!')
          setModelReady(true)
          setIsLoading(false)
          setProgress(100)
          window.onerror = originalErrorHandler // Restore error handler
        })
        
        let errorTimeout: NodeJS.Timeout | null = null
        
        modelViewer.addEventListener('error', (e: any) => {
          console.warn('⚠️ Model-viewer error (may be expected for USDZ):', e)
          // Don't set error immediately - USDZ may still render
          errorTimeout = setTimeout(() => {
            setHasError((prev) => {
              if (!prev) {
                setIsLoading(false)
                return true
              }
              return prev
            })
          }, 3000)
        })
        
        // Clear timeout if model loads successfully
        modelViewer.addEventListener('load', () => {
          if (errorTimeout) {
            clearTimeout(errorTimeout)
          }
        })
        
        modelViewer.addEventListener('progress', (e: any) => {
          if (e.detail && typeof e.detail.totalProgress === 'number') {
            const progressValue = Math.round(e.detail.totalProgress * 100)
            setProgress(progressValue)
          }
        })

        // Add to container
        if (containerRef.current) {
          containerRef.current.appendChild(modelViewer)
        }

        // Cleanup
        return () => {
          window.onerror = originalErrorHandler
          if (containerRef.current && modelViewer.parentNode) {
            containerRef.current.removeChild(modelViewer)
          }
        }

      } catch (err) {
        console.error('❌ Model viewer initialization error:', err)
        setHasError(true)
        setIsLoading(false)
      }
    }

    initModelViewer()
  }, [objectUrl, containerRef])

  return (
    <>
      {/* Loading Overlay */}
      {isLoading && !hasError && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-900/90 backdrop-blur-sm z-20">
          <div className="text-center text-white p-8">
            <div className="relative w-24 h-24 mx-auto mb-6">
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-20 h-20 border-t-4 border-b-4 border-purple-500 rounded-full animate-spin"></div>
              </div>
              <div className="absolute inset-0 flex items-center justify-center text-lg font-bold text-purple-300">
                3D
              </div>
            </div>
            
            <h3 className="text-2xl font-bold mb-2 text-purple-300">🏠 Loading 3D Room</h3>
            <p className="text-gray-300 text-lg mb-1">{fileName}</p>
            <p className="text-gray-400 text-sm mb-6">{fileSize}</p>
            
            <div className="w-80 max-w-full mx-auto mb-4">
              <div className="flex justify-between text-sm text-gray-400 mb-2">
                <span>Loading...</span>
                <span>{progress}%</span>
              </div>
              <div className="h-3 bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-purple-500 to-blue-500 rounded-full transition-all duration-500"
                  style={{ width: `${progress}%` }}
                ></div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Error State */}
      {hasError && !modelReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-900/90 backdrop-blur-sm z-20">
          <div className="text-center text-white bg-gray-800/90 rounded-lg p-8 max-w-md mx-4">
            <div className="text-purple-400 text-5xl mb-4">📱</div>
            <h3 className="text-xl font-bold mb-3">USDZ Preview</h3>
            <p className="text-gray-300 mb-4">
              USDZ files work best on iOS devices with Safari browser.
            </p>
            <a
              href={objectUrl}
              download={fileName}
              className="inline-block px-6 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors mb-4"
            >
              📥 Download USDZ File
            </a>
            <p className="text-gray-400 text-sm">
              Open in iOS Safari or 3D modeling software
            </p>
          </div>
        </div>
      )}

      {/* Success State */}
      {modelReady && (
        <>
          <div className="absolute top-4 right-4 bg-green-600/90 text-white px-4 py-2 rounded-lg text-sm z-30">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-green-300 rounded-full animate-pulse"></div>
              <span>3D Model Ready</span>
            </div>
          </div>

          <div className="absolute bottom-4 left-4 bg-black/80 text-white px-4 py-3 rounded-lg text-sm z-30">
            <h4 className="font-semibold mb-2">🎮 3D Controls</h4>
            <div className="text-gray-300 text-xs space-y-1">
              <div>• Drag to rotate</div>
              <div>• Scroll to zoom</div>
            </div>
          </div>
        </>
      )}
    </>
  )
}

export default USDZNativeViewer