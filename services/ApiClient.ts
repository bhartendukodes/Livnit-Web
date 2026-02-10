/**
 * API Client Service for Livinit Pipeline Backend
 * Handles all communication with the FastAPI backend
 */

export interface PipelineRequest {
  user_intent: string
  budget: number
  /** For new design: use room_id or filename from upload/room */
  usdz_path?: string
  /** For iteration: use output_id from previous pipeline result */
  output_id?: string
  export_glb?: boolean
  run_rag_scope?: boolean
  run_select_assets?: boolean
  run_initial_layout?: boolean
  run_refine_layout?: boolean
  run_layoutvlm?: boolean
  run_render_scene?: boolean
  upload_to_supabase?: boolean
}

export interface UploadResponse {
  status: string
  data: {
    room_id: string    // UUID for the room
    filename: string   // timestamped filename
  }
}

export interface PipelineEvent {
  type: 'start' | 'node_start' | 'node_progress' | 'node_complete' | 'heartbeat' | 'complete' | 'error'
  node?: string
  index?: number
  current?: number
  total?: number
  elapsed?: number
  message?: string
  status?: string
  data?: any
  result?: any
  nodes?: string[]
}

/** Room output asset from backend GET /api/v1/products/room-output/{id} */
export interface RoomOutputAsset {
  image_url?: string | null
  name: string
  category?: string | null
  cost?: string | null
  description?: string | null
  product_url?: string | null
  model_url?: string | null
}

export interface RoomOutputWithAssetsResponse {
  assets: RoomOutputAsset[]
  total: number
}

export interface PipelineResult {
  run_dir: string
  output_id: string
  selected_assets: Array<{
    uid: string
    category: string
    price: number
    width: number
    depth: number
    height: number
    materials: string[]
    description: string
    reason?: string
    asset_color?: string
    asset_style?: string
    asset_shape?: string
    image_path?: string
    path?: string
  }>
  selected_uids: string[]
  total_cost: number
  layoutvlm_layout: any
  layout_preview_path?: string
  layout_preview_refine_path?: string
  layout_preview_post_path?: string
  layoutvlm_gif_path?: string
  final_usdz_path?: string
  final_glb_path?: string
  render_top_view?: string
  render_perspective_view?: string
  previous_output_id?: string // For iterations
}

export class ApiClientError extends Error {
  constructor(
    message: string,
    public status?: number,
    public code?: string
  ) {
    super(message)
    this.name = 'ApiClientError'
  }
}

export class ApiClient {
  private baseURL: string
  private useProxy: boolean = false // Direct backend calls like Postman, enable proxy on errors

  constructor(baseURL?: string) {
    this.baseURL = (
      baseURL || 
      process.env.NEXT_PUBLIC_API_BASE_URL || 
      'https://pipeline.livinit.ai'
    ).replace(/\/$/, '') // Remove trailing slash
  }

  /**
   * Enable proxy mode to route requests through Next.js API routes
   * This can help with CORS and network reliability issues
   */
  enableProxy() {
    this.useProxy = true
  }

  /**
   * Get the appropriate URL for API calls based on proxy mode
   */
  private getApiUrl(endpoint: string): string {
    if (this.useProxy) {
      // Use Next.js API routes which proxy to the backend
      return endpoint.startsWith('/') ? `/api${endpoint}` : `/api/${endpoint}`
    }
    return `${this.baseURL}/${endpoint.replace(/^\//, '')}`
  }

  /**
   * Upload USDZ room file to the backend
   */
  async uploadRoom(file: File): Promise<UploadResponse> {
    const formData = new FormData()
    formData.append('file', file)

    console.log('📤 Starting USDZ upload:', {
      filename: file.name,
      size: `${(file.size / 1024 / 1024).toFixed(1)} MB`,
      type: file.type
    })

    try {
      // Try direct backend first (like Postman), fallback to proxy on CORS
      const uploadUrl = `${this.baseURL}/upload/room`
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 5 * 60 * 1000)

      const response = await fetch(uploadUrl, {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      })

      clearTimeout(timeoutId)

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Upload failed' }))
        throw new ApiClientError(
          errorData.detail || `Upload failed with status ${response.status}`,
          response.status
        )
      }

      const json = await response.json()
      console.log('✅ Upload successful:', json)
      return json
      } catch (error) {
        if (error instanceof ApiClientError) {
          throw error
        }
        
        // Handle CORS by retrying with proxy
        if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
          console.log('🔄 Upload CORS detected, retrying with proxy...')
          try {
            const proxyController = new AbortController()
            const proxyTimeoutId = setTimeout(() => proxyController.abort(), 5 * 60 * 1000)
            const proxyResponse = await fetch('/api/upload/room', {
              method: 'POST',
              body: formData,
              signal: proxyController.signal,
            })
            clearTimeout(proxyTimeoutId)
            
            if (!proxyResponse.ok) {
              const errorData = await proxyResponse.json().catch(() => ({ detail: 'Upload failed' }))
              throw new ApiClientError(
                errorData.detail || `Upload failed with status ${proxyResponse.status}`,
                proxyResponse.status
              )
            }
            
            const json = await proxyResponse.json()
            console.log('✅ Upload successful via proxy:', json)
            return json
          } catch (proxyError) {
            throw new ApiClientError(
              'Upload failed even with proxy. Please check your connection and try again.',
              0,
              'NETWORK_DISCONNECTED'
            )
          }
        }
        
        if (error instanceof DOMException && error.name === 'AbortError') {
          throw new ApiClientError(
            'Upload timeout - file is too large or connection too slow. Please try with a smaller file.',
            0,
            'UPLOAD_TIMEOUT'
          )
        }
        
        throw new ApiClientError(
          `Upload failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
          0,
          'UPLOAD_ERROR'
        )
      }
  }

  /**
   * Get usdz_path from upload response - backend returns room_id and filename
   * Per backend analysis: usdz_path can be room_id (UUID) or filename
   */
  getUsdzPathFromUploadResponse(response: UploadResponse): string {
    // Backend returns: { data: { room_id: "uuid", filename: "timestamp_file.usdz" } }
    // usdz_path can be either room_id or filename - prefer room_id for cleaner API
    const roomId = response?.data?.room_id
    const filename = response?.data?.filename
    
    if (roomId && typeof roomId === 'string') {
      return roomId // Use room_id (UUID) as usdz_path
    }
    
    if (filename && typeof filename === 'string') {
      return filename // Fallback to filename
    }
    
    throw new ApiClientError(
      'Upload succeeded but backend did not return room_id or filename. Pipeline requires usdz_path.',
      0,
      'MISSING_ROOM_ID'
    )
  }

  /**
   * Run pipeline with Server-Sent Events for progress tracking
   * Supports both new design (usdz_path) and iteration (output_id) modes
   */
  async runPipeline(
    request: PipelineRequest,
    onEvent: (event: PipelineEvent) => void,
    onError: (error: ApiClientError) => void,
    abortSignal?: AbortSignal
  ): Promise<PipelineResult> {
    return new Promise(async (resolve, reject) => {
      let resolved = false

      const resolveOnce = (result: PipelineResult | ApiClientError) => {
        if (!resolved) {
          resolved = true
          if (result instanceof ApiClientError) {
            reject(result)
          } else {
            resolve(result)
          }
        }
      }

      // Timeout after 8 minutes (shorter than proxy timeout)
      let timeoutId: NodeJS.Timeout | null = null

      try {
        const mode = request.output_id ? 'iteration' : 'new'
        console.log(`🚀 Starting pipeline (${mode}) via fetch with SSE response`)
        console.log('📋 Request:', { ...request, usdz_path: request.usdz_path ? '[hidden]' : undefined })

        // Validate request
        if (!request.output_id && !request.usdz_path) {
          throw new ApiClientError('Pipeline requires either usdz_path (new design) or output_id (iteration)', 400)
        }

        // Use appropriate URL based on proxy mode
        const pipelineUrl = this.getApiUrl('pipeline')
        const requestBody = JSON.stringify(request)
        console.log('🚀 Pipeline request URL:', pipelineUrl)
        console.log('📋 Pipeline request body:', requestBody)
        
        const response = await fetch(pipelineUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'User-Agent': 'Livinit-Web/1.0 (like Postman)',
          },
          body: requestBody,
          signal: abortSignal,
        })

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: 'Pipeline failed to start' }))
          const message =
            (typeof errorData.detail === 'string' && errorData.detail) ||
            (Array.isArray(errorData.detail) && errorData.detail[0]?.msg && String(errorData.detail[0].msg)) ||
            (errorData.message) ||
            `Failed to start pipeline: ${response.status}`
          throw new ApiClientError(message, response.status)
        }

        if (!response.body) {
          throw new ApiClientError('No response body for SSE stream', 0, 'SSE_ERROR')
        }

        // Read SSE stream with robust buffer handling and progressive timeout
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = '' // Buffer for incomplete data
        let lastEventTime = Date.now()
        let consecutiveEmptyReads = 0
        const MAX_EMPTY_READS = 10 // Maximum consecutive empty reads before considering stream stalled

        // Progressive timeout that resets on each event (not just a single 8-min timer)
        const resetProgressiveTimeout = () => {
          if (timeoutId) clearTimeout(timeoutId)
          lastEventTime = Date.now()
          consecutiveEmptyReads = 0 // Reset empty read counter on activity
          timeoutId = setTimeout(() => {
            if (!resolved) {
              const minutesWaiting = Math.round((Date.now() - lastEventTime) / 60000)
              console.log(`⏰ Pipeline timeout after ${minutesWaiting} minutes of inactivity`)
              resolveOnce(new ApiClientError(
                `Pipeline timeout after ${minutesWaiting} minutes of no progress. The process may still be running. Check results or retry.`,
                0,
                'TIMEOUT'
              ))
            }
          }, 5 * 60 * 1000) // 5-minute timeout between events (more aggressive)
        }
        
        resetProgressiveTimeout() // Initial timeout
        
        // Override resolveOnce to clean up timeout
        const originalResolveOnce = resolveOnce
        const resolveOnceWithCleanup = (result: PipelineResult | ApiClientError) => {
          if (timeoutId) clearTimeout(timeoutId)
          originalResolveOnce(result)
        }
        
        // Replace resolveOnce calls in the readStream function
        const readStreamWithCleanup = async () => {
          try {
            while (true) {
              const { done, value } = await reader.read()
              
              if (done) break
              
              // Handle empty reads which might indicate chunking issues
              if (!value || value.length === 0) {
                consecutiveEmptyReads++
                if (consecutiveEmptyReads >= MAX_EMPTY_READS) {
                  console.warn(`⚠️ Stream appears stalled after ${consecutiveEmptyReads} empty reads, triggering recovery`)
                  throw new Error('Stream stalled - chunked encoding incomplete')
                }
                // Small delay before next read to avoid tight loop
                await new Promise(resolve => setTimeout(resolve, 100))
                continue
              }
              
              // Reset empty read counter on successful read
              consecutiveEmptyReads = 0
              
              // Decode chunk and add to buffer
              const chunk = decoder.decode(value, { stream: true })
              buffer += chunk
              
              // Process complete lines from buffer
              const lines = buffer.split('\n')
              
              // Keep the last incomplete line in buffer
              buffer = lines.pop() || ''
              
              for (const line of lines) {
                if (line.startsWith('data: ')) {
                  try {
                    const jsonStr = line.slice(6).trim()
                    
                    // Skip empty data lines
                    if (!jsonStr) continue
                    
                    const data: PipelineEvent = JSON.parse(jsonStr)
                    console.log('📡 Pipeline event:', data.type, data.node || '', data.index || '')
                    onEvent(data)

                    // Handle completion
                    if (data.type === 'complete') {
                      if (data.status === 'success' && data.data) {
                        console.log('✅ Pipeline completed successfully!', data.data)
                        resolveOnceWithCleanup(data.data as PipelineResult)
                        return
                      } else {
                        resolveOnceWithCleanup(new ApiClientError(
                          data.message || 'Pipeline completed with unknown status',
                          0,
                          'PIPELINE_ERROR'
                        ))
                        return
                      }
                    }

                    // Handle errors - be less aggressive than before to match Postman behavior
                    if (data.type === 'error') {
                      console.log('📡 Pipeline SSE error event:', data)
                      const rawMessage = data.message || 'Pipeline failed'
                      const isOverloaded = rawMessage.includes('503') || rawMessage.includes('overloaded') || rawMessage.includes('UNAVAILABLE')
                      
                      // For 503 errors, just log them but continue the stream (like Postman)
                      // The backend may retry internally or the next event might succeed
                      if (isOverloaded) {
                        console.log('⚠️ 503 overload detected in SSE stream, but continuing to listen for recovery...')
                        // Don't throw immediately - let the stream continue in case the backend recovers
                        onEvent({ ...data, type: 'node_progress', current: 0, total: 1 }) // Show as progress event instead
                        return // Skip this error event but keep stream open
                      }
                      
                      // For critical errors, resolve immediately
                      console.error('❌ Critical pipeline error:', rawMessage)
                      resolveOnceWithCleanup(new ApiClientError(rawMessage, 0, 'PIPELINE_ERROR'))
                      return
                    }
                  } catch (parseError) {
                    // Don't log every parse error - large responses get chunked
                    if (line.slice(6).trim().length > 100) {
                      console.warn('⚠️ Large SSE event, possible chunking issue')
                    } else {
                      console.error('Failed to parse SSE event:', parseError, 'Raw line length:', line.length)
                    }
                  }
                }
              }
            }
          } catch (error) {
            if (abortSignal?.aborted) {
              resolveOnceWithCleanup(new ApiClientError('Pipeline aborted', 0, 'ABORTED'))
            } else {
              const isNetworkError =
                error instanceof TypeError && (error.message === 'network error' || error.message.includes('Failed to fetch')) ||
                (error instanceof Error && (
                  error.message.includes('chunked') || 
                  error.message.includes('incomplete') || 
                  error.message.includes('network') ||
                  error.message.includes('stalled') ||
                  error.message.includes('ERR_INCOMPLETE_CHUNKED_ENCODING')
                ))
              
              if (isNetworkError) {
                console.error('🔌 Network error during SSE stream:', error)
                const errorType = error.message.includes('stalled') ? 'STREAM_STALLED' : 'SSE_ERROR'
                // For network errors, immediately trigger fallback
                onError(new ApiClientError(
                  'Connection lost during pipeline execution. Checking if pipeline completed...',
                  0,
                  errorType
                ))
                resolveOnceWithCleanup(new ApiClientError(
                  'Connection lost during pipeline execution. Checking if pipeline completed...',
                  0,
                  errorType
                ))
              } else {
                console.error('Stream reading error:', error)
                onError(new ApiClientError('Stream reading error during pipeline execution', 0, 'SSE_ERROR'))
                resolveOnceWithCleanup(new ApiClientError('Stream reading error during pipeline execution', 0, 'SSE_ERROR'))
              }
            }
          } finally {
            reader.releaseLock()
          }
        }

        // Start reading the stream
        readStreamWithCleanup()

      } catch (error) {
        if (timeoutId) clearTimeout(timeoutId)
        if (abortSignal?.aborted) {
          resolveOnce(new ApiClientError('Pipeline aborted', 0, 'ABORTED'))
        } else {
          // Check if this is a network error and we haven't tried proxy mode yet
          const isNetworkError = error instanceof Error && (
            error.message.includes('Failed to fetch') ||
            error.message.includes('ERR_CONNECTION_REFUSED') ||
            error.message.includes('network error') ||
            error.message.includes('TypeError')
          )
          
          if (isNetworkError && !this.useProxy) {
            console.log('🔄 Direct connection failed, retrying with proxy mode...')
            this.enableProxy()
            try {
              // Retry the entire pipeline call with proxy mode
              return this.runPipeline(request, onEvent, onError, abortSignal)
            } catch (retryError) {
              resolveOnce(new ApiClientError(
                `Failed to start pipeline even with proxy fallback: ${retryError instanceof Error ? retryError.message : 'Unknown error'}`,
                0,
                'SETUP_ERROR'
              ))
            }
          } else {
            resolveOnce(new ApiClientError(
              `Failed to start pipeline: ${error instanceof Error ? error.message : 'Unknown error'}`,
              0,
              'SETUP_ERROR'
            ))
          }
        }
      }
    })
  }

  /**
   * Alternative: Run pipeline via POST request (fallback if SSE doesn't work)
   */
  async runPipelinePost(request: PipelineRequest): Promise<PipelineResult> {
    try {
      const response = await fetch(`${this.baseURL}/pipeline`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Pipeline failed' }))
        throw new ApiClientError(
          errorData.detail || `Pipeline failed with status ${response.status}`,
          response.status
        )
      }

      return await response.json()
    } catch (error) {
      if (error instanceof ApiClientError) {
        throw error
      }
      throw new ApiClientError(
        `Network error during pipeline execution: ${error instanceof Error ? error.message : 'Unknown error'}`,
        0,
        'NETWORK_ERROR'
      )
    }
  }

  /**
   * Download final USDZ file
   */
  async downloadUSDZ(runDir: string): Promise<Blob> {
    try {
      console.log('📥 ApiClient: Starting USDZ download for runDir:', runDir)
      
      // Use hosted backend directly to avoid localhost issues
      const directUrl = `${this.baseURL}/download/usdz/${runDir}`
      console.log('📥 ApiClient: Fetching USDZ directly from backend:', directUrl)
      
      const response = await fetch(directUrl, {
        method: 'GET',
        headers: {
          'Accept': 'model/vnd.usdz+zip, application/octet-stream, */*',
        },
      })

      console.log('📊 ApiClient: Response status:', response.status, response.statusText)
      console.log('📊 ApiClient: Response headers:', Object.fromEntries(response.headers.entries()))
      console.log('📊 ApiClient: Response body readable:', !!response.body)
      console.log('📊 ApiClient: Response content-type:', response.headers.get('content-type'))

      if (!response.ok) {
        console.error('❌ ApiClient: API route responded with error:', response.status)
        const errorData = await response.json().catch(() => ({ detail: 'Download failed' }))
        console.error('❌ ApiClient: Error data:', errorData)
        throw new ApiClientError(
          errorData.detail || `Download failed with status ${response.status}`,
          response.status
        )
      }

      console.log('📦 ApiClient: About to read response as blob...')
      
      // Try to read the response step by step to debug
      let blob: Blob
      try {
        blob = await response.blob()
        console.log('✅ ApiClient: Successfully got blob, size:', blob.size, 'bytes, type:', blob.type)
      } catch (blobError) {
        console.error('❌ ApiClient: Failed to read response as blob:', blobError)
        
        // Try to read as text to see what we actually got
        try {
          const text = await response.text()
          console.log('📄 ApiClient: Response as text (first 500 chars):', text.substring(0, 500))
        } catch (textError) {
          console.error('❌ ApiClient: Also failed to read as text:', textError)
        }
        
        throw new ApiClientError(
          `Failed to read response as blob: ${blobError instanceof Error ? blobError.message : 'Unknown error'}`,
          0,
          'BLOB_READ_ERROR'
        )
      }
      
      // Verify blob has content
      if (blob.size === 0) {
        console.error('❌ ApiClient: Blob is empty')
        throw new ApiClientError(
          'Downloaded file is empty',
          0,
          'EMPTY_FILE'
        )
      }
      
      return blob
    } catch (error) {
      console.error('❌ ApiClient: Download error:', error)
      if (error instanceof ApiClientError) {
        throw error
      }
      throw new ApiClientError(
        `Network error during download: ${error instanceof Error ? error.message : 'Unknown error'}`,
        0,
        'NETWORK_ERROR'
      )
    }
  }

  /**
   * Check pipeline status for a run directory or output_id
   * Returns whether pipeline completed and what assets are available
   */
  async checkPipelineStatus(identifier: string): Promise<{
    completed: boolean
    assets: {
      glb: { available: boolean, size: number }
      usdz: { available: boolean, size: number }
      preview: { available: boolean }
    }
  }> {
    try {
      // Clean identifier - remove quotes if present
      const cleanIdentifier = identifier.replace(/^["']|["']$/g, '')
      
      // Use appropriate URL based on proxy mode or environment
      const statusUrl = this.useProxy || typeof window !== 'undefined' 
        ? `/api/pipeline-status/${cleanIdentifier}`
        : `${this.baseURL}/pipeline-status/${cleanIdentifier}`
      
      const response = await fetch(statusUrl)
      if (!response.ok) {
        throw new Error(`Status check failed: ${response.status}`)
      }
      return await response.json()
    } catch (error) {
      console.error('❌ Pipeline status check failed:', error)
      return {
        completed: false,
        assets: {
          glb: { available: false, size: 0 },
          usdz: { available: false, size: 0 },
          preview: { available: false }
        }
      }
    }
  }

  /**
   * Get room generation with full asset details (shopping list).
   * Uses pipeline output_id. Calls backend GET /api/v1/products/room-output/{id} at BACKEND_API_URL.
   */
  async getRoomOutputWithAssets(
    id: string,
    options?: { timeout?: number; poll_interval?: number }
  ): Promise<RoomOutputWithAssetsResponse> {
    const cleanId = id.replace(/^["']|["']$/g, '')
    const base =
      process.env.NEXT_PUBLIC_BACKEND_API_URL?.replace(/\/$/, '') ||
      ''
    if (!base) {
      throw new ApiClientError(
        'Backend API URL not configured (set NEXT_PUBLIC_BACKEND_API_URL)',
        0,
        'ROOM_OUTPUT_ERROR'
      )
    }
    const params = new URLSearchParams()
    if (options?.timeout != null) params.set('timeout', String(options.timeout))
    if (options?.poll_interval != null) params.set('poll_interval', String(options.poll_interval))
    const qs = params.toString()
    const url = `${base}/api/v1/products/room-output/${cleanId}${qs ? `?${qs}` : ''}`
    const res = await fetch(url)
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new ApiClientError(
        (err as { detail?: string }).detail || `Room output failed: ${res.status}`,
        res.status,
        'ROOM_OUTPUT_ERROR'
      )
    }
    return res.json()
  }

  /**
   * Download final GLB file (better for web viewing)
   * @param identifier - Either run_dir (timestamp) or output_id (UUID)
   */
  async downloadGLB(identifier: string): Promise<Blob> {
    try {
      console.log('📥 ApiClient: Starting GLB download for identifier:', identifier)
      
      // Clean the identifier - remove quotes if present
      const cleanIdentifier = identifier.replace(/^["']|["']$/g, '')
      
      // Always use same-origin proxy in browser to avoid CORS (backend has no Access-Control-Allow-Origin for /download/glb)
      const isBrowser = typeof window !== 'undefined'
      const downloadUrl = isBrowser
        ? `/api/download/glb/${cleanIdentifier}`
        : this.getApiUrl(`download/glb/${cleanIdentifier}`)
      console.log('📥 ApiClient: Fetching GLB from:', downloadUrl)
      
      // Add a small delay to let the backend finish writing the GLB file
      await new Promise(resolve => setTimeout(resolve, 2000))
      
      // Long timeout for large GLB files (5 min) - avoid abort during slow blob read
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 5 * 60 * 1000)
      
      const response = await fetch(downloadUrl, {
        method: 'GET',
        headers: {
          'Accept': 'model/gltf-binary, application/octet-stream, */*',
        },
        signal: controller.signal,
      })

      console.log('📊 ApiClient GLB: Response status:', response.status, response.statusText)
      console.log('📊 ApiClient GLB: Response headers:', Object.fromEntries(response.headers.entries()))

      if (!response.ok) {
        console.error('❌ ApiClient GLB: API route responded with error:', response.status)
        const errorData = await response.json().catch(() => ({ detail: 'GLB download failed' }))
        console.error('❌ ApiClient GLB: Error data:', errorData)
        
        // If 404, the GLB might not be generated yet - provide helpful message
        if (response.status === 404) {
          throw new ApiClientError(
            'GLB file not found. This might happen if export_glb was not enabled in the pipeline request, or the file is still being generated.',
            response.status,
            'GLB_NOT_FOUND'
          )
        }
        
        throw new ApiClientError(
          errorData.detail || `GLB download failed with status ${response.status}`,
          response.status
        )
      }

      // Read body as arrayBuffer then Blob - often more reliable for large streams than .blob()
      const arrayBuffer = await response.arrayBuffer()
      clearTimeout(timeoutId)
      const blob = new Blob([arrayBuffer], { type: response.headers.get('Content-Type') || 'model/gltf-binary' })
      console.log('✅ ApiClient GLB: Successfully got blob, size:', blob.size, 'bytes, type:', blob.type)
      
      // Verify blob has content
      if (blob.size === 0) {
        console.error('❌ ApiClient GLB: Blob is empty')
        throw new ApiClientError(
          'Downloaded GLB file is empty',
          0,
          'EMPTY_FILE'
        )
      }
      
      return blob
    } catch (error) {
      console.error('❌ ApiClient GLB: Download error:', error)
      if (error instanceof ApiClientError) {
        throw error
      }
      throw new ApiClientError(
        `Network error during GLB download: ${error instanceof Error ? error.message : 'Unknown error'}`,
        0,
        'NETWORK_ERROR'
      )
    }
  }

  /**
   * Get layout preview image
   */
  async getPreview(runDir: string, type: 'initial' | 'refine' | 'post' = 'initial'): Promise<Blob> {
    try {
      // Use hosted backend directly
      const response = await fetch(`${this.baseURL}/preview/${runDir}?type=${type}`)

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Preview not found' }))
        throw new ApiClientError(
          errorData.detail || `Preview not found`,
          response.status
        )
      }

      return await response.blob()
    } catch (error) {
      if (error instanceof ApiClientError) {
        throw error
      }
      throw new ApiClientError(
        `Network error during preview fetch: ${error instanceof Error ? error.message : 'Unknown error'}`,
        0,
        'NETWORK_ERROR'
      )
    }
  }

  /**
   * Get rendered view image (top or perspective)
   */
  async getRender(runDir: string, view: 'top' | 'perspective'): Promise<Blob> {
    try {
      // Use hosted backend directly
      const response = await fetch(`${this.baseURL}/render/${runDir}/${view}`)

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Render not found' }))
        throw new ApiClientError(
          errorData.detail || `Render not found`,
          response.status
        )
      }

      return await response.blob()
    } catch (error) {
      if (error instanceof ApiClientError) {
        throw error
      }
      throw new ApiClientError(
        `Network error during render fetch: ${error instanceof Error ? error.message : 'Unknown error'}`,
        0,
        'NETWORK_ERROR'
      )
    }
  }

  /**
   * Get optimization GIF
   */
  async getOptimizationGif(runDir: string): Promise<Blob> {
    try {
      // Use hosted backend directly
      const response = await fetch(`${this.baseURL}/layoutvlm-gif/${runDir}`)

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Optimization GIF not found' }))
        throw new ApiClientError(
          errorData.detail || `Optimization GIF not found`,
          response.status
        )
      }

      return await response.blob()
    } catch (error) {
      if (error instanceof ApiClientError) {
        throw error
      }
      throw new ApiClientError(
        `Network error during GIF fetch: ${error instanceof Error ? error.message : 'Unknown error'}`,
        0,
        'NETWORK_ERROR'
      )
    }
  }

  /**
   * Health check
   */
  async health(): Promise<{ status: string }> {
    try {
      const response = await fetch(`${this.baseURL}/health`)
      return await response.json()
    } catch (error) {
      throw new ApiClientError(
        `Health check failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
        0,
        'NETWORK_ERROR'
      )
    }
  }
}

// Singleton instance - uses environment variable or default
export const apiClient = new ApiClient()