'use client'

import React, { useState, useRef, useEffect } from 'react'
import Navigation from '@/components/Navigation'
import FilterSection from '@/components/FilterSection'
import RoomView from '@/components/RoomView'
import ChatInterface from '@/components/ChatInterface'
import DesignInput from '@/components/DesignInput'
import FileUploadModal from '@/components/FileUploadModal'
import PipelineProgressModal from '@/components/PipelineProgressModal'
import AnimatedSection from '@/components/AnimatedSection'
import { usePipeline } from '@/hooks/usePipeline'

export default function Home() {
  const [currentScreen, setCurrentScreen] = useState<'input' | 'result'>('input')
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [userPrompt, setUserPrompt] = useState('')
  const [selectedBudget, setSelectedBudget] = useState<number>(5000)
  const [selectedDimensions, setSelectedDimensions] = useState<string>('12x18')
  const [uploadedUsdzFile, setUploadedUsdzFile] = useState<File | null>(null)
  const navigateTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  
  const {
    status: pipelineStatus,
    progress,
    error: pipelineError,
    result: pipelineResult,
    finalUsdzBlob,
    finalGlbBlob,
    previewImages,
    renderImages,
    optimizationGif,
    isDownloadingAssets,
    downloadProgress,
    uploadAndRunPipeline,
    downloadFinalUSDZ,
    retryPipeline,
    abortPipeline,
    reset: resetPipeline
  } = usePipeline()

  // Auto-navigate to result when pipeline completes (no modal prompt)
  useEffect(() => {
    if (pipelineStatus === 'completed') {
      setCurrentScreen('result')
    }
  }, [pipelineStatus])

  const handleReset = () => {
    if (navigateTimeoutRef.current) {
      clearTimeout(navigateTimeoutRef.current)
      navigateTimeoutRef.current = null
    }
    resetPipeline()
    setCurrentScreen('input')
    setUserPrompt('')
    setUploadedUsdzFile(null)
  }

  const handleGenerate = async (prompt: string) => {
    if (!uploadedUsdzFile) return // Mandatory: must upload room first
    setUserPrompt(prompt)
    try {
      console.log('🚀 Generate with uploaded USDZ:', uploadedUsdzFile.name)
      await uploadAndRunPipeline(uploadedUsdzFile, prompt, selectedBudget)
    } catch (error) {
      console.error('Pipeline failed:', error)
    }
  }

  const handleUsdzSelected = (file: File) => {
    setUploadedUsdzFile(file)
    setShowUploadModal(false)
  }

  const handleBackToInput = () => {
    setCurrentScreen('input')
    resetPipeline()
    setUserPrompt('')
  }

  return (
    <div className="min-h-screen relative overflow-hidden">
      {/* Animated Background */}
      <div className="absolute inset-0 -z-10">
        {/* Base gradient */}
        <div className="absolute inset-0"
             style={{ 
               background: `linear-gradient(135deg, rgb(var(--primary-50)) 0%, rgb(var(--surface-soft)) 40%, rgb(var(--primary-50)) 100%)` 
             }}></div>
        
        {/* Animated floating elements */}
        <div className="absolute top-32 right-32 w-40 h-40 rounded-full opacity-20 animate-float blur-sm"
             style={{ 
               background: `radial-gradient(circle, rgb(var(--primary-200)) 0%, transparent 70%)`,
               animationDelay: '0s',
               animationDuration: '8s'
             }}></div>
        <div className="absolute top-80 left-20 w-32 h-32 rounded-full opacity-15 animate-float blur-sm"
             style={{ 
               background: `radial-gradient(circle, rgb(var(--primary-300)) 0%, transparent 70%)`,
               animationDelay: '2s',
               animationDuration: '10s'
             }}></div>
        <div className="absolute bottom-40 right-16 w-24 h-24 rounded-full opacity-10 animate-float blur-sm"
             style={{ 
               background: `radial-gradient(circle, rgb(var(--primary-400)) 0%, transparent 70%)`,
               animationDelay: '4s',
               animationDuration: '12s'
             }}></div>
        <div className="absolute bottom-20 left-1/3 w-36 h-36 rounded-full opacity-12 animate-float blur-sm"
             style={{ 
               background: `radial-gradient(circle, rgb(var(--primary-200)) 0%, transparent 70%)`,
               animationDelay: '6s',
               animationDuration: '14s'
             }}></div>
             
        {/* Subtle mesh gradient overlay */}
        <div className="absolute inset-0 opacity-5"
             style={{ 
               background: `repeating-linear-gradient(45deg, 
                 rgba(var(--primary-500), 0.02) 0px, 
                 transparent 2px, 
                 transparent 40px, 
                 rgba(var(--primary-500), 0.02) 42px
               )`
             }}></div>
      </div>

      {/* Navigation */}
      <Navigation />

      {/* Main Content */}
      <main className="px-4 py-6">
        {currentScreen === 'input' ? (
          /* Input Screen - redesigned */
          <div className="max-w-2xl mx-auto">
            <FilterSection 
              onReset={handleReset}
              onBudgetChange={setSelectedBudget}
              onDimensionsChange={setSelectedDimensions}
            />

            <DesignInput
              onGenerate={handleGenerate}
              hasUploadedRoom={!!uploadedUsdzFile}
              onUploadClick={() => setShowUploadModal(true)}
              uploadedFileName={uploadedUsdzFile?.name}
            />

            {/* Features */}
            <AnimatedSection animation="slide-up" delay={400} className="mt-12">
              <div className="grid grid-cols-3 gap-3 sm:gap-4">
                {[
                  { icon: "🤖", label: "AI-Powered" },
                  { icon: "📱", label: "3D Preview" },
                  { icon: "🛒", label: "Real Products" }
                ].map((f, i) => (
                  <div key={i} className="card-premium p-4 sm:p-5 flex flex-col items-center justify-center gap-2 text-center">
                    <span className="text-2xl">{f.icon}</span>
                    <span className="text-xs font-semibold" style={{ color: 'rgb(var(--text-secondary))' }}>{f.label}</span>
                  </div>
                ))}
              </div>
            </AnimatedSection>
          </div>
        ) : (
          /* Result Screen - wider container so preview and chat get more width */
          <div className="w-full max-w-[1600px] mx-auto px-2 sm:px-4">
            <AnimatedSection animation="fade-in" className="grid grid-cols-1 lg:grid-cols-12 gap-4">
              {/* Left Panel - 3D Preview (~67%) */}
              <div className="lg:col-span-8 flex flex-col min-h-[calc(100vh-120px)]">
                <div className="compact-card p-4 flex flex-col flex-1 min-h-0">
                  {/* Room View - fills space to bottom */}
                  <div className="flex-1 min-h-0 flex flex-col">
                    <RoomView 
                      finalUsdzBlob={finalUsdzBlob}
                      finalGlbBlob={finalGlbBlob}
                      previewImages={previewImages}
                      renderImages={renderImages}
                      optimizationGif={optimizationGif}
                      pipelineResult={pipelineResult}
                      onDownloadUSDZ={downloadFinalUSDZ}
                      isDownloadingAssets={isDownloadingAssets}
                      downloadProgress={downloadProgress}
                    />
                  </div>
                </div>
              </div>

              {/* Right Panel - Chat (~33%) */}
              <div className="lg:col-span-4">
                <div className="compact-card h-[calc(100vh-140px)] overflow-hidden border shadow-sm"
                     style={{ borderColor: 'rgb(var(--surface-muted))' }}>
                  <ChatInterface 
                    initialMessage={userPrompt}
                    pipelineResult={pipelineResult}
                    onDownloadUSDZ={downloadFinalUSDZ}
                  />
                </div>
              </div>
            </AnimatedSection>
          </div>
        )}
      </main>

      {/* File Upload Modal */}
      {showUploadModal && (
        <FileUploadModal
          key="upload-modal"
          isOpen={showUploadModal}
          onClose={() => setShowUploadModal(false)}
          onUpload={handleUsdzSelected}
        />
      )}

      {/* Pipeline Progress Modal */}
      <PipelineProgressModal
        isOpen={['uploading', 'running'].includes(pipelineStatus)}
        status={pipelineStatus}
        progress={progress}
        error={pipelineError}
        onClose={() => {}}
        onRetry={retryPipeline}
        onAbort={abortPipeline}
      />
      
    </div>
  )
}

