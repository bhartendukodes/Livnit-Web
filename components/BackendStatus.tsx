'use client'

import React, { useState, useEffect } from 'react'
import { apiClient } from '@/services/ApiClient'

const BackendStatus: React.FC = () => {
  const [isConnected, setIsConnected] = useState<boolean | null>(null)
  const [isChecking, setIsChecking] = useState(true)

  useEffect(() => {
    const checkBackend = async () => {
      try {
        await apiClient.health()
        setIsConnected(true)
        console.log('✅ Backend connection successful')
      } catch (error) {
        setIsConnected(false)
        console.warn('⚠️ Backend not available:', error)
      } finally {
        setIsChecking(false)
      }
    }

    checkBackend()
    
    // Check every 30 seconds
    const interval = setInterval(checkBackend, 30000)
    return () => clearInterval(interval)
  }, [])

  if (isChecking) {
    return (
      <div className="fixed top-4 right-4 bg-yellow-100 border border-yellow-300 text-yellow-800 px-3 py-2 rounded-lg text-sm z-50">
        <div className="flex items-center gap-2">
          <div className="animate-spin rounded-full h-3 w-3 border border-yellow-600 border-t-transparent"></div>
          <span>Checking backend...</span>
        </div>
      </div>
    )
  }

  if (isConnected === false) {
    return (
      <div className="fixed top-4 right-4 bg-red-100 border border-red-300 text-red-800 px-4 py-3 rounded-lg shadow-lg z-50 max-w-sm">
        <div className="flex items-start gap-3">
          <svg className="w-5 h-5 text-red-600 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <p className="font-medium">Backend Offline</p>
            <p className="text-sm mt-1">
              Start the backend server with:
              <code className="block mt-1 bg-red-200 px-2 py-1 rounded text-xs">npm run backend</code>
            </p>
          </div>
        </div>
      </div>
    )
  }

  if (isConnected === true) {
    return (
      <div className="fixed top-4 right-4 bg-green-100 border border-green-300 text-green-800 px-3 py-2 rounded-lg text-sm z-50">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-green-600 rounded-full"></div>
          <span>Backend Connected</span>
        </div>
      </div>
    )
  }

  return null
}

export default BackendStatus