import { NextRequest, NextResponse } from 'next/server'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'https://pipeline.livinit.ai'

export async function GET(
  request: NextRequest,
  { params }: { params: { runDir: string } }
) {
  try {
    const { runDir } = params
    
    if (!runDir) {
      return NextResponse.json({ error: 'runDir parameter is required' }, { status: 400 })
    }

    // Try to download GLB to check if pipeline completed
    try {
      const glbResponse = await fetch(`${API_BASE_URL}/download/glb/${runDir}`, {
        method: 'GET',
        headers: { 'User-Agent': 'Livinit-Status-Check/1.0' },
      })
      
      const glbAvailable = glbResponse.ok
      const glbSize = glbResponse.ok ? parseInt(glbResponse.headers.get('content-length') || '0') : 0
      
      // Try USDZ as well
      const usdzResponse = await fetch(`${API_BASE_URL}/download/usdz/${runDir}`, {
        method: 'GET',
        headers: { 'User-Agent': 'Livinit-Status-Check/1.0' },
      })
      
      const usdzAvailable = usdzResponse.ok
      const usdzSize = usdzResponse.ok ? parseInt(usdzResponse.headers.get('content-length') || '0') : 0
      
      // Check if preview images are available
      const previewResponse = await fetch(`${API_BASE_URL}/preview/${runDir}`, {
        method: 'HEAD',
        headers: { 'User-Agent': 'Livinit-Status-Check/1.0' },
      })
      
      const previewAvailable = previewResponse.ok
      
      const status = {
        runDir,
        completed: glbAvailable && glbSize > 1000, // GLB with reasonable size indicates completion
        assets: {
          glb: { available: glbAvailable, size: glbSize },
          usdz: { available: usdzAvailable, size: usdzSize },
          preview: { available: previewAvailable }
        },
        timestamp: new Date().toISOString()
      }
      
      return NextResponse.json(status)
      
    } catch (checkError) {
      return NextResponse.json({
        runDir,
        completed: false,
        error: 'Could not check pipeline status',
        timestamp: new Date().toISOString()
      })
    }
    
  } catch (error) {
    console.error('❌ Pipeline status check error:', error)
    return NextResponse.json(
      { error: 'Status check failed' },
      { status: 500 }
    )
  }
}