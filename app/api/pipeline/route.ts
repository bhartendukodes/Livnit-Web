/**
 * Proxy pipeline SSE stream through Next.js with robust error handling and fallback.
 * Direct browser → pipeline.livinit.ai connections often get ERR_INCOMPLETE_CHUNKED_ENCODING
 * during long steps (render_scene ~15+ sec). Server-to-server connection is more stable.
 */
// Vercel Hobby plan max is 300s; request completes when done, no need to wait full duration
export const maxDuration = 300

import { NextRequest, NextResponse } from 'next/server'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'https://pipeline.livinit.ai'

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()

    if (!body || typeof body !== 'object') {
      return NextResponse.json({ detail: 'Request body must be JSON object' }, { status: 400 })
    }

    const backendUrl = `${API_BASE_URL}/pipeline`
    console.log('📡 Pipeline proxy: forwarding to', backendUrl, 'with body:', Object.keys(body))

    const controller = new AbortController()
    const clientAbort = () => {
      console.log('📡 Pipeline proxy: client aborted, cancelling backend request')
      controller.abort()
    }

    // Abort backend fetch when client disconnects
    request.signal.addEventListener('abort', clientAbort, { once: true })

    // Set a longer timeout (6 minutes) for render_scene step which can take 2-3 minutes
    const timeoutId = setTimeout(() => {
      console.log('📡 Pipeline proxy: backend timeout after 6 minutes, aborting')
      controller.abort()
    }, 6 * 60 * 1000)

    try {
      const response = await fetch(backendUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
          'User-Agent': 'Livinit-Web-Proxy/1.0',
        },
        body: JSON.stringify(body),
        signal: controller.signal,
        // Disable keep-alive to prevent connection reuse issues
        keepalive: false
      })

      clearTimeout(timeoutId)

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Pipeline failed to start' }))
        console.error('❌ Pipeline proxy: backend error', response.status, errorData)
        return NextResponse.json(errorData, { status: response.status })
      }

      if (!response.body) {
        return NextResponse.json({ detail: 'No response body from pipeline' }, { status: 502 })
      }

      console.log('✅ Pipeline proxy: got SSE response, streaming to client')

      // Create readable stream that forwards and handles errors gracefully
      const stream = new ReadableStream({
        start(controller) {
          const reader = response.body!.getReader()
          
          const pump = async () => {
            try {
              while (true) {
                const { done, value } = await reader.read()
                
                if (done) {
                  console.log('📡 Pipeline proxy: backend stream ended normally')
                  controller.close()
                  break
                }
                
                controller.enqueue(value)
              }
            } catch (error) {
              console.error('❌ Pipeline proxy: stream error:', error)
              // Send error event to client
              const errorEvent = `data: ${JSON.stringify({
                type: 'error',
                message: 'Stream interrupted - pipeline may still be running. Check results or retry.',
                code: 'PROXY_STREAM_ERROR'
              })}\n\n`
              controller.enqueue(new TextEncoder().encode(errorEvent))
              controller.close()
            }
          }
          
          pump()
        },
        
        cancel() {
          console.log('📡 Pipeline proxy: client cancelled stream')
          response.body?.cancel()
        }
      })

      return new NextResponse(stream, {
        status: 200,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache, no-transform',
          'Connection': 'keep-alive',
          'X-Accel-Buffering': 'no',
        },
      })

    } finally {
      clearTimeout(timeoutId)
      request.signal.removeEventListener('abort', clientAbort)
    }

  } catch (error) {
    console.error('❌ Pipeline proxy error:', error)
    
    if ((error as Error).name === 'AbortError') {
      console.log('📡 Pipeline proxy: aborted')
      return new NextResponse(null, { status: 499 })
    }
    
    const message = error instanceof Error ? error.message : 'Unknown error'
    return NextResponse.json(
      { detail: `Pipeline proxy error: ${message}` },
      { status: 500 }
    )
  }
}
