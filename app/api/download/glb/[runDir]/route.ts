import { NextRequest, NextResponse } from 'next/server'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'https://pipeline.livinit.ai'

export async function GET(
  request: NextRequest,
  { params }: { params: { runDir: string } }
) {
  try {
    const { runDir } = params
    
    if (!runDir) {
      console.error('❌ No runDir provided for GLB download')
      return NextResponse.json(
        { detail: 'runDir parameter is required' },
        { status: 400 }
      )
    }

    // Fetch from backend API (backend may redirect to Supabase or serve local file)
    const backendUrl = `${API_BASE_URL}/download/glb/${runDir}`
    console.log('📥 GLB Route: Fetching from backend:', backendUrl)
    
    const response = await fetch(backendUrl, {
      method: 'GET',
      headers: {
        'Accept': 'model/gltf-binary, application/octet-stream, */*',
        'User-Agent': 'Livinit-Web-GLB/1.0',
      },
      redirect: 'follow', // Follow 307 redirect to Supabase
      timeout: 30000, // 30 second timeout
    })

    console.log('📊 GLB Route: Backend response:', {
      status: response.status,
      statusText: response.statusText,
      headers: Object.fromEntries(response.headers.entries()),
      url: response.url,
      redirected: response.redirected
    })

    if (!response.ok) {
      console.error('❌ GLB Route: Backend error:', response.status, response.statusText)
      const errorText = await response.text()
      console.error('❌ GLB Route: Error body:', errorText.slice(0, 1000))
      
      // Check if this is a 404 - GLB might not be generated yet
      if (response.status === 404) {
        console.log('🔍 GLB Route: 404 - GLB file not found, possibly not generated yet')
        return NextResponse.json(
          { 
            detail: 'GLB file not found - may still be generating or export_glb was not enabled',
            code: 'GLB_NOT_FOUND',
            runDir: runDir 
          },
          { status: 404 }
        )
      }
      
      let errorData: { detail?: string }
      try {
        errorData = errorText ? JSON.parse(errorText) : {}
      } catch {
        errorData = { detail: errorText || `Backend returned ${response.status}` }
      }
      
      return NextResponse.json(
        { 
          detail: errorData.detail || `GLB download failed (${response.status})`,
          runDir: runDir,
          backendStatus: response.status
        },
        { status: response.status }
      )
    }

    // Stream the response body through instead of buffering (avoids memory/timeout for large GLB)
    const contentType = response.headers.get('Content-Type') || 'model/gltf-binary'
    const contentDisposition = response.headers.get('Content-Disposition') || 'attachment; filename="room_with_assets.glb"'
    const contentLength = response.headers.get('Content-Length')

    const headers: Record<string, string> = {
      'Content-Type': contentType,
      'Content-Disposition': contentDisposition,
      'Cache-Control': 'public, max-age=3600',
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET',
      'Access-Control-Allow-Headers': 'Content-Type',
    }
    if (contentLength) headers['Content-Length'] = contentLength

    console.log('✅ API Route: Streaming GLB with headers:', headers)

    return new NextResponse(response.body, {
      status: 200,
      headers,
    })
  } catch (error) {
    console.error('❌ API Route Error proxying GLB download:', error)
    const errorMessage = error instanceof Error ? error.message : 'Unknown error'
    return NextResponse.json(
      { 
        detail: `Network error during GLB download: ${errorMessage}`,
        error: errorMessage,
        timestamp: new Date().toISOString(),
      },
      { status: 500 }
    )
  }
}