/**
 * Proxy USDZ room upload to backend. Avoids CORS when browser posts to pipeline.livinit.ai.
 */
import { NextRequest, NextResponse } from 'next/server'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'https://pipeline.livinit.ai'

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData()
    const file = formData.get('file')

    if (!file || !(file instanceof File)) {
      return NextResponse.json(
        { detail: 'Missing or invalid file. Send as form field "file".' },
        { status: 400 }
      )
    }

    if (!file.name.toLowerCase().endsWith('.usdz')) {
      return NextResponse.json(
        { detail: 'File must be a .usdz file' },
        { status: 400 }
      )
    }

    const backendUrl = `${API_BASE_URL}/upload/room`
    const backendFormData = new FormData()
    backendFormData.append('file', file, file.name)

    const response = await fetch(backendUrl, {
      method: 'POST',
      body: backendFormData,
      headers: {
        // Do not set Content-Type; FormData sets it with boundary
      },
    })

    const data = await response.json().catch(() => ({ detail: 'Upload failed' }))

    if (!response.ok) {
      return NextResponse.json(data, { status: response.status })
    }

    return NextResponse.json(data)
  } catch (error) {
    console.error('❌ Upload proxy error:', error)
    const message = error instanceof Error ? error.message : 'Unknown error'
    return NextResponse.json(
      { detail: `Upload proxy error: ${message}` },
      { status: 500 }
    )
  }
}
