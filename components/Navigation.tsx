'use client'

import React, { useState, useEffect } from 'react'
import Image from 'next/image'
import AnimatedSection from './AnimatedSection'

const Navigation: React.FC = () => {
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
      <nav className={`w-full px-4 py-3 flex items-center justify-between transition-all duration-200 ${
        isScrolled 
          ? 'compact-card backdrop-blur-md' 
          : 'bg-transparent'
      }`} style={{ margin: isScrolled ? '8px 16px' : '0', borderRadius: isScrolled ? '12px' : '0' }}>
        {/* Logo */}
        <div className="flex items-center gap-3 group cursor-pointer">
          <div className="relative">
            <div className="w-14 h-14 rounded-lg overflow-hidden group-hover:scale-105 transition-transform duration-200 bg-transparent flex items-center justify-center p-1">
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

        {/* Right side icons and buttons */}
        <div className="flex items-center gap-1">
          {/* User Profile Icon */}
          <button className="icon-button relative">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="8" r="3" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M12 14C8.13 14 5 16.57 5 19.5V21H19V19.5C19 16.57 15.87 14 12 14Z" 
                    stroke="currentColor" strokeWidth="1.5"/>
            </svg>
          </button>

          {/* Shopping Cart Icon */}
          <button className="icon-button relative">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M3 3H5L5.4 5M7 13H17L21 5H5.4M7 13L5.4 5M7 13L4.7 15.3C4.3 15.7 4.6 16.5 5.1 16.5H17" 
                    stroke="currentColor" strokeWidth="1.5"/>
              <circle cx="9" cy="20" r="1" stroke="currentColor" strokeWidth="1.5"/>
              <circle cx="20" cy="20" r="1" stroke="currentColor" strokeWidth="1.5"/>
            </svg>
            <div className="absolute -top-1 -right-1 w-4 h-4 bg-primary-500 text-white text-xs rounded-full flex items-center justify-center font-medium"
                 style={{ backgroundColor: 'rgb(var(--primary-500))', fontSize: '10px' }}>3</div>
          </button>

          {/* Divider */}
          <div className="w-px h-6 bg-surface-muted mx-2" style={{ backgroundColor: 'rgb(var(--surface-muted))' }}></div>

          {/* Explore Button - Hidden on mobile */}
          <button className="secondary-button hidden md:flex items-center gap-1.5 text-sm px-3 py-2">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M12 1V3M12 21V23M4.22 4.22L5.64 5.64M18.36 18.36L19.78 19.78M1 12H3M21 12H23M4.22 19.78L5.64 18.36M18.36 5.64L19.78 4.22" 
                    stroke="currentColor" strokeWidth="1.5"/>
            </svg>
            Explore
          </button>

          {/* Design AI Button */}
          <button className="primary-button flex items-center gap-1.5 text-sm px-4 py-2">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M2 17L12 22L22 17" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M2 12L12 17L22 12" stroke="currentColor" strokeWidth="1.5"/>
            </svg>
            <span className="hidden sm:inline">Design AI</span>
            <span className="sm:hidden">AI</span>
          </button>
        </div>
      </nav>
    </AnimatedSection>
  )
}

export default Navigation

