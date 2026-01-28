'use client'

import React, { useState, useEffect } from 'react'

interface PureUSDZViewerProps {
  usdzUrl: string | Blob
  fileName?: string
}

const PureUSDZViewer: React.FC<PureUSDZViewerProps> = ({ 
  usdzUrl,
  fileName = "room.usdz"
}) => {
  const [fileObjectUrl, setFileObjectUrl] = useState<string>('')
  const [isIOS, setIsIOS] = useState(false)
  
  useEffect(() => {
    // Create object URL if needed
    const url = typeof usdzUrl === 'string' 
      ? usdzUrl 
      : URL.createObjectURL(usdzUrl)
    
    setFileObjectUrl(url)
    
    // Detect iOS for AR Quick Look
    const userAgent = navigator.userAgent.toLowerCase()
    const iosDevice = /iphone|ipad|ipod/.test(userAgent)
    setIsIOS(iosDevice)
    
    return () => {
      if (typeof usdzUrl !== 'string') {
        URL.revokeObjectURL(url)
      }
    }
  }, [usdzUrl])

  const handleARClick = () => {
    console.log('🍎 Opening USDZ in AR Quick Look...')
  }

  const fileSize = typeof usdzUrl === 'object' 
    ? `${(usdzUrl.size / 1024 / 1024).toFixed(1)} MB`
    : 'Unknown size'

  return (
    <div className="relative w-full h-full bg-gradient-to-br from-gray-900 via-purple-900 to-gray-900 rounded-lg overflow-hidden">
      
      {isIOS ? (
        /* iOS: AR Quick Look Interface */
        <a
          href={fileObjectUrl}
          rel="ar"
          onClick={handleARClick}
          className="flex flex-col items-center justify-center h-full text-center p-8 text-white hover:bg-purple-800/20 transition-colors"
        >
          <div className="mb-6">
            <svg className="w-24 h-24 mx-auto text-purple-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
            </svg>
          </div>
          
          <h2 className="text-3xl font-bold mb-4">✨ Tap to View in AR</h2>
          <p className="text-purple-200 text-lg mb-2">{fileName}</p>
          <p className="text-purple-300 text-sm mb-6">{fileSize}</p>
          
          <div className="bg-purple-600 px-8 py-4 rounded-xl shadow-lg">
            <p className="font-semibold text-lg">🍎 AR Quick Look Ready</p>
            <p className="text-purple-100 text-sm mt-1">Tap to open in 3D AR viewer</p>
          </div>
        </a>
      ) : (
        /* Non-iOS: Download Interface with Preview */
        <div className="flex flex-col items-center justify-center h-full text-center p-8 text-white">
          {/* USDZ File Icon */}
          <div className="mb-6">
            <div className="relative">
              <svg className="w-24 h-24 mx-auto text-purple-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
              </svg>
              
              {/* 3D Indicator */}
              <div className="absolute -top-2 -right-2 bg-purple-600 text-white text-xs px-2 py-1 rounded-full font-bold">
                3D
              </div>
            </div>
          </div>
          
          <h2 className="text-3xl font-bold mb-4">🏠 USDZ Room Ready</h2>
          <p className="text-purple-200 text-lg mb-2">{fileName}</p>
          <p className="text-purple-300 text-sm mb-6">{fileSize}</p>
          
          <div className="space-y-4 max-w-md">
            {/* Download Button */}
            <a
              href={fileObjectUrl}
              download={fileName}
              className="block w-full px-8 py-4 bg-purple-600 hover:bg-purple-700 text-white rounded-xl font-semibold text-lg shadow-lg transition-colors"
            >
              📥 Download USDZ File
            </a>
            
            {/* Instructions */}
            <div className="bg-gray-800/50 backdrop-blur-sm rounded-lg p-4 text-sm">
              <h3 className="font-semibold mb-2 text-purple-200">🎯 How to View:</h3>
              <ul className="text-gray-300 space-y-1 text-left">
                <li>📱 <strong>iOS/Safari:</strong> Tap to open in AR</li>
                <li>🖥️ <strong>Desktop:</strong> Download and use 3D viewer</li>
                <li>🎨 <strong>Blender:</strong> Import USDZ for editing</li>
                <li>📐 <strong>CAD Apps:</strong> Open in 3D modeling software</li>
              </ul>
            </div>

            {/* File Details */}
            <div className="bg-black/30 rounded-lg p-3 text-xs text-gray-400">
              <div className="grid grid-cols-2 gap-2">
                <div><strong>Format:</strong> USDZ</div>
                <div><strong>Size:</strong> {fileSize}</div>
                <div><strong>3D Model:</strong> ✓ Ready</div>
                <div><strong>AR Ready:</strong> ✓ iOS Compatible</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Status Indicator */}
      <div className="absolute top-4 right-4 bg-green-600/90 text-white px-3 py-2 rounded-lg text-sm flex items-center gap-2">
        <div className="w-2 h-2 bg-green-300 rounded-full animate-pulse"></div>
        <span>USDZ Ready</span>
      </div>

      {/* File Info Badge */}
      <div className="absolute bottom-4 left-4 bg-black/70 backdrop-blur-sm text-white px-4 py-2 rounded-lg text-sm">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span>{fileName}</span>
        </div>
      </div>
    </div>
  )
}

export default PureUSDZViewer