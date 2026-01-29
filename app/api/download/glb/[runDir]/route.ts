import { NextRequest, NextResponse } from 'next/server'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'https://pipeline.livinit.ai'

export async function GET(
  request: NextRequest,
  { params }: { params: { runDir: string } }
) {
  try {
    const { runDir } = params
    
    if (!runDir) {
      return NextResponse.json(
        { detail: 'runDir parameter is required' },
        { status: 400 }
      )
    }

    // Fetch from backend API
    const backendUrl = `${API_BASE_URL}/download/glb/${runDir}`
    console.log('📥 Proxying GLB download:', backendUrl)
    
    const response = await fetch(backendUrl, {
      method: 'GET',
      headers: {
        'Accept': 'model/gltf-binary, application/octet-stream, */*',
      },
    })

    if (!response.ok) {
      const errorText = await response.text()
      let errorData
      try {
        errorData = JSON.parse(errorText)
      } catch {
        errorData = { detail: errorText || `GLB download failed with status ${response.status}` }
      }
      
      return NextResponse.json(
        errorData,
        { status: response.status }
      )
    }

    // Get the blob from the response
    const blob = await response.blob()
    
    // Return the blob with proper headers
    return new NextResponse(blob, {
      status: 200,
      headers: {
        'Content-Type': response.headers.get('Content-Type') || 'model/gltf-binary',
        'Content-Disposition': response.headers.get('Content-Disposition') || `attachment; filename="room_with_assets.glb"`,
        'Content-Length': blob.size.toString(),
        'Cache-Control': 'public, max-age=3600',
      },
    })
  } catch (error) {
    console.error('❌ Error proxying GLB download:', error)
    return NextResponse.json(
      { 
        detail: `Network error during GLB download: ${error instanceof Error ? error.message : 'Unknown error'}` 
      },
      { status: 500 }
    )
  }
}