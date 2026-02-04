'use client'

import React, { useEffect, useState } from 'react'
import { PipelineResult, RoomOutputAsset, apiClient } from '../services/ApiClient'
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
  status?: 'idle' | 'uploading' | 'running' | 'completed' | 'error' | 'aborted'
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
  downloadProgress,
  status
}) => {
  // Track GLB loading status
  const [isGlbLoading, setIsGlbLoading] = useState(false)
  const [isGlbLoaded, setIsGlbLoaded] = useState(false)
  // Shopping list modal
  const [shoppingListOpen, setShoppingListOpen] = useState(false)
  const [shoppingListLoading, setShoppingListLoading] = useState(false)
  const [shoppingListError, setShoppingListError] = useState<string | null>(null)
  const [shoppingListAssets, setShoppingListAssets] = useState<RoomOutputAsset[]>([])

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

  const outputId = pipelineResult?.output_id

  const openShoppingList = async () => {
    if (!outputId) return
    setShoppingListOpen(true)
    setShoppingListLoading(true)
    setShoppingListError(null)
    setShoppingListAssets([])
    try {
      const res = await apiClient.getRoomOutputWithAssets(outputId, { timeout: 120, poll_interval: 5 })
      setShoppingListAssets(res.assets || [])
    } catch (e) {
      setShoppingListError(e instanceof Error ? e.message : 'Failed to load shopping list')
    } finally {
      setShoppingListLoading(false)
    }
  }

  return (
    <div className="relative w-full h-full min-h-0 flex flex-col">
      {/* When shopping list is open, hide 3D model section and show placeholder */}
      {shoppingListOpen ? (
        <div className="relative w-full flex-1 min-h-[80vh] rounded-lg flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100/80">
          <p className="text-sm text-gray-500">Close shopping list to view 3D model</p>
        </div>
      ) : finalGlbBlob ? (
        <div className="relative w-full flex-1 min-h-[80vh] rounded-lg overflow-hidden bg-gradient-to-br from-blue-50/50 to-indigo-100/50">
          {/* Shopping list button - show when we have output_id */}
          {outputId && (
            <div className="absolute top-3 right-3 z-20">
              <button
                type="button"
                onClick={openShoppingList}
                className="flex items-center gap-2 px-4 py-2 rounded-xl shadow-md border transition-all hover:scale-105 active:scale-95"
                style={{
                  backgroundColor: 'rgb(var(--primary-500))',
                  color: 'white',
                  borderColor: 'rgb(var(--primary-600))',
                }}
              >
                <span aria-hidden>🛒</span>
                <span className="font-medium">Shopping list</span>
              </button>
            </div>
          )}
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
          {/* GLB viewer - fills space to bottom for full preview */}
          <SimpleGLBViewer 
            file={finalGlbBlob}
            onLoadComplete={() => handleGlbLoadStatusChange(false, true)}
            onError={() => handleGlbLoadStatusChange(false, false)}
            className="w-full h-full absolute inset-0"
            style={{ minHeight: '80vh' }}
          />
        </div>
      ) : isDownloadingAssets ? (
        <div className="relative w-full flex-1 min-h-[80vh] bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center rounded-lg">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500 mx-auto mb-4"></div>
            <div className="text-lg font-medium text-gray-800">Downloading 3D Model...</div>
            <div className="text-sm text-gray-600 mt-2">{downloadProgress}%</div>
          </div>
        </div>
      ) : (pipelineResult || status === 'completed') ? (
        <div className="relative w-full flex-1 min-h-[80vh] bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center rounded-lg">
          <div className="text-center text-gray-600">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500 mx-auto mb-4"></div>
            <p className="font-medium">Processing 3D Model...</p>
            <p className="text-sm text-gray-400 mt-2">Pipeline completed, preparing model</p>
          </div>
        </div>
      ) : (
        <div className="relative w-full flex-1 min-h-[80vh] bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center rounded-lg border-2 border-dashed border-blue-200">
          <div className="text-center text-gray-600">
            <div className="text-4xl mb-4">🏠</div>
            <p className="font-medium">Upload USDZ file to see 3D design</p>
            <p className="text-sm text-gray-400 mt-2">Your designed room will appear here</p>
          </div>
        </div>
      )}

      {/* Shopping list - right-side drawer (does not cover top bar in center) */}
      {shoppingListOpen && (
        <div
          className="fixed inset-0 z-50 flex justify-end"
          style={{ minHeight: '100dvh', contain: 'layout style' }}
          role="dialog"
          aria-modal="true"
          aria-labelledby="shopping-list-title"
        >
          {/* Backdrop - click to close */}
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={() => setShoppingListOpen(false)}
            aria-hidden="true"
          />
          {/* Side panel */}
          <div
            className="relative w-full max-w-md sm:max-w-lg h-full flex flex-col bg-white shadow-2xl border-l"
            style={{
              boxShadow: '-10px 0 40px rgba(0,0,0,0.15)',
              borderColor: 'rgb(var(--surface-muted))',
              transform: 'translateZ(0)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header - fixed height to avoid shift when subtitle text changes */}
            <div
              className="flex items-center justify-between px-5 py-4 shrink-0 min-h-[72px]"
              style={{
                background: 'linear-gradient(135deg, rgb(var(--primary-50)) 0%, rgb(var(--primary-100)) 100%)',
                borderBottom: '1px solid rgb(var(--primary-200))',
              }}
            >
              <div className="flex items-center gap-3 min-w-0">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center text-xl flex-shrink-0"
                  style={{ backgroundColor: 'rgb(var(--primary-500))', color: 'white' }}
                >
                  🛒
                </div>
                <div className="min-w-0">
                  <h2 id="shopping-list-title" className="text-xl font-bold truncate" style={{ color: 'rgb(var(--text-primary))' }}>
                    Shopping list
                  </h2>
                  <p className="text-sm mt-0.5 min-h-[1.25rem]" style={{ color: 'rgb(var(--text-secondary))' }}>
                    {!shoppingListLoading && !shoppingListError && shoppingListAssets.length > 0
                      ? `${shoppingListAssets.length} item${shoppingListAssets.length === 1 ? '' : 's'} in your design`
                      : 'Items in your room'}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShoppingListOpen(false)}
                className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 transition-colors hover:opacity-90 active:opacity-80"
                style={{ backgroundColor: 'rgba(255,255,255,0.8)', color: 'rgb(var(--text-secondary))' }}
                aria-label="Close"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Content - min-height prevents jump when loading finishes */}
            <div
              className="flex-1 overflow-y-auto overflow-x-hidden p-5 min-h-[280px]"
              style={{ backgroundColor: 'rgb(var(--surface-soft))' }}
            >
              {shoppingListLoading && (
                <div className="flex flex-col items-center justify-center py-16">
                  <div
                    className="animate-spin rounded-full h-12 w-12 border-2 border-t-transparent mb-4"
                    style={{ borderColor: 'rgb(var(--primary-300))', borderTopColor: 'rgb(var(--primary-500))' }}
                  />
                  <p className="font-medium" style={{ color: 'rgb(var(--text-secondary))' }}>Loading your items…</p>
                  <p className="text-sm mt-1" style={{ color: 'rgb(var(--text-muted))' }}>Fetching product details</p>
                </div>
              )}
              {shoppingListError && (
                <div className="rounded-2xl p-6 text-center" style={{ backgroundColor: 'rgb(var(--surface))', border: '1px solid rgb(var(--error))' }}>
                  <p className="font-medium text-red-600">{shoppingListError}</p>
                  <p className="text-sm text-gray-500 mt-2">Check your connection and try again.</p>
                </div>
              )}
              {!shoppingListLoading && !shoppingListError && shoppingListAssets.length === 0 && (
                <div className="rounded-2xl p-12 text-center" style={{ backgroundColor: 'rgb(var(--surface))', border: '1px dashed rgb(var(--surface-muted))' }}>
                  <div className="text-5xl mb-4 opacity-60">📦</div>
                  <p className="font-medium" style={{ color: 'rgb(var(--text-secondary))' }}>No items in this room yet</p>
                  <p className="text-sm mt-1" style={{ color: 'rgb(var(--text-muted))' }}>Complete a design to see your shopping list here.</p>
                </div>
              )}
              {!shoppingListLoading && !shoppingListError && shoppingListAssets.length > 0 && (
                <ul className="space-y-4">
                  {shoppingListAssets.map((asset, i) => (
                    <li
                      key={asset.name + String(i)}
                      className="rounded-2xl overflow-hidden border"
                      style={{
                        backgroundColor: 'rgb(var(--surface))',
                        borderColor: 'rgb(var(--surface-muted))',
                        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
                        contain: 'layout',
                      }}
                    >
                      <div className="flex flex-col">
                        {/* Image - fixed size to prevent layout shift when image loads */}
                        <div className="relative w-full h-36 flex-shrink-0 bg-gray-100 overflow-hidden">
                          {asset.image_url ? (
                            <img
                              src={asset.image_url}
                              alt={asset.name}
                              width={144}
                              height={144}
                              decoding="async"
                              className="w-full h-full object-cover"
                              style={{ display: 'block' }}
                            />
                          ) : (
                            <div
                              className="w-full h-full flex items-center justify-center text-4xl"
                              style={{ backgroundColor: 'rgb(var(--surface-muted))', color: 'rgb(var(--text-muted))' }}
                            >
                              🪑
                            </div>
                          )}
                          {asset.category && (
                            <span
                              className="absolute top-2 left-2 px-2 py-0.5 rounded-lg text-xs font-medium"
                              style={{ backgroundColor: 'rgb(var(--primary-500))', color: 'white' }}
                            >
                              {asset.category}
                            </span>
                          )}
                        </div>
                        {/* Body */}
                        <div className="flex-1 p-4 flex flex-col min-w-0">
                          <h3 className="font-semibold text-lg leading-tight line-clamp-2" style={{ color: 'rgb(var(--text-primary))' }}>
                            {asset.name}
                          </h3>
                          {asset.description && (
                            <p className="text-sm mt-2 line-clamp-2" style={{ color: 'rgb(var(--text-secondary))' }}>
                              {asset.description}
                            </p>
                          )}
                          {asset.cost && (
                            <p className="mt-2 font-semibold text-base" style={{ color: 'rgb(var(--primary-600))' }}>
                              {asset.cost}
                            </p>
                          )}
                          <div className="flex flex-wrap gap-2 mt-4">
                            {asset.product_url && (
                              <a
                                href={asset.product_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium transition-opacity hover:opacity-90 active:opacity-80"
                                style={{ backgroundColor: 'rgb(var(--primary-500))', color: 'white' }}
                              >
                                <span>View product</span>
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                                  <polyline points="15 3 21 3 21 9" />
                                  <line x1="10" y1="14" x2="21" y2="3" />
                                </svg>
                              </a>
                            )}
                            {asset.model_url && (
                              <a
                                href={asset.model_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium border transition-opacity hover:opacity-90 active:opacity-80"
                                style={{ borderColor: 'rgb(var(--surface-muted))', color: 'rgb(var(--text-secondary))' }}
                              >
                                <span>3D Model</span>
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                                  <polyline points="15 3 21 3 21 9" />
                                  <line x1="10" y1="14" x2="21" y2="3" />
                                </svg>
                              </a>
                            )}
                          </div>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default RoomView