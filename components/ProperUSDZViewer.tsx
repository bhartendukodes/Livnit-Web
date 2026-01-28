'use client'

import React, { useEffect, useState, useRef } from 'react'

interface ProperUSDZViewerProps {
  usdzBlob: Blob | File
  previewImage?: string // Optional preview image from pipeline
  fileName?: string
}

const ProperUSDZViewer: React.FC<ProperUSDZViewerProps> = ({ 
  usdzBlob, 
  previewImage,
  fileName = 'room.usdz'
}) => {
  const [objectUrl, setObjectUrl] = useState<string>('')
  const [isIOS, setIsIOS] = useState(false)
  const [supportsAR, setSupportsAR] = useState(false)
  const [previewImageUrl, setPreviewImageUrl] = useState<string>('')
  const containerRef = useRef<HTMLDivElement>(null)

  // Detect iOS and AR support
  useEffect(() => {
    const userAgent = navigator.userAgent.toLowerCase()
    const iosDevice = /iphone|ipad|ipod/.test(userAgent) || 
                     (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1) // iPad on iOS 13+
    setIsIOS(iosDevice)

    // Check AR Quick Look support
    const a = document.createElement('a')
    if (a.relList && a.relList.supports('ar')) {
      setSupportsAR(true)
      console.log('✅ AR Quick Look is supported')
    } else {
      console.log('⚠️ AR Quick Look not supported')
    }
  }, [])

  // Create object URL for USDZ
  useEffect(() => {
    if (usdzBlob && usdzBlob.size > 0) {
      const url = URL.createObjectURL(usdzBlob)
      setObjectUrl(url)
      console.log('🔗 USDZ Object URL created, size:', (usdzBlob.size / 1024 / 1024).toFixed(1), 'MB')
      
      return () => {
        URL.revokeObjectURL(url)
      }
    }
  }, [usdzBlob])

  // Handle preview image
  useEffect(() => {
    if (previewImage) {
      setPreviewImageUrl(previewImage)
    } else {
      // Create a placeholder image if no preview
      const canvas = document.createElement('canvas')
      canvas.width = 800
      canvas.height = 600
      const ctx = canvas.getContext('2d')
      if (ctx) {
        // Gradient background
        const gradient = ctx.createLinearGradient(0, 0, 800, 600)
        gradient.addColorStop(0, '#1f2937')
        gradient.addColorStop(1, '#111827')
        ctx.fillStyle = gradient
        ctx.fillRect(0, 0, 800, 600)
        
        // Text
        ctx.fillStyle = '#ffffff'
        ctx.font = 'bold 48px Arial'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText('3D Room Model', 400, 250)
        
        ctx.font = '24px Arial'
        ctx.fillStyle = '#9ca3af'
        ctx.fillText('Tap to view in AR (iOS)', 400, 320)
        ctx.fillText('or download to view', 400, 360)
        
        setPreviewImageUrl(canvas.toDataURL())
      }
    }
  }, [previewImage])

  // Handle download
  const handleDownload = () => {
    if (objectUrl) {
      const link = document.createElement('a')
      link.href = objectUrl
      link.download = fileName
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      console.log('📥 USDZ download initiated')
    }
  }

  const fileSize = (usdzBlob.size / 1024 / 1024).toFixed(1)

  // iOS with AR Quick Look support
  if (isIOS && supportsAR && objectUrl && previewImageUrl) {
    return (
      <div className="relative w-full h-full bg-gray-900 rounded-lg overflow-hidden">
        <a
          href={objectUrl}
          rel="ar"
          className="block w-full h-full"
          style={{
            display: 'block',
            width: '100%',
            height: '100%',
            position: 'relative'
          }}
        >
          <img
            src={previewImageUrl}
            alt="3D Room Model - Tap to view in AR"
            className="w-full h-full object-cover"
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover'
            }}
          />
          {/* AR Badge Overlay */}
          <div className="absolute top-4 right-4 bg-black/70 backdrop-blur-sm rounded-lg px-4 py-2 flex items-center gap-2">
            <svg 
              width="24" 
              height="24" 
              viewBox="0 0 24 24" 
              fill="none" 
              stroke="currentColor" 
              strokeWidth="2"
              className="text-white"
            >
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
            <span className="text-white font-medium">Tap to View in AR</span>
          </div>
          {/* File Info */}
          <div className="absolute bottom-4 left-4 bg-black/70 backdrop-blur-sm rounded-lg px-4 py-2">
            <p className="text-white text-sm font-medium">{fileName}</p>
            <p className="text-gray-400 text-xs">{fileSize} MB</p>
          </div>
        </a>
      </div>
    )
  }

  // Desktop/Non-iOS - Show preview with download option
  return (
    <div className="relative w-full h-full bg-gray-900 rounded-lg overflow-hidden">
      {/* Preview Image */}
      {previewImageUrl && (
        <div className="w-full h-full relative">
          <img
            src={previewImageUrl}
            alt="3D Room Model Preview"
            className="w-full h-full object-cover"
          />
          
          {/* Overlay with Info and Download */}
          <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent">
            {/* Info at top */}
            <div className="absolute top-4 left-4 bg-black/70 backdrop-blur-sm rounded-lg px-4 py-2">
              <p className="text-white text-sm font-medium">{fileName}</p>
              <p className="text-gray-400 text-xs">{fileSize} MB • USDZ Format</p>
            </div>

            {/* Download Button at bottom */}
            <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2">
              <button
                onClick={handleDownload}
                className="bg-purple-600 hover:bg-purple-700 text-white px-6 py-3 rounded-lg font-medium flex items-center gap-2 transition-colors shadow-lg"
              >
                <svg 
                  width="20" 
                  height="20" 
                  viewBox="0 0 24 24" 
                  fill="none" 
                  stroke="currentColor" 
                  strokeWidth="2"
                >
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>
                </svg>
                Download USDZ
              </button>
            </div>

            {/* Info Message */}
            <div className="absolute bottom-20 left-1/2 transform -translate-x-1/2 text-center">
              <p className="text-white text-sm mb-1">USDZ Preview</p>
              <p className="text-gray-300 text-xs">
                {isIOS 
                  ? 'AR Quick Look not available. Download to view on device.'
                  : 'Download to view in AR (iOS) or 3D viewer'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Loading State */}
      {!previewImageUrl && (
        <div className="w-full h-full flex items-center justify-center">
          <div className="text-center">
            <div className="w-12 h-12 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-white font-medium">Preparing USDZ Preview...</p>
            <p className="text-gray-400 text-sm mt-2">{fileSize} MB</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default ProperUSDZViewer
