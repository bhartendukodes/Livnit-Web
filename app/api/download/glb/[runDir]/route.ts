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

    // Get the blob from the response
    const blob = await response.blob()
    console.log('✅ Successfully got GLB blob from backend, size:', blob.size, 'bytes')
    
    // Verify blob has content
    if (blob.size === 0) {
      console.error('❌ GLB Blob is empty')
      return NextResponse.json(
        { detail: 'Downloaded GLB file is empty' },
        { status: 500 }
      )
    }
    
    // Return the blob with proper headers
    const headers = {
      'Content-Type': response.headers.get('Content-Type') || 'model/gltf-binary',
      'Content-Disposition': response.headers.get('Content-Disposition') || `attachment; filename="room_with_assets.glb"`,
      'Content-Length': blob.size.toString(),
      'Cache-Control': 'public, max-age=3600',
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET',
      'Access-Control-Allow-Headers': 'Content-Type',
    }
    
    console.log('✅ API Route: Returning GLB blob with headers:', headers)
    
    return new NextResponse(blob, {
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