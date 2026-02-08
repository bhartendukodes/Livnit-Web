'use client'

import React, { useEffect, useState } from 'react'
import { PipelineResult, RoomOutputAsset, apiClient } from '../services/ApiClient'
import SimpleGLBViewer from './SimpleGLBViewer'

/** Thumbnail that loads GLB from model_url when available, else shows image or placeholder */
function ProductGLBThumb({
  modelUrl,
  imageUrl,
  name,
  category,
}: {
  modelUrl?: string | null
  imageUrl?: string | null
  name: string
  category?: string | null
}) {
  const [glbBlob, setGlbBlob] = useState<Blob | null>(null)
  const [loadError, setLoadError] = useState(false)

  useEffect(() => {
    if (!modelUrl) return
    setLoadError(false)
    setGlbBlob(null)
    let cancelled = false
    fetch(modelUrl)
      .then((r) => (r.ok ? r.blob() : Promise.reject(new Error('Failed to load model'))))
      .then((blob) => {
        if (!cancelled) setGlbBlob(blob)
      })
      .catch(() => { if (!cancelled) setLoadError(true) })
    return () => { cancelled = true }
  }, [modelUrl])

  const showGlb = glbBlob && !loadError
  return (
    <div className="relative w-full aspect-square bg-gray-100 overflow-hidden rounded-t-xl">
      {showGlb ? (
        <SimpleGLBViewer
          file={glbBlob}
          className="w-full h-full absolute inset-0"
          style={{ minHeight: '100%' }}
        />
      ) : imageUrl && !showGlb ? (
        <img src={imageUrl} alt={name} className="w-full h-full object-cover" width={200} height={200} decoding="async" />
      ) : (
        <div className="w-full h-full flex items-center justify-center text-4xl text-gray-400">🪑</div>
      )}
      {category && (
        <span className="absolute top-2 left-2 px-2 py-0.5 rounded-md text-xs font-medium" style={{ backgroundColor: 'rgb(var(--primary-500))', color: 'white' }}>
          {category}
        </span>
      )}
    </div>
  )
}

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
      {finalGlbBlob ? (
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
                <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><circle cx="5" cy="6" r="1.5" fill="currentColor"/><path d="M10 6h8M10 12h8M10 18h8"/><circle cx="5" cy="12" r="1.5" fill="currentColor"/><circle cx="5" cy="18" r="1.5" fill="currentColor"/></svg>
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

      {/* Shopping list - centered dialog with products + 3D model */}
      {shoppingListOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ minHeight: '100dvh' }}
          role="dialog"
          aria-modal="true"
          aria-labelledby="shopping-list-title"
        >
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setShoppingListOpen(false)} aria-hidden="true" />
          <div
            className="relative z-10 w-full max-w-6xl max-h-[90vh] flex flex-col bg-white rounded-2xl shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-6 py-4 shrink-0"
              style={{
                background: 'linear-gradient(135deg, rgb(var(--primary-50)) 0%, rgb(var(--primary-100)) 100%)',
                borderBottom: '1px solid rgb(var(--primary-200))',
              }}
            >
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ backgroundColor: 'rgb(var(--primary-500))', color: 'white' }}>
                  <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="5" cy="6" r="1.5" fill="currentColor"/><path d="M10 6h8M10 12h8M10 18h8"/><circle cx="5" cy="12" r="1.5" fill="currentColor"/><circle cx="5" cy="18" r="1.5" fill="currentColor"/></svg>
                </div>
                <div>
                  <h2 id="shopping-list-title" className="text-xl font-bold" style={{ color: 'rgb(var(--text-primary))' }}>
                    Shopping list
                  </h2>
                  <p className="text-sm mt-0.5" style={{ color: 'rgb(var(--text-secondary))' }}>
                    {!shoppingListLoading && !shoppingListError && shoppingListAssets.length > 0
                      ? `${shoppingListAssets.length} product${shoppingListAssets.length === 1 ? '' : 's'} in your design`
                      : 'Products in your room'}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShoppingListOpen(false)}
                className="w-10 h-10 rounded-xl flex items-center justify-center hover:bg-white/80 transition-colors"
                style={{ color: 'rgb(var(--text-secondary))' }}
                aria-label="Close"
              >
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M18 6L6 18M6 6l12 12" /></svg>
              </button>
            </div>

            {/* Content: only products list (vertical) */}
            <div className="flex-1 min-h-0 overflow-hidden flex flex-col" style={{ backgroundColor: 'rgb(var(--surface-soft))' }}>
              {shoppingListLoading && (
                <div className="flex flex-col items-center justify-center py-20">
                  <div className="animate-spin rounded-full h-12 w-12 border-2 border-t-transparent mb-4" style={{ borderColor: 'rgb(var(--primary-300))', borderTopColor: 'rgb(var(--primary-500))' }} />
                  <p className="font-medium" style={{ color: 'rgb(var(--text-secondary))' }}>Loading products…</p>
                </div>
              )}
              {shoppingListError && (
                <div className="p-5 rounded-2xl m-4" style={{ backgroundColor: 'rgb(254 242 242)', border: '1px solid rgb(254 202 202)' }}>
                  <p className="text-red-800 font-semibold text-sm mb-1">Couldn’t load shopping list</p>
                  <p className="text-red-700 text-sm">{shoppingListError}</p>
                  <p className="text-red-600/80 text-xs mt-2">Check your connection and try again, or close and reopen the list.</p>
                </div>
              )}
              {!shoppingListLoading && !shoppingListError && shoppingListAssets.length === 0 && (
                <div className="p-12 text-center" style={{ backgroundColor: 'rgb(var(--surface))' }}>
                  <div className="text-5xl mb-4 opacity-60">📦</div>
                  <p className="font-medium" style={{ color: 'rgb(var(--text-secondary))' }}>No products in this room yet</p>
                </div>
              )}
              {!shoppingListLoading && !shoppingListError && shoppingListAssets.length > 0 && (
                <div className="flex-1 overflow-y-auto p-4">
                  <ul className="flex flex-col gap-4">
                    {shoppingListAssets.map((asset, i) => (
                      <li
                        key={asset.name + String(i)}
                        className="rounded-xl overflow-hidden border bg-white shadow-sm hover:shadow-md transition-shadow flex flex-row"
                        style={{ borderColor: 'rgb(var(--surface-muted))' }}
                      >
                        <div className="w-32 sm:w-40 flex-shrink-0 aspect-square bg-gray-100">
                          <ProductGLBThumb
                            modelUrl={asset.model_url}
                            imageUrl={asset.image_url}
                            name={asset.name}
                            category={asset.category}
                          />
                        </div>
                        <div className="flex-1 min-w-0 p-4 flex flex-col justify-center">
                          <h3 className="font-semibold text-base line-clamp-2" style={{ color: 'rgb(var(--text-primary))' }}>{asset.name}</h3>
                          {asset.cost && <p className="mt-1 font-semibold text-sm" style={{ color: 'rgb(var(--primary-600))' }}>{asset.cost}</p>}
                          {asset.product_url && (
                            <a href={asset.product_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold text-white hover:opacity-90 transition-opacity mt-2 w-fit" style={{ backgroundColor: 'rgb(var(--primary-500))' }}>
                              Buy now
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" /><polyline points="15 3 21 3 21 9" /><line x1="10" y1="14" x2="21" y2="3" /></svg>
                            </a>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default RoomView