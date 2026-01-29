import { NextRequest, NextResponse } from 'next/server'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'https://pipeline.livinit.ai'

export async function GET(
  request: NextRequest,
  { params }: { params: { runDir: string } }
) {
  try {
    const { runDir } = params
    const searchParams = request.nextUrl.searchParams
    const type = searchParams.get('type') || 'initial'
    
    if (!runDir) {
      return NextResponse.json(
        { detail: 'runDir parameter is required' },
        { status: 400 }
      )
    }

    // Determine endpoint based on type
    const endpoint = type === 'initial' 
      ? `/preview/${runDir}`
      : type === 'refine' 
        ? `/preview-refine/${runDir}`
        : `/preview-post/${runDir}`

    // Fetch from backend API
    const backendUrl = `${API_BASE_URL}${endpoint}`
    console.log('📥 Proxying preview download:', backendUrl)
    
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
        errorData = { detail: errorText || `Preview not found` }
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
    console.error('❌ Error proxying preview download:', error)
    return NextResponse.json(
      { 
        detail: `Network error during preview fetch: ${error instanceof Error ? error.message : 'Unknown error'}` 
      },
      { status: 500 }
    )
  }
}
