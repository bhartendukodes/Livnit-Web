'use client'

import React, { useEffect } from 'react'
import { useModelViewer } from '../hooks/useModelViewer'
import { PipelineResult } from '../services/ApiClient'
import WorkingUSDZViewer from './WorkingUSDZViewer'
import USDZNativeViewer from './USDZNativeViewer'
import USDZViewer from './USDZViewerArchitecture'
import DirectUSDZRenderer from './DirectUSDZRenderer'
import SimpleDirectUSDZ from './SimpleDirectUSDZ'
import USDZProgressViewer from './USDZProgressViewer'
import NormalUSDZViewer from './NormalUSDZViewer'
import ThreeJSUSDZViewer from './ThreeJSUSDZViewer'
import GLBViewer from './GLBViewer'

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
  console.log('🔍 RoomView render - finalUsdzBlob:', !!finalUsdzBlob)
  console.log('🔍 RoomView render - finalGlbBlob:', !!finalGlbBlob)
  console.log('🔍 RoomView render - usdzFile:', !!usdzFile)
  console.log('🔍 RoomView render - pipelineResult:', !!pipelineResult)
  console.log('🔍 RoomView render - isDownloadingAssets:', isDownloadingAssets)
  const {
    viewerRef,
    isViewerReady,
    isModelLoaded,
    loadingState,
    error,
    loadModel,
    metadata
  } = useModelViewer({ autoInit: true })

  // Load model when final USDZ is available
  useEffect(() => {
    if (finalUsdzBlob && isViewerReady) {
      // Create a File object from the blob for the model viewer
      const file = new File([finalUsdzBlob], 'generated_room.usdz', { 
        type: 'model/vnd.usdz+zip' 
      })
      console.log('📦 Loading final USDZ from pipeline')
      loadModel(file)
    }
  }, [finalUsdzBlob, isViewerReady, loadModel])

  // Fallback: Load original USDZ if no final result yet
  useEffect(() => {
    if (usdzFile && isViewerReady && !finalUsdzBlob) {
      console.log('📦 Loading original USDZ file:', usdzFile.name)
      loadModel(usdzFile)
    }
  }, [usdzFile, isViewerReady, loadModel, finalUsdzBlob])

  return (
    <div className="relative w-full h-full bg-gray-50 rounded-lg overflow-hidden">
      {/* Debug Info */}
      {process.env.NODE_ENV === 'development' && (
        <div className="absolute top-2 left-2 bg-black/80 text-white px-2 py-1 rounded text-xs z-50">
          GLB: {finalGlbBlob ? '✅' : '❌'} | USDZ: {finalUsdzBlob ? '✅' : '❌'} | usdzFile: {usdzFile ? '✅' : '❌'}
        </div>
      )}
      
      {/* 3D Model Viewer - Prefer GLB for web, fallback to USDZ */}
      {(usdzFile || finalUsdzBlob || finalGlbBlob) ? (
        <div className="relative w-full h-full min-h-[600px] bg-neutral-900">
          {/* GLB Viewer - Best for web viewing */}
          {finalGlbBlob ? (
            <GLBViewer glbBlob={finalGlbBlob} />
          ) : finalUsdzBlob ? (
            <ThreeJSUSDZViewer usdzBlob={finalUsdzBlob} />
          ) : usdzFile ? (
            <ThreeJSUSDZViewer usdzBlob={usdzFile} />
          ) : (
            <div className="flex items-center justify-center h-full text-gray-500">
              <p>No 3D file available for preview</p>
            </div>
          )}
          
          {/* Fallback: Model viewer container - managed by hook */}
          <div 
            ref={viewerRef} 
            className="absolute inset-0 opacity-0 pointer-events-none -z-10"
          />
          
          {/* Loading States */}
          {loadingState === 'initializing' && (
            <div className="absolute inset-0 flex items-center justify-center bg-neutral-900 z-10">
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-500 mx-auto mb-4"></div>
                <p className="text-white font-medium">Initializing 3D Viewer...</p>
                <p className="text-gray-400 text-sm mt-2">Setting up model-viewer</p>
              </div>
            </div>
          )}

          {/* Loading state - hide quickly for USDZ to let it render */}
          {loadingState === 'loading' && (
            <div 
              className={`absolute inset-0 flex items-center justify-center bg-neutral-900/90 z-10 pointer-events-none ${metadata?.format === 'usdz' ? 'loading-fade-out' : ''}`}
              style={{ 
                backdropFilter: 'blur(2px)',
                transition: 'opacity 0.5s ease-out'
              }}
            >
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-500 mx-auto mb-4"></div>
                <p className="text-white font-medium">Loading 3D Model...</p>
                {metadata && (
                  <>
                    <p className="text-gray-400 text-sm mt-2">{metadata.name}</p>
                    <p className="text-gray-500 text-xs mt-1">{metadata.sizeFormatted} • {metadata.format.toUpperCase()}</p>
                  </>
                )}
              </div>
            </div>
          )}

          {/* Error State - Only show if really failed, not just for USDZ */}
          {loadingState === 'error' && metadata?.format !== 'usdz' && (
            <div className="absolute inset-0 flex items-center justify-center bg-neutral-900 z-20">
              <div className="text-center p-8 max-w-md">
                <div className="mb-6">
                  <svg className="w-16 h-16 mx-auto text-red-500 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.732 15.5c-.77.833.192 2.5 1.732 2.5z" />
                  </svg>
                </div>
                <h3 className="text-xl font-bold text-white mb-2">Unable to Preview</h3>
                {metadata && (
                  <>
                    <p className="text-gray-400 mb-2">{metadata.name}</p>
                    <p className="text-gray-500 text-sm mb-4">{metadata.sizeFormatted}</p>
                  </>
                )}
                {error && (
                  <p className="text-red-400 text-sm mb-6">{error}</p>
                )}
                <p className="text-gray-500 text-xs mb-6">
                  This 3D file format may not be supported in your browser.
                </p>
                {usdzFile && (
                  <a
                    href={URL.createObjectURL(usdzFile)}
                    download={usdzFile.name}
                    className="inline-block px-6 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors"
                  >
                    Download File
                  </a>
                )}
              </div>
            </div>
          )}
          
          {/* USDZ files - let them try to load, don't show error overlay immediately */}
          {loadingState === 'error' && metadata?.format === 'usdz' && (
            <div className="absolute bottom-4 left-4 bg-black/70 text-white px-4 py-2 rounded-lg text-sm z-30">
              <p className="text-yellow-400">⚠️ USDZ preview may not work on all browsers</p>
              <p className="text-xs text-gray-400 mt-1">File is loaded - trying to render...</p>
            </div>
          )}

          {/* Success State - Model should be visible in viewerRef */}
          {loadingState === 'loaded' && isModelLoaded && metadata?.format !== 'usdz' && (
            <div className="absolute bottom-4 right-4 bg-black/70 text-white px-3 py-2 rounded-lg text-sm z-30">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <span>Model Loaded</span>
              </div>
            </div>
          )}

          {/* USDZ Success State - Show different message */}
          {loadingState === 'loaded' && isModelLoaded && metadata?.format === 'usdz' && (
            <div className="absolute bottom-4 right-4 bg-black/70 text-white px-3 py-2 rounded-lg text-sm z-30">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
                <span>USDZ File Ready</span>
              </div>
            </div>
          )}

          {/* Not ready state */}
          {!isViewerReady && loadingState === 'idle' && (
            <div className="absolute inset-0 flex items-center justify-center bg-neutral-900">
              <div className="text-center">
                <div className="animate-pulse w-16 h-16 bg-gray-700 rounded-full mx-auto mb-4"></div>
                <p className="text-gray-400">Preparing 3D viewer...</p>
              </div>
            </div>
          )}
        </div>
      ) : (
        /* Room Rendering Area - Show pipeline results or default room */
        <div className="relative w-full h-full min-h-[600px] bg-gradient-to-br from-amber-50 via-stone-50 to-amber-100">
        
        {/* Show pipeline preview images if available */}
        {(previewImages?.initial || renderImages?.top || renderImages?.perspective) ? (
          <div className="absolute inset-0 p-6">
            {/* Layout Preview */}
            {previewImages?.initial && (
              <div className="absolute top-4 right-4 w-48 h-32 bg-white rounded-lg shadow-lg overflow-hidden">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img 
                  src={previewImages.initial} 
                  alt="Initial Layout"
                  className="w-full h-full object-cover"
                />
                <div className="absolute bottom-0 left-0 right-0 bg-black/70 text-white px-2 py-1 text-xs">
                  Initial Layout
                </div>
              </div>
            )}
            
            {/* Refined Preview */}
            {previewImages?.refined && (
              <div className="absolute top-4 right-52 w-48 h-32 bg-white rounded-lg shadow-lg overflow-hidden">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img 
                  src={previewImages.refined} 
                  alt="Refined Layout"
                  className="w-full h-full object-cover"
                />
                <div className="absolute bottom-0 left-0 right-0 bg-black/70 text-white px-2 py-1 text-xs">
                  Refined Layout
                </div>
              </div>
            )}

            {/* Top View Render */}
            {renderImages?.top && (
              <div className="absolute bottom-4 right-4 w-48 h-32 bg-white rounded-lg shadow-lg overflow-hidden">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img 
                  src={renderImages.top} 
                  alt="Top View"
                  className="w-full h-full object-cover"
                />
                <div className="absolute bottom-0 left-0 right-0 bg-black/70 text-white px-2 py-1 text-xs">
                  Top View
                </div>
              </div>
            )}

            {/* Perspective View Render */}
            {renderImages?.perspective && (
              <div className="absolute bottom-4 right-52 w-48 h-32 bg-white rounded-lg shadow-lg overflow-hidden">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img 
                  src={renderImages.perspective} 
                  alt="Perspective View"
                  className="w-full h-full object-cover"
                />
                <div className="absolute bottom-0 left-0 right-0 bg-black/70 text-white px-2 py-1 text-xs">
                  Perspective View
                </div>
              </div>
            )}

            {/* Pipeline Result Info */}
            {pipelineResult && (
              <div className="absolute top-4 left-4 bg-white/90 backdrop-blur-sm rounded-lg p-4 shadow-lg max-w-xs">
                <h3 className="font-bold text-gray-900 mb-2">Design Results</h3>
                <div className="text-sm space-y-1">
                  <p><span className="text-gray-600">Assets:</span> {pipelineResult.selected_uids.length}</p>
                  <p><span className="text-gray-600">Total Cost:</span> ${pipelineResult.total_cost.toFixed(2)}</p>
                  <p><span className="text-gray-600">Run:</span> {pipelineResult.run_dir}</p>
                </div>
                
                {/* Manual Download Button */}
                {!finalUsdzBlob && onDownloadUSDZ && (
                  <button
                    onClick={onDownloadUSDZ}
                    className="mt-3 w-full px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm rounded-lg font-medium transition-colors"
                  >
                    📥 Load 3D Preview
                  </button>
                )}
                
                {finalUsdzBlob && (
                  <div className="mt-2 text-green-600 text-xs flex items-center gap-1">
                    <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                    3D Model Ready
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          /* Default Room - Simulated Room with Furniture */
          <div className="absolute inset-0 p-6">
            {/* Long Horizontal Window with Black Frame */}
            <div className="absolute top-6 left-6 right-6 h-24 bg-gradient-to-b from-sky-100 to-green-200 rounded border-4 border-black">
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-full h-full bg-gradient-to-b from-green-300/40 to-green-500/40 blur-md"></div>
              </div>
            </div>

            {/* Wall-mounted Planter (Left Wall) */}
            <div className="absolute top-20 left-6 w-14 h-16 bg-gray-800 rounded-t-lg">
              <div className="absolute top-1 left-1 right-1 bottom-1 bg-green-300 rounded-t"></div>
            </div>

            {/* Round Side Table with Vase (Left of Sofa) */}
            <div className="absolute bottom-40 left-8">
              <div className="w-14 h-14 bg-amber-900 rounded-full shadow-lg"></div>
              <div className="absolute -top-10 left-1/2 transform -translate-x-1/2 w-6 h-10 bg-white rounded-full shadow-md">
                <div className="absolute top-1 left-1/2 transform -translate-x-1/2 w-0.5 h-6 bg-amber-200"></div>
              </div>
            </div>

            {/* Low Accent Chair (Left) - Wooden frame, black straps, light gray cushion */}
            <div className="absolute bottom-32 left-20">
              <div className="w-18 h-20 bg-amber-800 rounded-lg shadow-lg">
                <div className="absolute inset-1 bg-gray-100 rounded flex flex-col">
                  <div className="h-2 bg-black mb-1"></div>
                  <div className="h-2 bg-black mb-1"></div>
                  <div className="flex-1 bg-gray-200"></div>
                </div>
              </div>
            </div>

            {/* Large Dark Gray Sofa with Pillows */}
            <div className="absolute bottom-28 left-36 right-40 h-36 bg-gray-700 rounded-lg shadow-xl">
              <div className="absolute inset-1 bg-gray-600 rounded flex gap-1 p-2">
                <div className="flex-1 bg-amber-100 rounded shadow-inner"></div>
                <div className="flex-1 bg-gray-200 rounded shadow-inner"></div>
                <div className="flex-1 bg-amber-50 rounded shadow-inner"></div>
              </div>
            </div>

            {/* Rectangular Wooden Coffee Table */}
            <div className="absolute bottom-40 left-1/2 transform -translate-x-1/2 w-36 h-24 bg-amber-800 rounded-lg shadow-xl">
              <div className="absolute inset-0.5 bg-amber-700 rounded"></div>
            </div>

            {/* Two Square Brown Leather Poufs */}
            <div className="absolute bottom-36 left-1/2 transform -translate-x-20 w-14 h-14 bg-amber-900 rounded-lg shadow-lg"></div>
            <div className="absolute bottom-36 left-1/2 transform translate-x-6 w-14 h-14 bg-amber-900 rounded-lg shadow-lg"></div>

            {/* Tall Arcing Brass Floor Lamp */}
            <div className="absolute bottom-28 right-36">
              <div className="relative">
                <div className="absolute bottom-0 left-1/2 transform -translate-x-1/2 w-1.5 h-32 bg-amber-600"></div>
                <div className="absolute -top-4 left-1/2 transform -translate-x-1/2 w-14 h-14 bg-amber-200 rounded-full border-2 border-amber-600 shadow-lg"></div>
              </div>
            </div>

            {/* Tall Leafy Green Plant (Right) */}
            <div className="absolute bottom-28 right-24 w-10 h-28 bg-gray-900 rounded-lg shadow-lg">
              <div className="absolute top-1 left-1 right-1 bottom-1 bg-green-400 rounded"></div>
            </div>

            {/* Brown Leather Accent Chair (Right) - Black metal frame */}
            <div className="absolute bottom-32 right-8">
              <div className="w-18 h-20 bg-amber-900 rounded-lg shadow-lg">
                <div className="absolute inset-1 bg-gray-200 rounded flex flex-col">
                  <div className="h-1 bg-black mb-0.5"></div>
                  <div className="h-1 bg-black mb-0.5"></div>
                  <div className="flex-1 bg-amber-50"></div>
                </div>
              </div>
            </div>

            {/* Light Colored Textured Rug (Jute/Sisal) */}
            <div className="absolute bottom-20 left-28 right-32 h-28 bg-amber-100 opacity-70 rounded-lg shadow-inner">
              <div className="absolute inset-0 bg-gradient-to-br from-amber-50 to-amber-200 opacity-50"></div>
            </div>
          </div>
        )}
        </div>
      )}

      {/* Shopping List Button */}
      <button className="absolute bottom-4 left-4 px-4 py-2 bg-white border border-gray-300 rounded-lg shadow-md hover:bg-gray-50 transition-colors flex items-center gap-2 text-gray-700 font-medium z-10">
        <span>Shopping List</span>
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M5 15L12 8L19 15"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
    </div>
  )
}

export default RoomView