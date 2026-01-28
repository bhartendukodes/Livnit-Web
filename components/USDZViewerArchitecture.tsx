'use client'

/**
 * Production USDZ Viewer Architecture
 * 
 * Key Principles:
 * 1. Clean separation between GLB/GLTF (Three.js) and USDZ (native) pipelines
 * 2. Platform-specific rendering strategies
 * 3. Proper blob management and URL lifecycle
 * 4. Error boundary isolation
 * 5. Performance optimizations
 */

import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react'

// Types
interface USDZAsset {
  blob: Blob
  url: string
  filename: string
  size: number
  type: 'usdz'
}

interface USDZViewerProps {
  usdzBlob: Blob
  filename?: string
  onError?: (error: Error) => void
  onLoad?: () => void
}

// Platform detection utilities
const PlatformUtils = {
  isIOS: () => /iPad|iPhone|iPod/.test(navigator.userAgent),
  isSafari: () => /^((?!chrome|android).)*safari/i.test(navigator.userAgent),
  supportsARQuickLook: () => PlatformUtils.isIOS(),
  supportsModelViewer: () => typeof window !== 'undefined' && 'customElements' in window
}

/**
 * USDZ Asset Manager
 * Handles blob lifecycle, URL management, and cleanup
 */
class USDZAssetManager {
  private assets = new Map<string, USDZAsset>()
  
  createAsset(blob: Blob, filename: string): USDZAsset {
    const id = this.generateAssetId(filename)
    
    // Clean up existing asset with same ID
    if (this.assets.has(id)) {
      this.destroyAsset(id)
    }
    
    const url = URL.createObjectURL(blob)
    const asset: USDZAsset = {
      blob,
      url,
      filename,
      size: blob.size,
      type: 'usdz'
    }
    
    this.assets.set(id, asset)
    return asset
  }
  
  destroyAsset(id: string): void {
    const asset = this.assets.get(id)
    if (asset) {
      URL.revokeObjectURL(asset.url)
      this.assets.delete(id)
    }
  }
  
  getAsset(id: string): USDZAsset | undefined {
    return this.assets.get(id)
  }
  
  private generateAssetId(filename: string): string {
    return `usdz-${filename}-${Date.now()}`
  }
  
  cleanup(): void {
    for (const [id] of this.assets) {
      this.destroyAsset(id)
    }
  }
}

/**
 * iOS AR Quick Look Viewer
 * Native iOS implementation using rel="ar" 
 */
const IOSARViewer: React.FC<{ asset: USDZAsset }> = ({ asset }) => {
  return (
    <div className="relative w-full h-full bg-gradient-to-br from-gray-900 via-purple-900 to-gray-900 rounded-lg overflow-hidden">
      {/* AR Quick Look Link */}
      <a
        href={asset.url}
        rel="ar"
        className="flex flex-col items-center justify-center h-full p-8 text-white hover:bg-purple-800/20 transition-all duration-300 group"
      >
        {/* AR Icon */}
        <div className="relative mb-8 group-hover:scale-110 transition-transform duration-300">
          <div className="w-32 h-32 rounded-full bg-gradient-to-br from-purple-500 to-blue-600 flex items-center justify-center shadow-2xl">
            <div className="text-6xl">🏠</div>
          </div>
          <div className="absolute -top-2 -right-2 bg-green-500 text-white text-xs px-3 py-1 rounded-full font-bold animate-pulse">
            AR
          </div>
        </div>
        
        <h2 className="text-3xl font-bold mb-4 text-center">Tap to View in AR</h2>
        <p className="text-purple-200 text-lg mb-2">{asset.filename}</p>
        <p className="text-purple-300 text-sm mb-8">
          {(asset.size / 1024 / 1024).toFixed(1)} MB
        </p>
        
        <div className="bg-purple-600/90 backdrop-blur-sm px-8 py-4 rounded-2xl shadow-2xl border-2 border-purple-400">
          <p className="font-bold text-xl">🍎 AR Quick Look</p>
        </div>
      </a>
      
      <div className="absolute top-4 right-4 bg-green-600/90 text-white px-4 py-2 rounded-lg text-sm">
        AR Ready
      </div>
    </div>
  )
}

/**
 * Desktop Model Viewer
 * Uses model-viewer with proper error isolation
 */
const DesktopModelViewer: React.FC<{ 
  asset: USDZAsset
  onLoad?: () => void
  onError?: (error: Error) => void
}> = ({ asset, onLoad, onError }) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [hasError, setHasError] = useState(false)
  const [progress, setProgress] = useState(0)
  
  useEffect(() => {
    let cleanup: (() => void) | undefined
    
    const initViewer = async () => {
      try {
        // Load model-viewer if needed
        if (!customElements.get('model-viewer')) {
          await loadModelViewerScript()
        }
        
        cleanup = await createIsolatedModelViewer()
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Failed to initialize viewer')
        setHasError(true)
        setIsLoading(false)
        onError?.(error)
      }
    }
    
    const loadModelViewerScript = (): Promise<void> => {
      return new Promise((resolve, reject) => {
        const script = document.createElement('script')
        script.type = 'module'
        script.src = 'https://unpkg.com/@google/model-viewer@3.4.0/dist/model-viewer.min.js'
        script.onload = () => resolve()
        script.onerror = () => reject(new Error('Failed to load model-viewer'))
        document.head.appendChild(script)
      })
    }
    
    const createIsolatedModelViewer = async (): Promise<() => void> => {
      if (!containerRef.current) throw new Error('Container not available')
      
      // Create isolated error handling
      const errorBoundary = new USDZErrorBoundary()
      
      const modelViewer = document.createElement('model-viewer') as any
      
      // Configure for USDZ
      modelViewer.src = asset.url
      modelViewer.setAttribute('ios-src', asset.url)
      modelViewer.setAttribute('camera-controls', 'true')
      modelViewer.setAttribute('auto-rotate', 'true')
      modelViewer.setAttribute('loading', 'eager')
      modelViewer.setAttribute('reveal', 'interaction')
      
      // Style
      Object.assign(modelViewer.style, {
        width: '100%',
        height: '100%',
        backgroundColor: '#1f2937'
      })
      
      // Events with proper isolation
      const handleLoad = () => {
        console.log('✅ USDZ model loaded successfully')
        setIsLoading(false)
        setProgress(100)
        onLoad?.()
        errorBoundary.clear()
      }
      
      const handleError = (e: any) => {
        // Don't immediately error - USDZ might still render
        setTimeout(() => {
          if (!hasError) {
            console.warn('⚠️ Model-viewer could not parse USDZ (expected behavior)')
            setHasError(true)
            setIsLoading(false)
          }
        }, 2000)
      }
      
      const handleProgress = (e: any) => {
        if (e.detail?.totalProgress) {
          setProgress(Math.round(e.detail.totalProgress * 100))
        }
      }
      
      modelViewer.addEventListener('load', handleLoad)
      modelViewer.addEventListener('error', handleError)  
      modelViewer.addEventListener('progress', handleProgress)
      
      containerRef.current.appendChild(modelViewer)
      
      return () => {
        errorBoundary.clear()
        if (containerRef.current?.contains(modelViewer)) {
          containerRef.current.removeChild(modelViewer)
        }
      }
    }
    
    initViewer()
    
    return cleanup
  }, [asset, onLoad, onError, hasError])
  
  if (hasError) {
    return <DesktopFallbackUI asset={asset} />
  }
  
  return (
    <div className="relative w-full h-full bg-gray-900 rounded-lg overflow-hidden">
      <div ref={containerRef} className="w-full h-full" />
      
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-900/90 z-20">
          <div className="text-center text-white">
            <div className="w-16 h-16 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p>Loading 3D Model... {progress}%</p>
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Desktop Fallback UI
 * Clean fallback when model-viewer fails
 */
const DesktopFallbackUI: React.FC<{ asset: USDZAsset }> = ({ asset }) => (
  <div className="relative w-full h-full bg-gray-900 rounded-lg overflow-hidden flex items-center justify-center">
    <div className="text-center text-white p-8">
      <div className="text-6xl mb-4">📱</div>
      <h3 className="text-xl font-bold mb-4">USDZ Preview</h3>
      <p className="text-gray-300 mb-6">
        This USDZ file is optimized for iOS AR Quick Look
      </p>
      <USDZActionButtons asset={asset} />
    </div>
  </div>
)

/**
 * USDZ Action Buttons
 * Copy, Download, Share functionality
 */
const USDZActionButtons: React.FC<{ asset: USDZAsset }> = ({ asset }) => {
  const [copied, setCopied] = useState(false)
  
  const handleCopy = useCallback(async () => {
    try {
      // Copy blob URL to clipboard
      await navigator.clipboard.writeText(asset.url)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
      // Fallback: select and copy
      const textArea = document.createElement('textarea')
      textArea.value = asset.url
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }, [asset.url])
  
  const handleDownload = useCallback(() => {
    const link = document.createElement('a')
    link.href = asset.url
    link.download = asset.filename
    link.click()
  }, [asset])
  
  const handleShare = useCallback(async () => {
    if (navigator.share && navigator.canShare?.({ files: [new File([asset.blob], asset.filename)] })) {
      try {
        await navigator.share({
          files: [new File([asset.blob], asset.filename)],
          title: 'USDZ 3D Model',
          text: 'Check out this 3D model!'
        })
      } catch (err) {
        console.log('Share cancelled or failed')
      }
    } else {
      // Fallback to copy
      handleCopy()
    }
  }, [asset, handleCopy])
  
  return (
    <div className="space-y-3">
      <button
        onClick={handleDownload}
        className="w-full px-6 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors"
      >
        📥 Download USDZ
      </button>
      
      <div className="flex gap-2">
        <button
          onClick={handleCopy}
          className="flex-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg text-sm transition-colors"
        >
          {copied ? '✅ Copied!' : '📋 Copy Link'}
        </button>
        
        <button
          onClick={handleShare}
          className="flex-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg text-sm transition-colors"
        >
          🔗 Share
        </button>
      </div>
      
      <p className="text-gray-400 text-xs">
        Best viewed on iOS Safari for AR experience
      </p>
    </div>
  )
}

/**
 * Error Boundary for USDZ parsing
 */
class USDZErrorBoundary {
  private originalErrorHandler: typeof window.onerror = null
  private originalConsoleError: typeof console.error = console.error
  
  constructor() {
    this.suppress()
  }
  
  private suppress(): void {
    this.originalErrorHandler = window.onerror
    
    window.onerror = (msg, url, line, col, error) => {
      if (typeof msg === 'string' && (
        msg.includes('PK') || 
        msg.includes('Unexpected token') ||
        msg.includes('is not valid JSON') ||
        msg.includes('GLTFLoader')
      )) {
        // Suppress USDZ parsing errors
        return true
      }
      
      return this.originalErrorHandler ? 
        this.originalErrorHandler(msg, url, line, col, error) : 
        false
    }
  }
  
  clear(): void {
    if (this.originalErrorHandler !== null) {
      window.onerror = this.originalErrorHandler
    }
  }
}

/**
 * Main USDZ Viewer Component
 * Orchestrates platform-specific rendering
 */
const USDZViewer: React.FC<USDZViewerProps> = ({ 
  usdzBlob, 
  filename = 'model.usdz',
  onError,
  onLoad 
}) => {
  const assetManagerRef = useRef<USDZAssetManager>()
  const [asset, setAsset] = useState<USDZAsset | null>(null)
  
  // Initialize asset manager
  if (!assetManagerRef.current) {
    assetManagerRef.current = new USDZAssetManager()
  }
  
  // Platform detection (stable reference)
  const platform = useMemo(() => ({
    isIOS: PlatformUtils.isIOS(),
    supportsAR: PlatformUtils.supportsARQuickLook(),
    supportsModelViewer: PlatformUtils.supportsModelViewer()
  }), [])
  
  // Create asset from blob
  useEffect(() => {
    if (usdzBlob && assetManagerRef.current) {
      const newAsset = assetManagerRef.current.createAsset(usdzBlob, filename)
      setAsset(newAsset)
    }
    
    return () => {
      if (assetManagerRef.current) {
        assetManagerRef.current.cleanup()
      }
    }
  }, [usdzBlob, filename])
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      assetManagerRef.current?.cleanup()
    }
  }, [])
  
  if (!asset) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gray-900 rounded-lg">
        <div className="text-white">Loading USDZ asset...</div>
      </div>
    )
  }
  
  // Platform-specific rendering
  if (platform.isIOS && platform.supportsAR) {
    return <IOSARViewer asset={asset} />
  }
  
  if (platform.supportsModelViewer) {
    return (
      <DesktopModelViewer 
        asset={asset}
        onLoad={onLoad}
        onError={onError}
      />
    )
  }
  
  // Fallback
  return <DesktopFallbackUI asset={asset} />
}

export default USDZViewer
export { USDZAssetManager, PlatformUtils }