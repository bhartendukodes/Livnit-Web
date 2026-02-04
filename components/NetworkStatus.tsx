'use client'

import React, { useState, useEffect, useRef } from 'react'

interface NetworkStatusProps {
  show?: boolean
}

/** Quick connectivity check so we don't show "No internet" on false browser offline events */
async function checkActuallyOffline(): Promise<boolean> {
  try {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 3000)
    await fetch(window.location.origin, { method: 'HEAD', cache: 'no-store', signal: controller.signal })
    clearTimeout(timeoutId)
    return false // we have connectivity
  } catch {
    return true // assume offline if fetch failed
  }
}

const NetworkStatus: React.FC<NetworkStatusProps> = ({ show = true }) => {
  const [isOnline, setIsOnline] = useState(true)
  const [showOfflineMessage, setShowOfflineMessage] = useState(false)
  const checkInProgress = useRef(false)

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true)
      setShowOfflineMessage(false)
    }

    const handleOffline = async () => {
      // Browsers often fire false "offline" when backend is slow or a request fails.
      // Only show "No internet" if a real connectivity check fails.
      if (checkInProgress.current) return
      checkInProgress.current = true
      await new Promise(r => setTimeout(r, 800)) // debounce brief glitches
      const actuallyOffline = await checkActuallyOffline()
      checkInProgress.current = false
      if (actuallyOffline) {
        setIsOnline(false)
        setShowOfflineMessage(true)
      }
    }

    const init = async () => {
      if (navigator.onLine) {
        setIsOnline(true)
        return
      }
      const actuallyOffline = await checkActuallyOffline()
      if (actuallyOffline) {
        setIsOnline(false)
        setShowOfflineMessage(true)
      } else {
        setIsOnline(true)
      }
    }

    init()
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  // Hide message after a few seconds when back online
  useEffect(() => {
    if (isOnline && showOfflineMessage) {
      const timer = setTimeout(() => setShowOfflineMessage(false), 3000)
      return () => clearTimeout(timer)
    }
  }, [isOnline, showOfflineMessage])

  if (!show || (!showOfflineMessage && isOnline)) {
    return null
  }

  return (
    <div className="fixed top-4 right-4 z-50">
      {!isOnline ? (
        <div className="bg-red-500 text-white px-4 py-2 rounded-lg shadow-lg flex items-center space-x-2">
          <div className="w-2 h-2 bg-white rounded-full animate-pulse"></div>
          <span className="text-sm font-medium">
            📡 No internet connection
          </span>
        </div>
      ) : showOfflineMessage ? (
        <div className="bg-green-500 text-white px-4 py-2 rounded-lg shadow-lg flex items-center space-x-2">
          <div className="w-2 h-2 bg-white rounded-full"></div>
          <span className="text-sm font-medium">
            ✅ Back online!
          </span>
        </div>
      ) : null}
    </div>
  )
}

export default NetworkStatus