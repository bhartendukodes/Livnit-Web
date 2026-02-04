import { NextRequest, NextResponse } from 'next/server'

const BACKEND_API_URL = process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_BACKEND_API_URL || ''

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  if (!BACKEND_API_URL) {
    return NextResponse.json(
      { detail: 'Backend API URL not configured' },
      { status: 503 }
    )
  }

  const { id } = params
  if (!id) {
    return NextResponse.json({ detail: 'id is required' }, { status: 400 })
  }

  const { searchParams } = new URL(request.url)
  const timeout = searchParams.get('timeout') || '120'
  const poll_interval = searchParams.get('poll_interval') || '5'

  const url = new URL(`${BACKEND_API_URL.replace(/\/$/, '')}/api/v1/products/room-output/${id}`)
  url.searchParams.set('timeout', timeout)
  url.searchParams.set('poll_interval', poll_interval)

  try {
    const res = await fetch(url.toString(), {
      method: 'GET',
      headers: { Accept: 'application/json' },
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      return NextResponse.json(data, { status: res.status })
    }
    return NextResponse.json(data)
  } catch (e) {
    console.error('Products room-output proxy error:', e)
    return NextResponse.json(
      { detail: 'Failed to fetch room output' },
      { status: 502 }
    )
  }
}
