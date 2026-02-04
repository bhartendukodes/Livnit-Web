'use client'

import React, { useState, useEffect } from 'react'

interface FilterSectionProps {
  onReset: () => void
  onBudgetChange?: (budget: number) => void
  onDimensionsChange?: (dimensions: string) => void
  onUploadClick?: () => void
  hasUploadedRoom?: boolean
  uploadedFileName?: string
}

const FilterSection: React.FC<FilterSectionProps> = ({
  onReset,
  onBudgetChange,
  onDimensionsChange,
  onUploadClick,
  hasUploadedRoom = false,
  uploadedFileName
}) => {
  const [roomType, setRoomType] = useState('living-room')
  const [dimensions, setDimensions] = useState('12x18')
  const [budget, setBudget] = useState('5000')

  useEffect(() => {
    onDimensionsChange?.(dimensions)
  }, [dimensions, onDimensionsChange])

  const handleBudgetChange = (value: string) => {
    setBudget(value)
    if (onBudgetChange) {
      const numericValue = value === '5000' ? 5000 : 
                          value === 'low' ? 2000 :
                          value === 'medium' ? 5000 :
                          value === 'high' ? 10000 :
                          value === 'premium' ? 20000 : 5000
      onBudgetChange(numericValue)
    }
  }

  const handleReset = () => {
    setRoomType('living-room')
    setDimensions('12x18')
    setBudget('5000')
    if (onBudgetChange) {
      onBudgetChange(5000)
    }
    onReset()
  }

  return (
    <div className="mb-6 space-y-4">
      {/* Top row: 3 items - Room Type, Budget, Size */}
      <div className="card-premium p-5 md:p-6">
        <div className="flex flex-col md:flex-row gap-3 md:gap-4 flex-wrap items-end">
          {/* Room Type */}
          <div className="flex-1 min-w-[140px]">
            <label className="block text-xs font-semibold mb-1.5"
                   style={{ color: 'rgb(var(--text-secondary))' }}>
              Room Type
            </label>
            <div className="relative">
              <select
                value={roomType}
                onChange={(e) => setRoomType(e.target.value)}
                className="modern-select w-full appearance-none pr-8 py-2.5"
              >
                <option value="living-room">🛋️ Living Room</option>
                <option value="bedroom" disabled>🛏️ Bedroom (coming soon)</option>
                <option value="kitchen" disabled>🍳 Kitchen (coming soon)</option>
                <option value="bathroom" disabled>🚿 Bathroom (coming soon)</option>
                <option value="dining-room" disabled>🍽️ Dining Room (coming soon)</option>
                <option value="office" disabled>💼 Office (coming soon)</option>
              </select>
              <div className="absolute right-2 top-1/2 transform -translate-y-1/2 pointer-events-none">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="text-muted">
                  <path d="M6 9L12 15L18 9" stroke="currentColor" strokeWidth="2"/>
                </svg>
              </div>
            </div>
          </div>

          {/* Dimensions */}
          <div className="flex-1 min-w-[140px]">
            <label className="block text-xs font-semibold mb-1.5"
                   style={{ color: 'rgb(var(--text-secondary))' }}>
              Size
            </label>
            <div className="relative">
              <select
                value={dimensions}
                onChange={(e) => setDimensions(e.target.value)}
                className="modern-select w-full appearance-none pr-8 py-2.5"
              >
                <option value="">Select Size</option>
                <option value="small">Small (&lt; 150 sq ft)</option>
                <option value="12x18">Medium (12&apos; x 18&apos;)</option>
                <option value="large">Large (300-500 sq ft)</option>
                <option value="xlarge">XL (500+ sq ft)</option>
              </select>
              <div className="absolute right-2 top-1/2 transform -translate-y-1/2 pointer-events-none">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="text-muted">
                  <path d="M6 9L12 15L18 9" stroke="currentColor" strokeWidth="2"/>
                </svg>
              </div>
            </div>
          </div>

          {/* Budget */}
          <div className="flex-1 min-w-[140px]">
            <label className="block text-xs font-semibold mb-1.5"
                   style={{ color: 'rgb(var(--text-secondary))' }}>
              Budget
            </label>
            <div className="relative">
              <select
                value={budget}
                onChange={(e) => handleBudgetChange(e.target.value)}
                className="modern-select w-full appearance-none pr-8 py-2.5"
              >
                <option value="">Budget</option>
                <option value="low">$500 - $2K</option>
                <option value="medium">$2K - $5K</option>
                <option value="5000">$5,000</option>
                <option value="high">$5K - $10K</option>
                <option value="premium">$10K+</option>
              </select>
              <div className="absolute right-2 top-1/2 transform -translate-y-1/2 pointer-events-none">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="text-muted">
                  <path d="M6 9L12 15L18 9" stroke="currentColor" strokeWidth="2"/>
                </svg>
              </div>
            </div>
          </div>

          {/* Reset Button */}
          <div className="flex items-end">
            <button
              onClick={handleReset}
              className="icon-button p-2.5 flex items-center gap-1.5"
              title="Reset filters"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path d="M3 12A9 9 0 1 1 12 21" stroke="currentColor" strokeWidth="2"/>
                <path d="M8 12L12 8L16 12" stroke="currentColor" strokeWidth="2"/>
              </svg>
              <span className="hidden sm:inline text-xs">Reset</span>
            </button>
          </div>
        </div>
      </div>

      {/* Below: USDZ upload */}
      {onUploadClick && (
        <div className="card-premium p-5 md:p-6">
          <label className="block text-xs font-semibold mb-3" style={{ color: 'rgb(var(--text-secondary))' }}>
            Room model (USDZ)
          </label>
          <button
            type="button"
            onClick={onUploadClick}
            className="w-full flex items-center justify-center gap-2 px-5 py-4 rounded-xl text-sm font-medium border-2 border-dashed transition-opacity hover:opacity-90"
            style={{
              backgroundColor: hasUploadedRoom ? 'rgb(var(--primary-50))' : 'rgb(var(--surface-soft))',
              color: hasUploadedRoom ? 'rgb(var(--primary-700))' : 'rgb(var(--text-secondary))',
              borderColor: hasUploadedRoom ? 'rgb(var(--primary-300))' : 'rgb(var(--surface-muted))'
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            {hasUploadedRoom ? (uploadedFileName ? `Room: ${uploadedFileName}` : 'Change room') : 'Upload room (USDZ) — tap to select file'}
          </button>
        </div>
      )}
    </div>
  )
}

export default FilterSection
