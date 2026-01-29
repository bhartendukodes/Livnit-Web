import { NextRequest, NextResponse } from 'next/server'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'https://pipeline.livinit.ai'

export async function GET(
  request: NextRequest,
  { params }: { params: { runDir: string } }
) {
  const { runDir } = params
  
  // Test direct backend connectivity
  const backendUrl = `${API_BASE_URL}/download/usdz/${runDir}`
  
  try {
    console.log('🧪 Testing direct backend connectivity to:', backendUrl)
    
    const response = await fetch(backendUrl, {
      method: 'HEAD', // Just check if the file exists
      headers: {
        'Accept': 'model/vnd.usdz+zip, application/octet-stream, */*',
      },
    })
    
    const result = {
      backendUrl,
      status: response.status,
      statusText: response.statusText,
      headers: Object.fromEntries(response.headers.entries()),
      ok: response.ok,
      timestamp: new Date().toISOString(),
    }
    
    console.log('🧪 Backend test result:', result)
    
    return NextResponse.json(result, { 
      status: 200,
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Cache-Control': 'no-cache',
      }
    })
  } catch (error) {
    const errorResult = {
      backendUrl,
      error: error instanceof Error ? error.message : 'Unknown error',
      stack: error instanceof Error ? error.stack : undefined,
      timestamp: new Date().toISOString(),
    }
    
    console.error('🧪 Backend test failed:', errorResult)
    
    return NextResponse.json(errorResult, { 
      status: 500,
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Cache-Control': 'no-cache',
      }
    })
  }
}