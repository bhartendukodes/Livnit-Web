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
  
  // Chat/iteration state
  currentOutputId: string | null
  canIterate: boolean
  
  // Actions
  uploadAndRunPipeline: (
    file: File, 
    userIntent: string, 
    budget: number, 
    options?: Partial<PipelineRequest>
  ) => Promise<void>
  runPipelineWithDefaultRoom: (
    userIntent: string,
    budget: number,
    usdzPath: string,
    options?: Partial<PipelineRequest>
  ) => Promise<void>
  iterateDesign: (
    userIntent: string,
    budget?: number,
    options?: Partial<PipelineRequest>
  ) => Promise<void>
  downloadFinalUSDZ: () => Promise<void>
  retryPipeline: () => Promise<void>
  abortPipeline: () => void
  clearError: () => void
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
  const [currentOutputId, setCurrentOutputId] = useState<string | null>(null)
  
  // Store current request for retry
  const currentRequestRef = useRef<{
    file?: File
    userIntent: string
    budget: number
    options?: Partial<PipelineRequest>
    defaultUsdzPath?: string
    outputId?: string
  } | null>(null)
  
  const abortControllerRef = useRef<AbortController | null>(null)
  
  // Proactive polling when in render_scene to catch completion even if SSE fails
  const proactivePollingRef = useRef<NodeJS.Timeout | null>(null)

  const clearError = useCallback(() => {
    setError(null)
    setStatus('idle')
  }, [])

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
    setCurrentOutputId(null)
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
        
        // Note: render_scene is where SSE often fails, but we have robust error recovery
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
          setIsDownloadingAssets(true) // Show loading state immediately
          
          // Store output_id for future iterations (chat functionality)
          if (pipelineResult.output_id) {
            console.log('💾 Storing output_id for iterations:', pipelineResult.output_id)
            setCurrentOutputId(pipelineResult.output_id)
          }
          
          // Automatically download the final USDZ and preview images
          const downloadAssets = async () => {
            try {
              console.log('📥 Auto-downloading final USDZ and assets...')
              console.log('🔍 Pipeline result run_dir:', pipelineResult?.run_dir)
              
              if (pipelineResult?.run_dir) {
                setDownloadProgress(10)
                
                // Download GLB for web viewing (GLB is better for web than USDZ)
                // Prefer output_id over run_dir for GLB download (more reliable)
                const downloadIdentifier = pipelineResult.output_id || pipelineResult.run_dir
                console.log('📦 Downloading GLB using:', { 
                  identifier: downloadIdentifier, 
                  type: pipelineResult.output_id ? 'output_id' : 'run_dir' 
                })
                setDownloadProgress(30)
                const glbBlob = await apiClient.downloadGLB(downloadIdentifier)
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
              
              // Debug: check what files are actually available when GLB download fails
              if (pipelineResult?.run_dir) {
                try {
                  const debugIdentifier = pipelineResult.output_id || pipelineResult.run_dir
                  // Use Next.js API route for debug (non-essential, ok to use proxy)
                  const debugResponse = await fetch(`/api/debug/rundir/${debugIdentifier}`)
                  if (debugResponse.ok) {
                    const debugData = await debugResponse.json()
                    console.log('🔍 Debug: Contents after GLB failure for', debugIdentifier, ':', debugData)
                  }
                } catch (debugError) {
                  console.warn('Could not fetch debug info:', debugError)
                }
              }
              
              setIsDownloadingAssets(false)
            }
          }
          
          // Use setTimeout to avoid blocking the event handler
          setTimeout(downloadAssets, 500)
          break
        
      case 'error': {
        const raw = event.message || 'Pipeline failed'
        const isOverloaded = raw.includes('503') || raw.includes('overloaded') || raw.includes('UNAVAILABLE')
        setError(isOverloaded ? "Our AI is busy right now. We'll retry automatically in a few seconds—please wait." : raw)
        setStatus('error')
        break
      }
    }
  }, [])

  const handlePipelineError = useCallback(async (error: ApiClientError) => {
    console.error('❌ Pipeline error:', error)
    
    // If error is network-related and we have progress data, try aggressive recovery
    const hasRunDir = result?.run_dir
    const wasInRenderOrLateStage = progress.currentNode === 'render_scene' || 
                                   progress.currentNode === 'layoutvlm' ||
                                   progress.nodesCompleted.length >= 5 // If we've completed 5+ steps
    
    if ((error.code === 'SSE_ERROR' || error.message.includes('Connection')) && 
        hasRunDir && wasInRenderOrLateStage) {
      console.log('🔄 Network error in late stage, starting aggressive recovery...')
      setError('Connection lost. Checking if pipeline completed...')
      
      // More aggressive polling with shorter intervals
      const pollForCompletion = async (attempt = 1, maxAttempts = 8) => {
        // Start with shorter delays: 2s, 3s, 5s, 8s, 12s, 18s, 25s, 35s
        const delay = attempt === 1 ? 2000 : Math.min(2000 * Math.pow(1.4, attempt - 1), 35000)
        
        console.log(`🔍 Recovery poll ${attempt}/${maxAttempts}: checking in ${Math.round(delay/1000)}s...`)
        await new Promise(resolve => setTimeout(resolve, delay))
        
        try {
          // Use output_id if available for more reliable status check
          const statusIdentifier = currentOutputId || hasRunDir
          const status = await apiClient.checkPipelineStatus(statusIdentifier)
          console.log('📊 Pipeline status:', status)
          
          if (status.completed) {
            console.log('✅ Pipeline completed! Downloading assets...')
            setError('Pipeline completed successfully! Downloading 3D model...')
            
            try {
              // Download GLB first (primary 3D asset)
              // Try with output_id first if available, fall back to run_dir
              const downloadIdentifier = currentOutputId || hasRunDir
              console.log('📦 Recovery: Downloading GLB using:', { 
                identifier: downloadIdentifier, 
                type: currentOutputId ? 'output_id' : 'run_dir' 
              })
              const glbBlob = await apiClient.downloadGLB(downloadIdentifier)
              setFinalGlbBlob(glbBlob)
              
              // Mark as completed immediately so user can see the preview
              setStatus('completed')
              setError(null)
              setProgress(prev => ({
                ...prev,
                currentNode: undefined,
                nodesCompleted: [...new Set([...prev.nodesCompleted, 'render_scene'])]
              }))
              
              // Download other assets in background
              setTimeout(async () => {
                setIsDownloadingAssets(true)
                setDownloadProgress(25)
                
                try {
                  // Download USDZ
                  const usdzBlob = await apiClient.downloadUSDZ(hasRunDir)
                  setFinalUsdzBlob(usdzBlob)
                  setDownloadProgress(50)
                  
                  // Download preview images and renders
                  const [initialPreview, topRender, perspectiveRender] = await Promise.allSettled([
                    apiClient.getPreview(hasRunDir, 'initial'),
                    apiClient.getRender(hasRunDir, 'top'),
                    apiClient.getRender(hasRunDir, 'perspective')
                  ])
                  
                  setDownloadProgress(75)
                  
                  if (initialPreview.status === 'fulfilled') {
                    setPreviewImages(prev => ({ ...prev, initial: URL.createObjectURL(initialPreview.value) }))
                  }
                  if (topRender.status === 'fulfilled') {
                    setRenderImages(prev => ({ ...prev, top: URL.createObjectURL(topRender.value) }))
                  }
                  if (perspectiveRender.status === 'fulfilled') {
                    setRenderImages(prev => ({ ...prev, perspective: URL.createObjectURL(perspectiveRender.value) }))
                  }
                  
                  setDownloadProgress(100)
                  
                } catch (downloadError) {
                  console.warn('⚠️ Could not download some assets:', downloadError)
                } finally {
                  setIsDownloadingAssets(false)
                  setDownloadProgress(0)
                }
              }, 500)
              
              return true // Recovery successful
            } catch (downloadError) {
              console.error('❌ Pipeline completed but could not download GLB:', downloadError)
              
              // Debug: check what files are actually available
              try {
                const debugIdentifier = currentOutputId || hasRunDir
                const debugResponse = await fetch(`/api/debug/rundir/${debugIdentifier}`)
                if (debugResponse.ok) {
                  const debugData = await debugResponse.json()
                  console.log('🔍 Debug: Contents for', debugIdentifier, ':', debugData)
                }
              } catch (debugError) {
                console.warn('Could not fetch debug info:', debugError)
              }
              
              setError('Pipeline completed but failed to download 3D model. This might mean export_glb was not enabled or the GLB file is still being generated. Please try refreshing.')
              setStatus('error')
              return false
            }
          } else if (attempt < maxAttempts) {
            // Continue polling if not completed and attempts left
            setError(`Checking completion... (${attempt}/${maxAttempts}) - ${Math.round((35000 - delay)/1000)}s until next check`)
            return await pollForCompletion(attempt + 1, maxAttempts)
          } else {
            // Max attempts reached
            console.log('❌ Max recovery attempts reached')
            setError('Unable to verify pipeline completion. The process may still be running in the background. Try refreshing in a few minutes.')
            setStatus('error')
            return false
          }
        } catch (statusError) {
          console.error('❌ Status check failed:', statusError)
          if (attempt < maxAttempts) {
            return await pollForCompletion(attempt + 1, maxAttempts)
          } else {
            setError('Could not determine pipeline status. Please retry.')
            setStatus('error')
            return false
          }
        }
      }
      
      // Start polling
      const recovered = await pollForCompletion()
      if (recovered) {
        return // Don't set error state, recovery was successful
      }
    }
    
    // Normal error handling if recovery didn't work
    setError(error.message)
    setStatus('error')
  }, [progress.currentNode, result?.run_dir])

  const uploadAndRunPipeline = useCallback(async (
    file: File,
    userIntent: string,
    budget: number,
    options: Partial<PipelineRequest> = {}
  ) => {
    let attempt = 1
    const maxRetries = 3

    const attemptUploadAndPipeline = async (): Promise<void> => {
      try {
        // Store for retry
        currentRequestRef.current = { file, userIntent, budget, options }
        
        // Reset state
        setStatus('uploading')
        setError(null)
        setResult(null)
        setProgress({ nodesCompleted: [] })

        console.log(`📤 Uploading USDZ file (attempt ${attempt}/${maxRetries}):`, file.name)
        
        // 1. Upload USDZ file
        const uploadResponse = await apiClient.uploadRoom(file)
        console.log('✅ Upload successful:', uploadResponse)

      // 2. Get usdz_path (backend returns room_id and filename)
      const usdzPath = apiClient.getUsdzPathFromUploadResponse(uploadResponse)
      console.log('📍 Using usdz_path for new design:', usdzPath)

      // 3. Prepare pipeline request (new design mode)
      const pipelineRequest: PipelineRequest = {
        user_intent: userIntent,
        budget: budget,
        usdz_path: usdzPath,
        export_glb: true,
        run_rag_scope: false,
        run_select_assets: true,
        run_initial_layout: true,
        run_refine_layout: true,
        run_layoutvlm: true,
        run_render_scene: true,
        upload_to_supabase: true,
        ...options
      }

      console.log('🔄 Starting pipeline with request:', { ...pipelineRequest, usdz_path: usdzPath })
      
      abortControllerRef.current = new AbortController()
      
      // 5. Run pipeline with SSE
      setStatus('running')
      
      await apiClient.runPipeline(
        pipelineRequest,
        handlePipelineEvent,
        handlePipelineError,
        abortControllerRef.current.signal
      )

      } catch (error) {
        console.error(`❌ Pipeline execution failed (attempt ${attempt}):`, error)
        
        // Handle network disconnection with retry
        if (error instanceof ApiClientError && error.code === 'NETWORK_DISCONNECTED' && attempt < maxRetries) {
          console.log(`🔄 Network disconnected, retrying in ${attempt * 2} seconds...`)
          setError(`Network connection lost. Retrying... (${attempt}/${maxRetries})`)
          
          await new Promise(resolve => setTimeout(resolve, attempt * 2000)) // 2s, 4s, 6s delays
          attempt++
          return attemptUploadAndPipeline() // Retry
        }

        // Handle 503 / model overloaded with exponential backoff (5s, 15s, 45s)
        if (error instanceof ApiClientError && (error.code === 'MODEL_OVERLOADED' || error.status === 503) && attempt < maxRetries) {
          const delayMs = 5000 * Math.pow(3, attempt - 1) // 5s, 15s, 45s
          console.log(`🔄 AI busy (503), retrying in ${delayMs / 1000}s (${attempt}/${maxRetries})...`)
          setError(`Our AI is busy right now. Retrying in ${delayMs / 1000} seconds... (${attempt}/${maxRetries})`)
          await new Promise(resolve => setTimeout(resolve, delayMs))
          attempt++
          return attemptUploadAndPipeline() // Retry
        }
        
        if (error instanceof ApiClientError) {
          // Provide more user-friendly messages for network issues
          if (error.code === 'SSE_ERROR' || error.code === 'STREAM_STALLED') {
            setError('Connection interrupted while processing your design. Please check your internet connection and try again.')
          } else if (error.message.includes('chunked') || error.message.includes('incomplete')) {
            setError('Network connection issue detected. Your design may still be processing. Please wait a moment and check your results.')
          } else if (error.message.includes('Connection') || error.message.includes('network')) {
            setError('Network connection lost. Please check your internet connection and try again.')
          } else {
            setError(error.message)
          }
        } else {
          setError(`Unexpected error: ${error instanceof Error ? error.message : 'Unknown error'}`)
        }
        setStatus('error')
      }
    }

    return attemptUploadAndPipeline()
  }, [handlePipelineEvent, handlePipelineError])

  const runPipelineWithDefaultRoom = useCallback(async (
    userIntent: string,
    budget: number,
    usdzPath: string,
    options: Partial<PipelineRequest> = {}
  ) => {
    try {
      currentRequestRef.current = { userIntent, budget, options, defaultUsdzPath: usdzPath }
      setStatus('running')
      setError(null)
      setResult(null)
      setProgress({ nodesCompleted: [] })

      const pipelineRequest: PipelineRequest = {
        user_intent: userIntent,
        budget: budget,
        usdz_path: usdzPath,
        export_glb: true,
        run_rag_scope: false,
        run_select_assets: true,
        run_initial_layout: true,
        run_refine_layout: true,
        run_layoutvlm: true,
        run_render_scene: true,
        upload_to_supabase: true,
        ...options
      }

      console.log('🔄 Starting pipeline with default room:', usdzPath)
      abortControllerRef.current = new AbortController()
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

  const iterateDesign = useCallback(async (
    userIntent: string,
    budget?: number,
    options: Partial<PipelineRequest> = {}
  ) => {
    if (!currentOutputId) {
      throw new ApiClientError('No output_id available for iteration. Run a design first.')
    }

    let attempt = 1
    const maxRetries = 3

    const attemptIteration = async (): Promise<void> => {
      try {
        currentRequestRef.current = { 
          userIntent, 
          budget: budget || currentRequestRef.current?.budget || 5000, 
          options, 
          outputId: currentOutputId 
        }
        setStatus('running')
        setError(null)
        setProgress({ nodesCompleted: [] })

        const pipelineRequest: PipelineRequest = {
          user_intent: userIntent,
          budget: budget || currentRequestRef.current?.budget || 5000,
          output_id: currentOutputId,
          export_glb: true,
          run_rag_scope: false,
          run_select_assets: true,
          run_initial_layout: true,
          run_refine_layout: true,
          run_layoutvlm: true,
          run_render_scene: true,
          upload_to_supabase: true,
          ...options
        }

        console.log('🔄 Starting iteration with output_id:', currentOutputId, `(attempt ${attempt}/${maxRetries})`)
        abortControllerRef.current = new AbortController()
        await apiClient.runPipeline(
          pipelineRequest,
          handlePipelineEvent,
          handlePipelineError,
          abortControllerRef.current.signal
        )
      } catch (error) {
        console.error(`❌ Iteration failed (attempt ${attempt}):`, error)
        
        // Handle 503 / model overloaded with exponential backoff (5s, 15s, 45s)
        if (error instanceof ApiClientError && (error.code === 'MODEL_OVERLOADED' || error.status === 503) && attempt < maxRetries) {
          const delayMs = 5000 * Math.pow(3, attempt - 1) // 5s, 15s, 45s
          console.log(`🔄 AI busy during iteration (503), retrying in ${delayMs / 1000}s (${attempt}/${maxRetries})...`)
          setError(`AI is busy processing your changes. Retrying in ${delayMs / 1000} seconds... (${attempt}/${maxRetries})`)
          await new Promise(resolve => setTimeout(resolve, delayMs))
          attempt++
          return attemptIteration() // Retry
        }
        
        if (error instanceof ApiClientError) {
          setError(error.message)
        } else {
          setError(`Iteration error: ${error instanceof Error ? error.message : 'Unknown error'}`)
        }
        setStatus('error')
      }
    }

    return attemptIteration()
  }, [currentOutputId, handlePipelineEvent, handlePipelineError])

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
    const { file, userIntent, budget, options, defaultUsdzPath, outputId } = currentRequestRef.current
    if (outputId) {
      await iterateDesign(userIntent, budget, options)
    } else if (file) {
      await uploadAndRunPipeline(file, userIntent, budget, options)
    } else if (defaultUsdzPath) {
      await runPipelineWithDefaultRoom(userIntent, budget, defaultUsdzPath, options)
    }
  }, [uploadAndRunPipeline, runPipelineWithDefaultRoom])

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
    runPipelineWithDefaultRoom,
    iterateDesign,
    downloadFinalUSDZ,
    retryPipeline,
    abortPipeline,
    clearError,
    reset,
    currentOutputId,
    canIterate: !!currentOutputId
  }
}