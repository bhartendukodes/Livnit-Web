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

      </nav>
    </AnimatedSection>
  )
}

export default Navigation

