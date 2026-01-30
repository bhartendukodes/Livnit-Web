'use client'

import React, { useEffect, useState } from 'react'
import { PipelineResult } from '../services/ApiClient'
import SimpleGLBViewer from './SimpleGLBViewer'

interface RoomViewProps {
  roomImage?: string
  usdzFile?: File | null
  finalUsdzBlob?: Blob | null
  finalGlbBlob?: Blob | null
  previewImages?: {
    initial?: string
    refined?: string
    post?: string
  }
  renderImages?: {
    top?: string
    perspective?: string
  }
  optimizationGif?: string
  pipelineResult?: PipelineResult | null
  onDownloadUSDZ?: () => Promise<void>
  isDownloadingAssets?: boolean
  downloadProgress?: number
}

const RoomView: React.FC<RoomViewProps> = ({ 
  roomImage, 
  usdzFile, 
  finalUsdzBlob,
  finalGlbBlob,
  previewImages,
  renderImages,
  optimizationGif,
  pipelineResult,
  onDownloadUSDZ,
  isDownloadingAssets,
  downloadProgress
}) => {
  // Track GLB loading status
  const [isGlbLoading, setIsGlbLoading] = useState(false)
  const [isGlbLoaded, setIsGlbLoaded] = useState(false)

  // Reset loading state when GLB blob changes
  useEffect(() => {
    if (finalGlbBlob) {
      console.log('📦 [RoomView] New GLB blob received:', {
        size: (finalGlbBlob.size / 1024 / 1024).toFixed(1) + ' MB',
        type: finalGlbBlob.type || 'unknown'
      })
      console.log('📦 [RoomView] Resetting loading state')
      setIsGlbLoading(true)
      setIsGlbLoaded(false)
    } else {
      console.log('📦 [RoomView] No GLB blob available')
    }
  }, [finalGlbBlob])

  const handleGlbLoadStatusChange = (loading: boolean, loaded: boolean) => {
    console.log('🎯 [RoomView] GLB load status change:', {
      loading,
      loaded,
      timestamp: new Date().toISOString()
    })
    setIsGlbLoading(loading)
    setIsGlbLoaded(loaded)
    
    if (loaded && !loading) {
      console.log('✅ [RoomView] GLB fully loaded and visible - hiding loader overlay')
    }
  }

  return (
    <div className="relative w-full h-full">
      {finalGlbBlob ? (
        <div className="relative w-full h-[450px]">
          {/* Show loader overlay until GLB is fully loaded and visible */}
          {(!isGlbLoaded || isGlbLoading) && (
            <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 rounded-lg z-10">
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500 mx-auto mb-4"></div>
                <div className="text-lg font-medium text-gray-800">Loading 3D Model...</div>
                <div className="text-sm text-gray-600 mt-2">Preparing your design</div>
              </div>
            </div>
          )}
          {/* GLB viewer - always render but overlay hides it until loaded */}
          <SimpleGLBViewer 
            file={finalGlbBlob}
            onLoadComplete={() => handleGlbLoadStatusChange(false, true)}
            onError={() => handleGlbLoadStatusChange(false, false)}
            className="w-full h-full"
            style={{ height: '450px' }}
          />
        </div>
      ) : isDownloadingAssets ? (
        <div className="relative w-full h-[450px] bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center rounded-lg">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500 mx-auto mb-4"></div>
            <div className="text-lg font-medium text-gray-800">Downloading 3D Model...</div>
            <div className="text-sm text-gray-600 mt-2">{downloadProgress}%</div>
          </div>
        </div>
      ) : pipelineResult ? (
        <div className="relative w-full h-[450px] bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center rounded-lg">
          <div className="text-center text-gray-600">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500 mx-auto mb-4"></div>
            <p className="font-medium">Processing 3D Model...</p>
            <p className="text-sm text-gray-400 mt-2">Pipeline completed, preparing model</p>
          </div>
        </div>
      ) : (
        <div className="relative w-full h-[450px] bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center rounded-lg border-2 border-dashed border-blue-200">
          <div className="text-center text-gray-600">
            <div className="text-4xl mb-4">🏠</div>
            <p className="font-medium">Upload USDZ file to see 3D design</p>
            <p className="text-sm text-gray-400 mt-2">Your designed room will appear here</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default RoomView