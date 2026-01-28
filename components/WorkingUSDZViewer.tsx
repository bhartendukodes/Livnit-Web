'use client'

import React, { useEffect, useRef, useState } from 'react'

interface WorkingUSDZViewerProps {
  usdzUrl: string | Blob
  fileName?: string
}

const WorkingUSDZViewer: React.FC<WorkingUSDZViewerProps> = ({ 
  usdzUrl,
  fileName = "room.usdz"
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const [objectUrl, setObjectUrl] = useState<string>('')
  const [isLoading, setIsLoading] = useState(true)
  const [progress, setProgress] = useState(0)
  const [modelReady, setModelReady] = useState(false)
  const [error, setError] = useState<string>('')

  useEffect(() => {
    // Create object URL from blob
    const url = typeof usdzUrl === 'string' ? usdzUrl : URL.createObjectURL(usdzUrl)
    setObjectUrl(url)
    console.log('🔗 Object URL created:', url)
    
    return () => {
      if (typeof usdzUrl !== 'string') {
        URL.revokeObjectURL(url)
      }
    }
  }, [usdzUrl])

  useEffect(() => {
    if (!objectUrl || !containerRef.current) return

    const initModelViewer = async () => {
      try {
        // Load model-viewer dynamically
        if (typeof window !== 'undefined' && !customElements.get('model-viewer')) {
          console.log('📦 Loading model-viewer script...')
          
          const script = document.createElement('script')
          script.type = 'module'
          script.src = 'https://unpkg.com/@google/model-viewer@3.4.0/dist/model-viewer.min.js'
          
          await new Promise((resolve, reject) => {
            script.onload = () => {
              console.log('✅ Model-viewer loaded successfully')
              resolve(true)
            }
            script.onerror = () => {
              console.error('❌ Failed to load model-viewer')
              reject(new Error('Failed to load model-viewer'))
            }
            document.head.appendChild(script)
          })
          
          // Wait a bit for custom element to register
          await new Promise(resolve => setTimeout(resolve, 500))
        }

        // Create model-viewer element
        const modelViewer = document.createElement('model-viewer') as any
        
        // Configure for USDZ
        modelViewer.src = objectUrl
        modelViewer.setAttribute('ios-src', objectUrl)
        modelViewer.alt = "3D Room Model"
        modelViewer.setAttribute('camera-controls', true)
        modelViewer.setAttribute('auto-rotate', true)
        modelViewer.setAttribute('shadow-intensity', '1')
        modelViewer.setAttribute('ar', true)
        modelViewer.setAttribute('ar-modes', 'webxr scene-viewer quick-look')
        modelViewer.setAttribute('loading', 'eager')
        modelViewer.setAttribute('reveal', 'interaction')
        
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
        })
        
        modelViewer.addEventListener('error', (e: any) => {
          console.error('❌ Model loading error:', e)
          setError('Failed to load 3D model')
          setIsLoading(false)
        })
        
        modelViewer.addEventListener('progress', (e: any) => {
          if (e.detail && typeof e.detail.totalProgress === 'number') {
            const progressValue = Math.round(e.detail.totalProgress * 100)
            setProgress(progressValue)
            console.log(`📊 Loading progress: ${progressValue}%`)
          }
        })

        // Add to container
        if (containerRef.current) {
          containerRef.current.appendChild(modelViewer)
          console.log('🎬 Model-viewer added to DOM')
        }

        // Cleanup function
        return () => {
          if (containerRef.current && modelViewer.parentNode) {
            containerRef.current.removeChild(modelViewer)
          }
        }

      } catch (err) {
        console.error('❌ Model viewer initialization error:', err)
        setError('Failed to initialize 3D viewer')
        setIsLoading(false)
      }
    }

    initModelViewer()
  }, [objectUrl])

  const fileSize = typeof usdzUrl === 'object' 
    ? `${(usdzUrl.size / 1024 / 1024).toFixed(1)} MB`
    : 'Unknown'

  return (
    <div className="relative w-full h-full bg-gray-900 rounded-lg overflow-hidden">
      
      {/* Model Viewer Container */}
      <div
        ref={containerRef}
        className="w-full h-full"
        style={{
          opacity: modelReady ? 1 : 0.1,
          transition: 'opacity 0.8s ease-in-out'
        }}
      />

      {/* Loading Overlay */}
      {isLoading && !error && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-900/90 backdrop-blur-sm z-20">
          <div className="text-center text-white p-8">
            {/* Animated 3D Icon */}
            <div className="relative w-24 h-24 mx-auto mb-6">
              <div className="absolute inset-0 flex items-center justify-center">
                <div 
                  className="w-20 h-20 border-t-4 border-b-4 border-purple-500 rounded-full animate-spin"
                  style={{ animationDuration: '1.5s' }}
                ></div>
              </div>
              <div className="absolute inset-0 flex items-center justify-center">
                <div 
                  className="w-12 h-12 border-t-2 border-b-2 border-blue-400 rounded-full animate-spin"
                  style={{ animationDuration: '1s', animationDirection: 'reverse' }}
                ></div>
              </div>
              <div className="absolute inset-0 flex items-center justify-center text-lg font-bold text-purple-300">
                3D
              </div>
            </div>
            
            <h3 className="text-2xl font-bold mb-2 text-purple-300">🏠 Loading 3D Room</h3>
            <p className="text-gray-300 text-lg mb-1">{fileName}</p>
            <p className="text-gray-400 text-sm mb-6">{fileSize}</p>
            
            {/* Progress Bar */}
            <div className="w-80 max-w-full mx-auto mb-4">
              <div className="flex justify-between text-sm text-gray-400 mb-2">
                <span>Loading...</span>
                <span>{progress}%</span>
              </div>
              <div className="h-3 bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-purple-500 to-blue-500 rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${progress}%` }}
                ></div>
              </div>
            </div>
            
            <div className="text-gray-400 text-sm">
              <div className="mb-2">📦 Parsing USDZ geometry...</div>
              <div>🎨 Loading materials and textures...</div>
            </div>
          </div>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-red-900/20 backdrop-blur-sm z-20">
          <div className="text-center text-white bg-red-900/90 rounded-lg p-8 max-w-md mx-4">
            <div className="text-red-400 text-5xl mb-4">🚫</div>
            <h3 className="text-xl font-bold mb-3">Preview Failed</h3>
            <p className="text-red-200 mb-4">{error}</p>
            <div className="bg-red-800/50 rounded-lg p-4 text-sm">
              <p className="text-gray-300 mb-2">
                <strong>Alternative options:</strong>
              </p>
              <ul className="text-gray-300 text-left space-y-1">
                <li>📱 Try on iOS Safari for AR preview</li>
                <li>💾 Download and open in 3D software</li>
                <li>🔧 Check if file is corrupted</li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Success State - Model Ready */}
      {modelReady && (
        <>
          {/* Status Badge */}
          <div className="absolute top-4 right-4 z-30">
            <div className="bg-green-600/90 backdrop-blur-sm text-white px-4 py-2 rounded-lg text-sm font-medium shadow-lg">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-green-300 rounded-full animate-pulse"></div>
                <span>🎯 3D Model Ready</span>
              </div>
            </div>
          </div>

          {/* Controls Guide */}
          <div className="absolute bottom-4 left-4 bg-black/80 backdrop-blur-sm text-white px-4 py-3 rounded-lg text-sm z-30 max-w-xs">
            <h4 className="font-semibold mb-2 text-green-300">🎮 3D Controls</h4>
            <div className="text-gray-300 text-xs space-y-1">
              <div>• <strong>Drag:</strong> Rotate model</div>
              <div>• <strong>Scroll:</strong> Zoom in/out</div>
              <div>• <strong>Double-tap:</strong> AR mode (iOS)</div>
              <div>• <strong>Auto-rotate:</strong> Enabled</div>
            </div>
          </div>

          {/* File Info */}
          <div className="absolute bottom-4 right-4 bg-black/80 backdrop-blur-sm text-white px-4 py-3 rounded-lg text-sm z-30">
            <div className="text-center">
              <div className="font-semibold text-green-300">{fileName}</div>
              <div className="text-gray-400 text-xs">{fileSize} • USDZ Format</div>
              <div className="text-green-400 text-xs mt-1">✅ 3D Preview Active</div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default WorkingUSDZViewer