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

    // Fetch from backend API
    const backendUrl = `${API_BASE_URL}/download/glb/${runDir}`
    console.log('📥 API Route: Proxying GLB download from:', backendUrl)
    
    const response = await fetch(backendUrl, {
      method: 'GET',
      headers: {
        'Accept': 'model/gltf-binary, application/octet-stream, */*',
        'User-Agent': 'Livinit-Web/1.0',
      },
    })

    console.log('📊 Backend GLB response status:', response.status, response.statusText)
    console.log('📊 Backend GLB response headers:', Object.fromEntries(response.headers.entries()))

    if (!response.ok) {
      console.error('❌ Backend GLB responded with error:', response.status, response.statusText)
      const errorText = await response.text()
      console.error('❌ Backend GLB error body:', errorText)
      
      let errorData
      try {
        errorData = JSON.parse(errorText)
      } catch {
        errorData = { detail: errorText || `Backend GLB download failed with status ${response.status}` }
      }
      
      return NextResponse.json(
        errorData,
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