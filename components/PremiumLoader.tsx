'use client'

import React from 'react'

interface PremiumLoaderProps {
  message?: string
  progress?: number
  className?: string
}

const PremiumLoader: React.FC<PremiumLoaderProps> = ({
  message = "Creating your perfect space...",
  progress = 0,
  className = ""
}) => {
  return (
    <div className={`flex flex-col items-center justify-center p-8 ${className}`}>
      {/* Main loader animation */}
      <div className="relative mb-8">
        {/* Outer ring */}
        <div className="w-24 h-24 rounded-full border-4 border-primary-200 animate-spin"
             style={{ borderColor: 'rgb(var(--primary-200))' }}>
          <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-primary-500 animate-spin"
               style={{ borderTopColor: 'rgb(var(--primary-500))' }}></div>
        </div>
        
        {/* Inner decorative elements */}
        <div className="absolute inset-4 flex items-center justify-center">
          <div className="w-8 h-8 bg-primary-500 rounded-full animate-pulse"
               style={{ backgroundColor: 'rgb(var(--primary-500))' }}>
            <div className="w-full h-full rounded-full bg-gradient-to-tr from-primary-400 to-primary-600"
                 style={{ background: `linear-gradient(to top right, rgb(var(--primary-400)), rgb(var(--primary-600)))` }}></div>
          </div>
        </div>
        
        {/* Floating particles */}
        <div className="absolute -top-2 -right-2 w-3 h-3 bg-primary-400 rounded-full animate-float opacity-75"
             style={{ backgroundColor: 'rgb(var(--primary-400))', animationDelay: '0s' }}></div>
        <div className="absolute -bottom-2 -left-2 w-2 h-2 bg-primary-300 rounded-full animate-float opacity-60"
             style={{ backgroundColor: 'rgb(var(--primary-300))', animationDelay: '1s' }}></div>
        <div className="absolute top-1/2 -right-4 w-2 h-2 bg-primary-500 rounded-full animate-float opacity-80"
             style={{ backgroundColor: 'rgb(var(--primary-500))', animationDelay: '2s' }}></div>
      </div>

      {/* Progress bar */}
      {progress > 0 && (
        <div className="w-64 mb-6">
          <div className="flex justify-between text-sm text-muted mb-2" style={{ color: 'rgb(var(--text-muted))' }}>
            <span>Progress</span>
            <span>{Math.round(progress)}%</span>
          </div>
          <div className="h-2 bg-primary-100 rounded-full overflow-hidden"
               style={{ backgroundColor: 'rgb(var(--primary-100))' }}>
            <div 
              className="h-full bg-gradient-to-r from-primary-500 to-primary-600 rounded-full transition-all duration-500 ease-out"
              style={{ 
                width: `${progress}%`,
                background: `linear-gradient(to right, rgb(var(--primary-500)), rgb(var(--primary-600)))`
              }}
            >
              <div className="h-full w-full bg-white opacity-30 animate-shimmer"></div>
            </div>
          </div>
        </div>
      )}

      {/* Loading message */}
      <div className="text-center">
        <h3 className="text-xl font-bold text-primary-900 mb-2" style={{ color: 'rgb(var(--primary-900))' }}>
          {message}
        </h3>
        <div className="flex items-center justify-center gap-1 text-sm text-secondary" 
             style={{ color: 'rgb(var(--text-secondary))' }}>
          <span>AI is working</span>
          <div className="flex gap-1">
            <div className="w-1 h-1 bg-primary-500 rounded-full animate-bounce"
                 style={{ backgroundColor: 'rgb(var(--primary-500))', animationDelay: '0s' }}></div>
            <div className="w-1 h-1 bg-primary-500 rounded-full animate-bounce"
                 style={{ backgroundColor: 'rgb(var(--primary-500))', animationDelay: '0.2s' }}></div>
            <div className="w-1 h-1 bg-primary-500 rounded-full animate-bounce"
                 style={{ backgroundColor: 'rgb(var(--primary-500))', animationDelay: '0.4s' }}></div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default PremiumLoader