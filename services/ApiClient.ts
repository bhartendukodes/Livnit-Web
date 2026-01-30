/**
 * API Client Service for Livinit Pipeline Backend
 * Handles all communication with the FastAPI backend
 */

export interface PipelineRequest {
  user_intent: string
  budget: number
  usdz_path: string
  export_glb?: boolean
  run_rag_scope?: boolean
  run_select_assets?: boolean
  run_initial_layout?: boolean
  run_refine_layout?: boolean
  run_layoutvlm?: boolean
  run_render_scene?: boolean
}

export interface UploadResponse {
  status: string
  message: string
  data: {
    usdz_path: string
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

export interface PipelineResult {
  run_dir: string
  selected_uids: string[]
  total_cost: number
  layoutvlm_layout: any
  layout_preview_path?: string
  layout_preview_refine_path?: string
  layout_preview_post_path?: string
  layoutvlm_gif_path?: string
  final_usdz_path?: string
  render_top_view?: string
  render_perspective_view?: string
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

  constructor(baseURL?: string) {
    this.baseURL = (
      baseURL || 
      process.env.NEXT_PUBLIC_API_BASE_URL || 
      'https://pipeline.livinit.ai'
    ).replace(/\/$/, '') // Remove trailing slash
  }

  /**
   * Upload USDZ room file to the backend
   */
  async uploadRoom(file: File): Promise<UploadResponse> {
    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch(`${this.baseURL}/upload/room`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Upload failed' }))
        throw new ApiClientError(
          errorData.detail || `Upload failed with status ${response.status}`,
          response.status
        )
      }

      return await response.json()
    } catch (error) {
      if (error instanceof ApiClientError) {
        throw error
      }
      throw new ApiClientError(
        `Network error during upload: ${error instanceof Error ? error.message : 'Unknown error'}`,
        0,
        'NETWORK_ERROR'
      )
    }
  }

  /**
   * Run pipeline with Server-Sent Events for progress tracking
   * Uses POST request to start pipeline and SSE for progress updates
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

      try {
        console.log('🚀 Starting pipeline via fetch with SSE response')

        // Make POST request to pipeline endpoint
        const response = await fetch(`${this.baseURL}/pipeline`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream',
          },
          body: JSON.stringify(request),
          signal: abortSignal,
        })

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: 'Pipeline failed to start' }))
          throw new ApiClientError(
            errorData.detail || `Pipeline failed with status ${response.status}`,
            response.status
          )
        }

        if (!response.body) {
          throw new ApiClientError('No response body for SSE stream', 0, 'SSE_ERROR')
        }

        // Read SSE stream with proper buffer handling for large JSON responses
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = '' // Buffer for incomplete JSON data

        const readStream = async () => {
          try {
            while (true) {
              const { done, value } = await reader.read()
              
              if (done) break
              
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
                        resolveOnce(data.data as PipelineResult)
                        return
                      } else {
                        resolveOnce(new ApiClientError(
                          data.message || 'Pipeline completed with unknown status',
                          0,
                          'PIPELINE_ERROR'
                        ))
                        return
                      }
                    }

                    // Handle errors
                    if (data.type === 'error') {
                      console.error('❌ Pipeline error event:', data)
                      resolveOnce(new ApiClientError(
                        data.message || 'Pipeline failed',
                        0,
                        'PIPELINE_ERROR'
                      ))
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
              resolveOnce(new ApiClientError('Pipeline aborted', 0, 'ABORTED'))
            } else {
              console.error('Stream reading error:', error)
              onError(new ApiClientError(
                'Stream reading error during pipeline execution',
                0,
                'SSE_ERROR'
              ))
              resolveOnce(new ApiClientError(
                'Stream reading error during pipeline execution',
                0,
                'SSE_ERROR'
              ))
            }
          } finally {
            reader.releaseLock()
          }
        }

        // Start reading the stream
        readStream()

        // Timeout after 10 minutes
        setTimeout(() => {
          if (!resolved) {
            resolveOnce(new ApiClientError(
              'Pipeline timeout after 10 minutes',
              0,
              'TIMEOUT'
            ))
          }
        }, 10 * 60 * 1000)

      } catch (error) {
        if (abortSignal?.aborted) {
          resolveOnce(new ApiClientError('Pipeline aborted', 0, 'ABORTED'))
        } else {
          resolveOnce(new ApiClientError(
            `Failed to start pipeline: ${error instanceof Error ? error.message : 'Unknown error'}`,
            0,
            'SETUP_ERROR'
          ))
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
   * Uses Next.js API route to proxy the request and avoid CORS issues
   */
  async downloadUSDZ(runDir: string): Promise<Blob> {
    try {
      console.log('📥 ApiClient: Starting USDZ download for runDir:', runDir)
      
      // Use Next.js API route to proxy the request (server-side, no CORS)
      const apiUrl = `/api/download/usdz/${runDir}`
      console.log('📥 ApiClient: Fetching from API route:', apiUrl)
      
      const response = await fetch(apiUrl, {
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
   * Download final GLB file (better for web viewing)
   * Uses Next.js API route to proxy the request and avoid CORS issues
   */
  async downloadGLB(runDir: string): Promise<Blob> {
    try {
      console.log('📥 ApiClient: Starting GLB download for runDir:', runDir)
      
      // Use Next.js API route to proxy the request (server-side, no CORS)
      const apiUrl = `/api/download/glb/${runDir}`
      console.log('📥 ApiClient: Fetching GLB from API route:', apiUrl)
      
      const response = await fetch(apiUrl, {
        method: 'GET',
        headers: {
          'Accept': 'model/gltf-binary, application/octet-stream, */*',
        },
      })

      console.log('📊 ApiClient GLB: Response status:', response.status, response.statusText)
      console.log('📊 ApiClient GLB: Response headers:', Object.fromEntries(response.headers.entries()))

      if (!response.ok) {
        console.error('❌ ApiClient GLB: API route responded with error:', response.status)
        const errorData = await response.json().catch(() => ({ detail: 'GLB download failed' }))
        console.error('❌ ApiClient GLB: Error data:', errorData)
        throw new ApiClientError(
          errorData.detail || `GLB download failed with status ${response.status}`,
          response.status
        )
      }

      const blob = await response.blob()
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
   * Uses Next.js API route to proxy the request and avoid CORS issues
   */
  async getPreview(runDir: string, type: 'initial' | 'refine' | 'post' = 'initial'): Promise<Blob> {
    try {
      // Use Next.js API route to proxy the request (server-side, no CORS)
      const response = await fetch(`/api/preview/${runDir}?type=${type}`)

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
   * Uses Next.js API route to proxy the request and avoid CORS issues
   */
  async getRender(runDir: string, view: 'top' | 'perspective'): Promise<Blob> {
    try {
      // Use Next.js API route to proxy the request (server-side, no CORS)
      const response = await fetch(`/api/render/${runDir}/${view}`)

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
   * Uses Next.js API route to proxy the request and avoid CORS issues
   */
  async getOptimizationGif(runDir: string): Promise<Blob> {
    try {
      // Use Next.js API route to proxy the request (server-side, no CORS)
      const response = await fetch(`/api/layoutvlm-gif/${runDir}`)

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

// Singleton instance with hosted backend URL
export const apiClient = new ApiClient('https://pipeline.livinit.ai')