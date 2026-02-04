'use client'

import React, { useState, useEffect } from 'react'
import Image from 'next/image'
import AnimatedSection from './AnimatedSection'

interface NavigationProps {
  onUploadUSDZClick?: () => void
  hasCustomRoom?: boolean
  customRoomName?: string
}

const Navigation: React.FC<NavigationProps> = ({
  onUploadUSDZClick,
  hasCustomRoom,
  customRoomName
}) => {
  const [isScrolled, setIsScrolled] = useState(false)

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 20)
    }
    
    window.addEventListener('scroll', handleScroll)
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  return (
    <AnimatedSection animation="fade-in" className="sticky top-0 z-50">
      {/* Stable layout: same margin/radius always to prevent UI fluctuation on scroll/tap */}
      <nav
        className={`w-full px-4 py-3 flex items-center justify-between transition-colors duration-200 ${
          isScrolled ? 'compact-card backdrop-blur-md' : 'bg-transparent'
        }`}
        style={{ margin: '8px 16px', borderRadius: '12px' }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 group cursor-pointer">
          <div className="relative">
            <div className="w-14 h-14 rounded-lg overflow-hidden group-hover:opacity-90 transition-opacity duration-200 bg-transparent flex items-center justify-center p-1">
              <Image
                src="/logo.png"
                alt="Livinit Logo"
                width={56}
                height={56}
                className="object-contain w-full h-full"
                priority
              />
            </div>
          </div>
          <div>
            <span className="text-2xl font-bold text-gradient">Livinit</span>
            <div className="text-xs text-muted -mt-0.5" style={{ color: 'rgb(var(--text-muted))' }}>
              AI Design Studio
            </div>
          </div>
        </div>

        {/* Upload USDZ - separate from Generate; user can upload a room or use app dimensions */}
        {onUploadUSDZClick && (
          <div className="flex items-center gap-2">
            {hasCustomRoom && customRoomName && (
              <span className="text-xs truncate max-w-[120px] hidden sm:inline" style={{ color: 'rgb(var(--text-muted))' }} title={customRoomName}>
                {customRoomName}
              </span>
            )}
            <button
              type="button"
              onClick={onUploadUSDZClick}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors duration-200 hover:opacity-90 active:opacity-80"
              style={{
                backgroundColor: hasCustomRoom ? 'rgb(var(--primary-100))' : 'rgb(var(--primary-500))',
                color: hasCustomRoom ? 'rgb(var(--primary-700))' : 'white',
                border: hasCustomRoom ? '1px solid rgb(var(--primary-300))' : 'none'
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
              <span>{hasCustomRoom ? 'Change room (USDZ)' : 'Upload room (USDZ)'}</span>
            </button>
          </div>
        )}
      </nav>
    </AnimatedSection>
  )
}

export default Navigation

