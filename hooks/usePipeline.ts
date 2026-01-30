/**
 * Custom hook for managing the complete pipeline flow
 * Handles upload, pipeline execution, progress tracking, and result processing
 */

import { useState, useCallback, useRef } from 'react'
import { apiClient, ApiClientError, PipelineEvent, PipelineResult, PipelineRequest } from '../services/ApiClient'

export type PipelineStatus = 
  | 'idle' 
  | 'uploading' 
  | 'running' 
  | 'completed' 
  | 'error' 
  | 'aborted'

export interface PipelineProgress {
  currentNode?: string
  currentNodeIndex?: number
  totalNodes?: number
  nodeProgress?: {
    current: number
    total: number
  }
  nodesCompleted: string[]
  elapsedTime?: number
}

export interface UsePipelineReturn {
  // Status
  status: PipelineStatus
  progress: PipelineProgress
  error: string | null
  
  // Results
  result: PipelineResult | null
  finalUsdzBlob: Blob | null
  finalGlbBlob: Blob | null
  previewImages: {
    initial?: string
    refined?: string
    post?: string
  }
  renderImages: {
    top?: string
    perspective?: string
  }
  optimizationGif?: string
  
  // Download status
  isDownloadingAssets: boolean
  downloadProgress: number
  
  // Actions
  uploadAndRunPipeline: (
    file: File, 
    userIntent: string, 
    budget: number, 
    options?: Partial<PipelineRequest>
  ) => Promise<void>
  downloadFinalUSDZ: () => Promise<void>
  retryPipeline: () => Promise<void>
  abortPipeline: () => void
  reset: () => void
}

export function usePipeline(): UsePipelineReturn {
  const [status, setStatus] = useState<PipelineStatus>('idle')
  const [progress, setProgress] = useState<PipelineProgress>({
    nodesCompleted: []
  })
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<PipelineResult | null>(null)
  const [finalUsdzBlob, setFinalUsdzBlob] = useState<Blob | null>(null)
  const [finalGlbBlob, setFinalGlbBlob] = useState<Blob | null>(null)
  const [previewImages, setPreviewImages] = useState<{
    initial?: string
    refined?: string  
    post?: string
  }>({})
  const [renderImages, setRenderImages] = useState<{
    top?: string
    perspective?: string
  }>({})
  const [optimizationGif, setOptimizationGif] = useState<string | undefined>()
  const [isDownloadingAssets, setIsDownloadingAssets] = useState(false)
  const [downloadProgress, setDownloadProgress] = useState(0)
  
  // Store current request for retry
  const currentRequestRef = useRef<{
    file: File
    userIntent: string
    budget: number
    options?: Partial<PipelineRequest>
  } | null>(null)
  
  const abortControllerRef = useRef<AbortController | null>(null)

  const reset = useCallback(() => {
    setStatus('idle')
    setProgress({ nodesCompleted: [] })
    setError(null)
    setResult(null)
    setFinalUsdzBlob(null)
    setFinalGlbBlob(null)
    setPreviewImages({})
    setRenderImages({})
    setOptimizationGif(undefined)
    setIsDownloadingAssets(false)
    setDownloadProgress(0)
    currentRequestRef.current = null
    
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
  }, [])

  const handlePipelineEvent = useCallback((event: PipelineEvent) => {
    // Only log important events to reduce noise
    if (['start', 'node_start', 'node_complete', 'complete', 'error'].includes(event.type)) {
      console.log('📡 Pipeline event:', event.type, event.node || '', event.message || '')
    }
    
    switch (event.type) {
      case 'start':
        setProgress(prev => ({
          ...prev,
          totalNodes: event.nodes?.length || 0,
          nodesCompleted: []
        }))
        break
        
      case 'node_start':
        setProgress(prev => ({
          ...prev,
          currentNode: event.node,
          currentNodeIndex: event.index,
          nodeProgress: undefined
        }))
        break
        
      case 'node_progress':
        setProgress(prev => ({
          ...prev,
          nodeProgress: event.current !== undefined && event.total !== undefined 
            ? { current: event.current, total: event.total }
            : undefined
        }))
        break
        
      case 'node_complete':
        setProgress(prev => ({
          ...prev,
          nodesCompleted: event.node 
            ? [...prev.nodesCompleted, event.node]
            : prev.nodesCompleted,
          elapsedTime: event.elapsed
        }))
        break
        
      case 'heartbeat':
        setProgress(prev => ({
          ...prev,
          elapsedTime: event.elapsed
        }))
        break
        
        case 'complete':
          console.log('🎉 Pipeline completed! Setting result and downloading assets...')
          const pipelineResult = event.data as PipelineResult
          setResult(pipelineResult)
          setStatus('completed')
          
          // Automatically download the final USDZ and preview images
          const downloadAssets = async () => {
            try {
              console.log('📥 Auto-downloading final USDZ and assets...')
              console.log('🔍 Pipeline result run_dir:', pipelineResult?.run_dir)
              
              if (pipelineResult?.run_dir) {
                setIsDownloadingAssets(true)
                setDownloadProgress(10)
                
                // Download GLB for web viewing (GLB is better for web than USDZ)
                console.log('📦 Downloading GLB from:', pipelineResult.run_dir)
                setDownloadProgress(30)
                const glbBlob = await apiClient.downloadGLB(pipelineResult.run_dir)
                console.log('✅ GLB downloaded successfully, size:', glbBlob.size, 'bytes')
                setDownloadProgress(60)
                setFinalGlbBlob(glbBlob)
                
                // Download preview images
                try {
                  console.log('🖼️ Downloading initial preview...')
                  const initialPreview = await apiClient.getPreview(pipelineResult.run_dir, 'initial')
                  const initialUrl = URL.createObjectURL(initialPreview)
                  setPreviewImages(prev => ({ ...prev, initial: initialUrl }))
                  console.log('✅ Initial preview downloaded')
                } catch (e) { 
                  console.warn('⚠️ No initial preview available:', e) 
                }

                try {
                  console.log('🖼️ Downloading refined preview...')
                  const refinedPreview = await apiClient.getPreview(pipelineResult.run_dir, 'refine')
                  const refinedUrl = URL.createObjectURL(refinedPreview)
                  setPreviewImages(prev => ({ ...prev, refined: refinedUrl }))
                  console.log('✅ Refined preview downloaded')
                } catch (e) { 
                  console.warn('⚠️ No refined preview available:', e) 
                }

                try {
                  console.log('🖼️ Downloading top render...')
                  const topRender = await apiClient.getRender(pipelineResult.run_dir, 'top')
                  const topUrl = URL.createObjectURL(topRender)
                  setRenderImages(prev => ({ ...prev, top: topUrl }))
                  console.log('✅ Top render downloaded')
                } catch (e) { 
                  console.warn('⚠️ No top render available:', e) 
                }

                try {
                  console.log('🖼️ Downloading perspective render...')
                  const perspectiveRender = await apiClient.getRender(pipelineResult.run_dir, 'perspective')
                  const perspectiveUrl = URL.createObjectURL(perspectiveRender)
                  setRenderImages(prev => ({ ...prev, perspective: perspectiveUrl }))
                  console.log('✅ Perspective render downloaded')
                } catch (e) { 
                  console.warn('⚠️ No perspective render available:', e) 
                }
                
                console.log('✅ All assets downloaded and ready for preview!')
                setDownloadProgress(100)
                
                // Complete download after short delay
                setTimeout(() => {
                  setIsDownloadingAssets(false)
                }, 500)
              } else {
                console.error('❌ No run_dir in pipeline result:', pipelineResult)
                setIsDownloadingAssets(false)
              }
            } catch (error) {
              console.error('❌ Failed to download assets:', error)
              if (error instanceof Error) {
                console.error('❌ Error details:', error.message, error.stack)
              }
              setIsDownloadingAssets(false)
            }
          }
          
          // Use setTimeout to avoid blocking the event handler
          setTimeout(downloadAssets, 500)
          break
        
      case 'error':
        setError(event.message || 'Pipeline failed')
        setStatus('error')
        break
    }
  }, [])

  const handlePipelineError = useCallback((error: ApiClientError) => {
    console.error('❌ Pipeline error:', error)
    setError(error.message)
    setStatus('error')
  }, [])

  const uploadAndRunPipeline = useCallback(async (
    file: File,
    userIntent: string,
    budget: number,
    options: Partial<PipelineRequest> = {}
  ) => {
    try {
      // Store for retry
      currentRequestRef.current = { file, userIntent, budget, options }
      
      // Reset state
      setStatus('uploading')
      setError(null)
      setResult(null)
      setProgress({ nodesCompleted: [] })

      console.log('📤 Uploading USDZ file:', file.name)
      
      // 1. Upload USDZ file
      const uploadResponse = await apiClient.uploadRoom(file)
      console.log('✅ Upload successful:', uploadResponse)

      // 2. Prepare pipeline request
      const pipelineRequest: PipelineRequest = {
        user_intent: userIntent,
        budget: budget,
        usdz_path: uploadResponse.data.usdz_path,
        export_glb: true, // Enable GLB export for better web viewing
        run_rag_scope: false, // Use full catalog by default
        run_select_assets: true,
        run_initial_layout: true,
        run_refine_layout: true,
        run_layoutvlm: true,
        run_render_scene: true,
        ...options
      }

      console.log('🔄 Starting pipeline with request:', pipelineRequest)
      
      // 3. Create abort controller for pipeline
      abortControllerRef.current = new AbortController()
      
      // 4. Run pipeline with SSE
      setStatus('running')
      
      await apiClient.runPipeline(
        pipelineRequest,
        handlePipelineEvent,
        handlePipelineError,
        abortControllerRef.current.signal
      )

    } catch (error) {
      console.error('❌ Pipeline execution failed:', error)
      
      if (error instanceof ApiClientError) {
        setError(error.message)
      } else {
        setError(`Unexpected error: ${error instanceof Error ? error.message : 'Unknown error'}`)
      }
      
      setStatus('error')
    }
  }, [handlePipelineEvent, handlePipelineError])

  const downloadFinalUSDZ = useCallback(async () => {
    if (!result?.run_dir) {
      setError('No pipeline result available for download')
      return
    }

    try {
      console.log('📥 Downloading final USDZ from run:', result.run_dir)
      const blob = await apiClient.downloadUSDZ(result.run_dir)
      setFinalUsdzBlob(blob)
      
      // Also download preview images
      try {
        const initialPreview = await apiClient.getPreview(result.run_dir, 'initial')
        const initialUrl = URL.createObjectURL(initialPreview)
        setPreviewImages(prev => ({ ...prev, initial: initialUrl }))
      } catch (e) {
        console.warn('Failed to download initial preview:', e)
      }

      try {
        const refinedPreview = await apiClient.getPreview(result.run_dir, 'refine')
        const refinedUrl = URL.createObjectURL(refinedPreview)
        setPreviewImages(prev => ({ ...prev, refined: refinedUrl }))
      } catch (e) {
        console.warn('Failed to download refined preview:', e)
      }

      try {
        const topRender = await apiClient.getRender(result.run_dir, 'top')
        const topUrl = URL.createObjectURL(topRender)
        setRenderImages(prev => ({ ...prev, top: topUrl }))
      } catch (e) {
        console.warn('Failed to download top render:', e)
      }

      try {
        const perspectiveRender = await apiClient.getRender(result.run_dir, 'perspective')
        const perspectiveUrl = URL.createObjectURL(perspectiveRender)
        setRenderImages(prev => ({ ...prev, perspective: perspectiveUrl }))
      } catch (e) {
        console.warn('Failed to download perspective render:', e)
      }

      try {
        const gifBlob = await apiClient.getOptimizationGif(result.run_dir)
        const gifUrl = URL.createObjectURL(gifBlob)
        setOptimizationGif(gifUrl)
      } catch (e) {
        console.warn('Failed to download optimization GIF:', e)
      }

      console.log('✅ All assets downloaded successfully')
      
    } catch (error) {
      console.error('❌ Download failed:', error)
      const errorMsg = error instanceof ApiClientError 
        ? error.message 
        : 'Failed to download results'
      setError(errorMsg)
    }
  }, [result])

  const retryPipeline = useCallback(async () => {
    if (!currentRequestRef.current) {
      setError('No previous request to retry')
      return
    }

    const { file, userIntent, budget, options } = currentRequestRef.current
    await uploadAndRunPipeline(file, userIntent, budget, options)
  }, [uploadAndRunPipeline])

  const abortPipeline = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      setStatus('aborted')
    }
  }, [])

  return {
    status,
    progress,
    error,
    result,
    finalUsdzBlob,
    finalGlbBlob,
    previewImages,
    renderImages,
    optimizationGif,
    isDownloadingAssets,
    downloadProgress,
    uploadAndRunPipeline,
    downloadFinalUSDZ,
    retryPipeline,
    abortPipeline,
    reset
  }
}