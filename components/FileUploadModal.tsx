'use client'

import React, { useRef, useState, useEffect } from 'react'

interface FileUploadModalProps {
  isOpen: boolean
  onClose: () => void
  onUpload: (file: File) => void
}

const FileUploadModal: React.FC<FileUploadModalProps> = ({
  isOpen,
  onClose,
  onUpload,
}) => {
  const [dragActive, setDragActive] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isAnimating, setIsAnimating] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (isOpen) {
      console.log('✅ FileUploadModal is now open')
      setIsAnimating(true)
      // Prevent body scroll when modal is open
      document.body.style.overflow = 'hidden'
    } else {
      console.log('❌ FileUploadModal is closed')
      document.body.style.overflow = 'unset'
      setIsAnimating(false)
    }
    return () => {
      document.body.style.overflow = 'unset'
    }
  }, [isOpen])

  if (!isOpen) {
    return null
  }

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0]
      if (file.name.endsWith('.usdz')) {
        setSelectedFile(file)
      } else {
        alert('Please upload a USDZ file (.usdz)')
      }
    }
  }

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0]
      if (file.name.endsWith('.usdz')) {
        setSelectedFile(file)
      } else {
        alert('Please upload a USDZ file (.usdz)')
      }
    }
  }

  const handleUpload = () => {
    if (selectedFile) {
      onUpload(selectedFile)
      setSelectedFile(null)
      onClose()
    }
  }

  const handleBrowse = () => {
    fileInputRef.current?.click()
  }

  return (
    <div 
      className={`fixed inset-0 z-[9999] transition-all duration-300 ${
        isAnimating ? 'opacity-100' : 'opacity-0'
      }`}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          console.log('Modal backdrop clicked, closing modal')
          onClose()
        }
      }}
    >
      {/* Animated Backdrop */}
      <div className="absolute inset-0 bg-black bg-opacity-60 backdrop-blur-sm"></div>
      
      <div className="relative flex items-center justify-center min-h-screen p-4">
        <div className={`compact-card max-w-md w-full mx-auto transition-all duration-300 shadow-xl border-2 ${
          isAnimating ? 'scale-100 translate-y-0' : 'scale-95 translate-y-4'
        }`}
          style={{ borderColor: 'rgb(var(--primary-200))', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1)' }}>
          
          {/* Compact Header */}
          <div className="flex items-center justify-between p-6 pb-4">
            <div>
              <h3 className="text-xl font-bold text-primary-900" style={{ color: 'rgb(var(--text-primary))' }}>
                Upload Room File
              </h3>
              <p className="text-secondary text-sm" style={{ color: 'rgb(var(--text-secondary))' }}>
                Share your USDZ file to start designing
              </p>
            </div>
            <button
              onClick={onClose}
              className="icon-button p-2"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" strokeWidth="2"/>
              </svg>
            </button>
          </div>

          {/* Upload Area - clear border on white so drop zone is visible */}
          <div className="px-6">
            <div
              className={`relative rounded-xl p-8 text-center transition-all duration-200 ${
                dragActive
                  ? 'border-2 border-solid shadow-lg'
                  : 'border-2 border-dashed shadow-sm'
              }`}
              style={{
                borderColor: dragActive ? 'rgb(var(--primary-500))' : 'rgb(148 163 184)',
                backgroundColor: dragActive ? 'rgb(var(--primary-50))' : 'rgb(248 250 252)',
                boxShadow: dragActive ? '0 0 0 3px rgb(var(--primary-200))' : '0 1px 3px rgba(0,0,0,0.08)'
              }}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".usdz"
                onChange={handleFileInput}
                className="hidden"
              />

              {/* Compact Upload Icon */}
              <div className={`mb-4 transition-transform duration-200 ${dragActive ? 'scale-105' : ''}`}>
                <div className="w-12 h-12 mx-auto bg-primary-100 rounded-xl flex items-center justify-center"
                     style={{ backgroundColor: 'rgb(var(--primary-100))' }}>
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="text-primary-600"
                       style={{ color: 'rgb(var(--primary-600))' }}>
                    <path d="M21 15V19C21 20.1 20.1 21 19 21H5C3.9 21 3 20.1 3 19V15M17 8L12 3M12 3L7 8M12 3V15"
                          stroke="currentColor" strokeWidth="2"/>
                  </svg>
                </div>
              </div>

              {!selectedFile ? (
                <>
                  <h4 className="text-lg font-semibold text-primary-900 mb-2" style={{ color: 'rgb(var(--text-primary))' }}>
                    Drop USDZ file here
                  </h4>
                  <p className="text-secondary text-sm mb-4" style={{ color: 'rgb(var(--text-secondary))' }}>
                    or click to browse
                  </p>
                  <button onClick={handleBrowse} className="primary-button px-6 py-2">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="mr-2">
                      <path d="M14 2H6C4.9 2 4 2.9 4 4V20C4 21.1 4.9 22 6 22H18C19.1 22 20 21.1 20 20V8L14 2Z" 
                            stroke="currentColor" strokeWidth="2"/>
                    </svg>
                    Browse Files
                  </button>
                  <p className="text-xs text-muted mt-3" style={{ color: 'rgb(var(--text-muted))' }}>
                    USDZ format only
                  </p>
                </>
              ) : (
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center flex-shrink-0">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="text-green-600">
                        <path d="M20 6L9 17L4 12" stroke="currentColor" strokeWidth="2"/>
                      </svg>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-green-800 text-sm truncate">{selectedFile.name}</p>
                      <p className="text-green-600 text-xs">
                        {(selectedFile.size / 1024 / 1024).toFixed(1)} MB • Ready to upload
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Floating particles animation */}
              {dragActive && (
                <div className="absolute inset-0 pointer-events-none">
                  <div className="absolute top-4 left-4 w-2 h-2 bg-primary-400 rounded-full opacity-60 animate-float"></div>
                  <div className="absolute top-8 right-6 w-3 h-3 bg-primary-300 rounded-full opacity-40 animate-float" style={{ animationDelay: '0.5s' }}></div>
                  <div className="absolute bottom-6 left-8 w-2 h-2 bg-primary-500 rounded-full opacity-50 animate-float" style={{ animationDelay: '1s' }}></div>
                </div>
              )}
            </div>
          </div>

          {/* Compact Action Buttons */}
          <div className="flex gap-3 p-6 pt-4">
            <button onClick={onClose} className="secondary-button flex-1 py-2.5">
              Cancel
            </button>
            <button
              onClick={handleUpload}
              disabled={!selectedFile}
              className={`primary-button flex-1 py-2.5 flex items-center justify-center gap-1.5 ${
                !selectedFile ? 'opacity-50 cursor-not-allowed' : ''
              }`}
            >
              {selectedFile ? (
                <>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                    <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" strokeWidth="2"/>
                  </svg>
                  Generate Design
                </>
              ) : (
                'Select File First'
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default FileUploadModal

