'use client'

import React, { useState } from 'react'
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

  // Auto-switch to result screen when pipeline completes
  React.useEffect(() => {
    if (pipelineStatus === 'completed' && (finalUsdzBlob || finalGlbBlob)) {
      console.log('🎯 Pipeline completed with 3D file - switching to result screen')
      setCurrentScreen('result')
    }
  }, [pipelineStatus, finalUsdzBlob, finalGlbBlob])

  const handleReset = () => {
    console.log('Filters reset')
    resetPipeline()
    setCurrentScreen('input')
    setUserPrompt('')
  }

  const handleGenerate = (prompt: string) => {
    console.log('🚀 Generate design clicked:', prompt)
    setUserPrompt(prompt)
    setShowUploadModal(true)
  }


  const handleFileUpload = async (file: File) => {
    setShowUploadModal(false)
    
    try {
      console.log('🔄 Starting pipeline with uploaded file:', file.name)
      await uploadAndRunPipeline(file, userPrompt, selectedBudget)
      setCurrentScreen('result')
    } catch (error) {
      console.error('Pipeline failed:', error)
      // Error is handled by the hook, just log it
    }
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
          /* Input Screen */
          <div className="max-w-4xl mx-auto">
            {/* Filter Section */}
            <FilterSection 
              onReset={handleReset}
              onBudgetChange={setSelectedBudget}
            />

            {/* Design Input Section */}
            <div className="compact-card p-8 md:p-12 border shadow-sm"
                 style={{ borderColor: 'rgb(var(--surface-muted))' }}>
              <DesignInput
                onGenerate={handleGenerate}
              />
            </div>

            {/* Compact Features Section */}
            <AnimatedSection animation="slide-up" delay={400} className="mt-8">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {[
                  {
                    icon: "🤖",
                    title: "AI-Powered",
                    description: "Smart design algorithms"
                  },
                  {
                    icon: "📱",
                    title: "3D Preview",
                    description: "Interactive visualization"
                  },
                  {
                    icon: "🛒",
                    title: "Real Products",
                    description: "Direct purchase links"
                  }
                ].map((feature, index) => (
                  <div key={index} className="compact-card p-4 text-center hover:shadow-md transition-all duration-200 border" 
                       style={{ borderColor: 'rgb(var(--surface-muted))' }}>
                    <div className="text-2xl mb-2">{feature.icon}</div>
                    <h4 className="font-semibold text-primary-900 text-sm mb-1" 
                        style={{ color: 'rgb(var(--text-primary))' }}>
                      {feature.title}
                    </h4>
                    <p className="text-xs text-muted" style={{ color: 'rgb(var(--text-muted))' }}>
                      {feature.description}
                    </p>
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
          onUpload={handleFileUpload}
        />
      )}

      {/* Pipeline Progress Modal */}
      <PipelineProgressModal
        isOpen={['uploading', 'running'].includes(pipelineStatus)}
        status={pipelineStatus}
        progress={progress}
        error={pipelineError}
        onClose={() => {
          if (pipelineStatus === 'completed') {
            console.log('🎯 Pipeline completed, switching to result screen')
            setCurrentScreen('result')
          }
        }}
        onRetry={retryPipeline}
        onAbort={abortPipeline}
      />
      
    </div>
  )
}

