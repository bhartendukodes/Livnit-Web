import { NextRequest, NextResponse } from 'next/server'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'https://pipeline.livinit.ai'

export async function GET(
  request: NextRequest,
  { params }: { params: { runDir: string } }
) {
  try {
    const { runDir } = params
    
    if (!runDir) {
      return NextResponse.json({ error: 'identifier parameter is required' }, { status: 400 })
    }

    // Clean identifier - remove quotes if present (handles both output_id and run_dir)
    const cleanIdentifier = runDir.replace(/^["']|["']$/g, '')
    console.log('🔍 Debug: Checking identifier:', cleanIdentifier, '(type:', 
      /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/.test(cleanIdentifier) ? 'output_id' : 'run_dir',
      ')')
    
    // Check various endpoints to see what's available
    const checks = [
      { name: 'GLB', url: `${API_BASE_URL}/download/glb/${cleanIdentifier}`, method: 'HEAD' },
      { name: 'USDZ', url: `${API_BASE_URL}/download/usdz/${cleanIdentifier}`, method: 'HEAD' },
      { name: 'Preview', url: `${API_BASE_URL}/preview/${cleanIdentifier}`, method: 'HEAD' },
      { name: 'Top Render', url: `${API_BASE_URL}/render/${cleanIdentifier}/top`, method: 'HEAD' },
      { name: 'Perspective Render', url: `${API_BASE_URL}/render/${cleanIdentifier}/perspective`, method: 'HEAD' },
    ]
    
    const results = await Promise.allSettled(
      checks.map(async (check) => {
        try {
          const response = await fetch(check.url, { 
            method: 'HEAD',
            headers: { 'User-Agent': 'Livinit-Debug/1.0' },
          })
          return {
            name: check.name,
            url: check.url,
            status: response.status,
            available: response.ok,
            size: response.headers.get('content-length') || 'unknown',
            contentType: response.headers.get('content-type') || 'unknown'
          }
        } catch (error) {
          return {
            name: check.name,
            url: check.url,
            status: 0,
            available: false,
            error: error instanceof Error ? error.message : 'Unknown error'
          }
        }
      })
    )
    
    const fileStatus = results.map(result => 
      result.status === 'fulfilled' ? result.value : { error: 'Failed to check' }
    )
    
    return NextResponse.json({
      identifier: cleanIdentifier,
      originalParam: runDir,
      identifierType: /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/.test(cleanIdentifier) ? 'output_id' : 'run_dir',
      files: fileStatus,
      timestamp: new Date().toISOString()
    })
    
  } catch (error) {
    console.error('❌ Debug endpoint error:', error)
    return NextResponse.json(
      { error: 'Debug check failed' },
      { status: 500 }
    )
  }
}