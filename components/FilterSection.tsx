'use client'

import React, { useState } from 'react'

interface FilterSectionProps {
  onReset: () => void
  onBudgetChange?: (budget: number) => void
}

const FilterSection: React.FC<FilterSectionProps> = ({ onReset, onBudgetChange }) => {
  const [roomType, setRoomType] = useState('dining-room')
  const [dimensions, setDimensions] = useState('12x18')
  const [budget, setBudget] = useState('5000')

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
    setRoomType('dining-room')
    setDimensions('12x18')
    setBudget('5000')
    if (onBudgetChange) {
      onBudgetChange(5000)
    }
    onReset()
  }

  return (
    <div className="mb-6">
      <div className="compact-card p-4">
        <div className="flex flex-col md:flex-row gap-3 md:gap-4">
          {/* Room Type */}
          <div className="flex-1">
            <label className="block text-xs font-semibold text-primary-700 mb-1.5"
                   style={{ color: 'rgb(var(--primary-700))' }}>
              Room Type
            </label>
            <div className="relative">
              <select
                value={roomType}
                onChange={(e) => setRoomType(e.target.value)}
                className="modern-select w-full appearance-none pr-8 py-2.5"
              >
                <option value="">Select Room</option>
                <option value="living-room">🛋️ Living Room</option>
                <option value="bedroom">🛏️ Bedroom</option>
                <option value="kitchen">🍳 Kitchen</option>
                <option value="bathroom">🚿 Bathroom</option>
                <option value="dining-room">🍽️ Dining Room</option>
                <option value="office">💼 Office</option>
              </select>
              <div className="absolute right-2 top-1/2 transform -translate-y-1/2 pointer-events-none">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="text-muted">
                  <path d="M6 9L12 15L18 9" stroke="currentColor" strokeWidth="2"/>
                </svg>
              </div>
            </div>
          </div>

          {/* Dimensions */}
          <div className="flex-1">
            <label className="block text-xs font-semibold text-primary-700 mb-1.5"
                   style={{ color: 'rgb(var(--primary-700))' }}>
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
          <div className="flex-1">
            <label className="block text-xs font-semibold text-primary-700 mb-1.5"
                   style={{ color: 'rgb(var(--primary-700))' }}>
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
    </div>
  )
}

export default FilterSection
