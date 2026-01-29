import { NextRequest, NextResponse } from 'next/server'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'https://pipeline.livinit.ai'

export async function GET(
  request: NextRequest,
  { params }: { params: { runDir: string; view: string } }
) {
  try {
    const { runDir, view } = params
    
    if (!runDir || !view) {
      return NextResponse.json(
        { detail: 'runDir and view parameters are required' },
        { status: 400 }
      )
    }

    if (view !== 'top' && view !== 'perspective') {
      return NextResponse.json(
        { detail: 'View must be "top" or "perspective"' },
        { status: 400 }
      )
    }

    // Fetch from backend API
    const backendUrl = `${API_BASE_URL}/render/${runDir}/${view}`
    console.log('📥 Proxying render download:', backendUrl)
    
    const response = await fetch(backendUrl, {
      method: 'GET',
      headers: {
        'Accept': 'image/png, image/jpeg, */*',
      },
    })

    if (!response.ok) {
      const errorText = await response.text()
      let errorData
      try {
        errorData = JSON.parse(errorText)
      } catch {
        errorData = { detail: errorText || `Render not found` }
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
        'Content-Type': response.headers.get('Content-Type') || 'image/png',
        'Cache-Control': 'public, max-age=3600',
      },
    })
  } catch (error) {
    console.error('❌ Error proxying render download:', error)
    return NextResponse.json(
      { 
        detail: `Network error during render fetch: ${error instanceof Error ? error.message : 'Unknown error'}` 
      },
      { status: 500 }
    )
  }
}
