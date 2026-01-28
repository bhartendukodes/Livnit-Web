'use client'

import React, { useState } from 'react'
import Navigation from '@/components/Navigation'
import FilterSection from '@/components/FilterSection'
import RoomView from '@/components/RoomView'
import ChatInterface from '@/components/ChatInterface'
import DesignInput from '@/components/DesignInput'
import FileUploadModal from '@/components/FileUploadModal'
import PipelineProgressModal from '@/components/PipelineProgressModal'
import BackendStatus from '@/components/BackendStatus'
import ApiConnectionTest from '@/components/ApiConnectionTest'
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
    if (pipelineStatus === 'completed' && finalUsdzBlob) {
      console.log('🎯 Pipeline completed with USDZ blob - switching to result screen')
      setCurrentScreen('result')
    }
  }, [pipelineStatus, finalUsdzBlob])

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

  const handleSurprise = () => {
    const surprisePrompts = [
      'Create a minimalist Scandinavian living room with natural wood accents',
      'Design a cozy bohemian bedroom with plants and warm lighting',
      'Plan a modern industrial kitchen with exposed brick and metal fixtures',
    ]
    const randomPrompt = surprisePrompts[Math.floor(Math.random() * surprisePrompts.length)]
    setUserPrompt(randomPrompt)
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
      {/* Subtle Background */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute inset-0"
             style={{ 
               background: `linear-gradient(135deg, rgb(var(--surface-soft)) 0%, rgb(var(--surface)) 100%)` 
             }}></div>
        
        {/* Subtle geometric accents */}
        <div className="absolute top-20 right-20 w-32 h-32 bg-primary-100 rounded-full opacity-30 animate-float"
             style={{ backgroundColor: 'rgb(var(--primary-100))', animationDelay: '0s' }}></div>
        <div className="absolute bottom-40 left-20 w-24 h-24 bg-primary-200 rounded-full opacity-20 animate-float"
             style={{ backgroundColor: 'rgb(var(--primary-200))', animationDelay: '3s' }}></div>
      </div>

      {/* Backend Status Indicator */}
      <BackendStatus />
      
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
            <div className="compact-card p-8 md:p-12">
              <DesignInput
                onGenerate={handleGenerate}
                onSurprise={handleSurprise}
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
                  <div key={index} className="compact-card p-4 text-center hover:shadow-md transition-all duration-200">
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
          /* Result Screen */
          <div className="max-w-7xl mx-auto">
            <AnimatedSection animation="fade-in" className="grid grid-cols-1 lg:grid-cols-4 gap-4">
              {/* Left Panel - Room View */}
              <div className="lg:col-span-3">
                <div className="compact-card p-4 flex flex-col min-h-[calc(100vh-140px)]">
                  {/* Compact Filter Section */}
                  <FilterSection 
                    onReset={handleReset}
                    onBudgetChange={setSelectedBudget}
                  />

                  {/* Room View */}
                  <div className="flex-1 min-h-0">
                    <RoomView 
                      finalUsdzBlob={finalUsdzBlob}
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

              {/* Right Panel - Chat Interface */}
              <div className="lg:col-span-1">
                <div className="compact-card h-[calc(100vh-140px)] overflow-hidden">
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
      
      {/* API Connection Test - only in development */}
      {process.env.NODE_ENV === 'development' && (
        <ApiConnectionTest />
      )}
      
      {/* Debug info - remove in production */}
      {process.env.NODE_ENV === 'development' && (
        <div className="fixed bottom-4 left-4 bg-black/80 text-white px-3 py-2 rounded text-xs z-[10000] pointer-events-none">
          <div>Pipeline: {pipelineStatus}</div>
          <div>Progress: {progress.nodesCompleted.length}/{progress.totalNodes || 0}</div>
        </div>
      )}
    </div>
  )
}

