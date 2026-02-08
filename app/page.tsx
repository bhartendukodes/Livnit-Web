'use client'

import React, { useState } from 'react'
import FileUploadModal from '@/components/FileUploadModal'
import PipelineProgressModal from '@/components/PipelineProgressModal'
import NetworkStatus from '@/components/NetworkStatus'
import RoomView from '@/components/RoomView'
import ChatInterface from '@/components/ChatInterface'
import { usePipeline } from '@/hooks/usePipeline'

// Inline icons (no lucide-react dependency)
const IconSparkles = () => (
  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/></svg>
)
const IconChevronDown = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m6 9 6 6 6-6"/></svg>
)
const IconUploadCloud = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M12 12v9"/><path d="m16 16-4-4-4 4"/></svg>
)
const IconX = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
)
const IconLoader2 = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
)
const IconArrowRight = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
)
const IconShieldCheck = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
)
const IconMaximize = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/></svg>
)
const IconCheckCircle2 = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>
)

const SUGGESTION_PILLS = [
  "Clean minimalist living room: low white sofa, slim black metal coffee table.",
  "Classic mid-century: tufted olive sofa, walnut credenza, tapered-leg coffee table.",
  "Industrial loft: leather sectional, reclaimed wood accents, exposed metal shelving.",
  "Soft modern: curved bouclé sofa, marble-top coffee table, velvet accent chair."
]

export default function Home() {
  const [currentScreen, setCurrentScreen] = useState<'input' | 'result'>('input')
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [userPrompt, setUserPrompt] = useState('')
  const [selectedRoomType, setSelectedRoomType] = useState<string>('Living Room')
  const [selectedBudget, setSelectedBudget] = useState<string>('Standard ($5k - $15k)')
  const [selectedDimensions, setSelectedDimensions] = useState<string>('Standard (150-300 sqft)')
  const [uploadedUsdzFile, setUploadedUsdzFile] = useState<File | null>(null)
  
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
    iterateDesign,
    downloadFinalUSDZ,
    retryPipeline,
    abortPipeline,
    clearError,
    canIterate
  } = usePipeline()

  const handleGenerate = async () => {
    if (!uploadedUsdzFile || !userPrompt.trim()) return
    try {
      await uploadAndRunPipeline(uploadedUsdzFile, userPrompt, getBudgetValue(selectedBudget))
      setCurrentScreen('result')
    } catch (error) {
      console.error('Pipeline failed:', error)
    }
  }

  const getBudgetValue = (budgetString: string): number => {
    if (budgetString.includes('$1k - $5k')) return 2500
    if (budgetString.includes('$5k - $15k')) return 7500
    if (budgetString.includes('$15k - $40k')) return 20000
    return 30000
  }

  const handleUsdzSelected = (file: File) => {
    setUploadedUsdzFile(file)
    setShowUploadModal(false)
  }

  const removeUpload = (e: React.MouseEvent) => {
    e.stopPropagation()
    setUploadedUsdzFile(null)
  }

  const handleReset = () => {
    setUserPrompt('')
    setUploadedUsdzFile(null)
    setSelectedRoomType('Living Room')
    setSelectedBudget('Standard ($5k - $15k)')
    setSelectedDimensions('Standard (150-300 sqft)')
  }

  const isLivingRoom = selectedRoomType === 'Living Room'

  if (currentScreen === 'result') {
    return (
      <div className="min-h-screen flex flex-col bg-white">
        {/* Top bar on result screen */}
        <nav className="shrink-0 flex items-center justify-between px-6 py-3 border-b border-gray-100 bg-gray-50/50">
          <a href="https://livinit-ai.vercel.app/" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2">
            <img src="/logo.png" alt="Livinit" className="w-10 h-10 object-contain" />
            <span className="font-bold text-gray-900">Livinit</span>
          </a>
          <button
            type="button"
            onClick={() => setCurrentScreen('input')}
            className="text-sm font-medium text-gray-600 hover:text-blue-500"
          >
            ← New design
          </button>
        </nav>
        <main className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-12 gap-0 px-2 sm:px-4 py-2">
          <div className="lg:col-span-8 min-h-0 flex flex-col">
            <div className="flex-1 min-h-0 flex flex-col rounded-xl border border-gray-100 bg-white shadow-sm overflow-hidden">
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
                status={pipelineStatus}
              />
            </div>
          </div>
          <div className="lg:col-span-4 min-h-[50vh] lg:min-h-0 flex flex-col">
            <div className="flex-1 min-h-0 rounded-xl border border-gray-100 bg-white shadow-sm overflow-hidden flex flex-col">
              <ChatInterface
                initialMessage={userPrompt}
                pipelineResult={pipelineResult}
                onDownloadUSDZ={downloadFinalUSDZ}
                canIterate={canIterate}
                onIterate={iterateDesign}
                pipelineStatus={pipelineStatus}
                pipelineProgress={progress}
              />
            </div>
          </div>
        </main>
        <PipelineProgressModal
          isOpen={['uploading', 'running', 'error'].includes(pipelineStatus)}
          status={pipelineStatus}
          progress={progress}
          error={pipelineError}
          onClose={clearError}
          onRetry={retryPipeline}
          onAbort={abortPipeline}
          isIteration={canIterate && !!pipelineResult}
        />
        <NetworkStatus />
      </div>
    )
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-white">
      {/* Top Navigation Bar */}
      <nav className="shrink-0 flex items-center justify-between px-8 py-4 border-b border-gray-100 bg-gray-50/50">
        <a 
          href="https://livinit-ai.vercel.app/" 
          target="_blank" 
          rel="noopener noreferrer"
          className="flex items-center gap-3 group"
        >
          <div className="w-12 h-12 rounded-xl overflow-hidden">
            <img src="/logo.png" alt="Livinit" className="w-full h-full object-contain" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900 leading-tight group-hover:text-blue-500 transition-colors">Livinit</h1>
            <p className="text-sm font-medium text-blue-500 leading-tight">AI Design Studio</p>
          </div>
        </a>
        <div className="flex items-center gap-6">
          <a 
            href="https://livinit-ai.vercel.app/partner" 
            target="_blank" 
            rel="noopener noreferrer"
            className="text-sm font-bold uppercase tracking-wide text-gray-500 hover:text-blue-500 transition-colors"
          >
            Partner
          </a>
          <a 
            href="https://livinit-ai.vercel.app/" 
            target="_blank" 
            rel="noopener noreferrer"
            className="bg-blue-500 text-white px-5 py-2.5 rounded-full text-sm font-bold uppercase tracking-wide hover:bg-blue-600 transition-colors"
          >
            Main Site
          </a>
        </div>
      </nav>

      <div className="flex-1 flex flex-col justify-center py-4 overflow-hidden">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <div className="space-y-8 animate-in fade-in duration-1000 max-h-full">
          
          {/* Header Section */}
          <div className="text-center max-w-5xl mx-auto space-y-4 shrink-0">
            <div className="inline-flex items-center gap-2 px-6 py-2 rounded-full bg-blue-500/5 border border-blue-500/10 text-xs font-bold uppercase tracking-[0.25em] text-blue-500">
              <IconSparkles />
              Spatial Intelligence Engine
            </div>
            <h2 className="text-4xl md:text-6xl font-serif font-bold text-gray-900 tracking-tight leading-none whitespace-nowrap">
              Livinit <span className="text-blue-500 italic font-light">Design Studio</span>
            </h2>
            <p className="text-base md:text-lg text-gray-500 font-medium leading-relaxed max-w-xl mx-auto">
              LIVINIT uses advanced spatial intelligence to respect your floor plan, your budget, and the flow of your actual home.
            </p>
          </div>

          {/* Main Configuration Card */}
          <div className="max-w-5xl mx-auto bg-white rounded-[3rem] shadow-[0_40px_100px_-20px_rgba(0,0,0,0.04)] border border-gray-100 overflow-hidden flex flex-col">
            
            {/* Room selection: Room type dropdown (only Living Room working) + Dimensions + Budget */}
            <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-gray-200 border-b border-gray-100 shrink-0">
              {/* 01. Room type — Living Room working, rest coming soon */}
              <div className={`p-6 md:p-8 group ${selectedRoomType !== 'Living Room' ? 'bg-gray-50/80' : ''}`}>
                <label className="block text-xs font-bold uppercase tracking-wider text-gray-500 mb-3">
                  01. Room type
                </label>
                <div className="relative">
                  <select
                    value={selectedRoomType}
                    onChange={(e) => setSelectedRoomType(e.target.value)}
                    className="w-full bg-transparent text-base md:text-lg font-bold outline-none appearance-none cursor-pointer text-gray-900"
                  >
                    <option value="Living Room">Living Room</option>
                    <option value="Bedroom" disabled>Bedroom (coming soon)</option>
                    <option value="Kitchen" disabled>Kitchen (coming soon)</option>
                    <option value="Dining Room" disabled>Dining Room (coming soon)</option>
                    <option value="Home Office" disabled>Home Office (coming soon)</option>
                    <option value="Studio Apartment" disabled>Studio Apartment (coming soon)</option>
                  </select>
                  <IconChevronDown className="absolute right-0 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 pointer-events-none" />
                </div>
              </div>
              {/* 02. Dimensions */}
              <div className={`p-6 md:p-8 group cursor-pointer hover:bg-gray-50/50 transition-colors ${selectedDimensions !== 'Standard (150-300 sqft)' ? 'bg-blue-50/80' : ''}`}>
                <label className="block text-xs font-bold uppercase tracking-wider text-gray-500 mb-3">
                  02. Dimensions
                </label>
                <div className="relative">
                  <select
                    value={selectedDimensions}
                    onChange={(e) => setSelectedDimensions(e.target.value)}
                    className={`w-full bg-transparent text-base md:text-lg font-bold outline-none appearance-none cursor-pointer transition-colors ${selectedDimensions !== 'Standard (150-300 sqft)' ? 'text-blue-600' : 'text-gray-900'}`}
                  >
                    <option value="Compact (<150 sqft)">Compact (&lt;150 sqft)</option>
                    <option value="Standard (150-300 sqft)">Standard (150-300 sqft)</option>
                    <option value="Spacious (300-500 sqft)">Spacious (300-500 sqft)</option>
                    <option value="Grand (500+ sqft)">Grand (500+ sqft)</option>
                  </select>
                  <IconChevronDown className="absolute right-0 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 pointer-events-none group-hover:text-blue-500 transition-colors" />
                </div>
              </div>
              {/* 03. Budget range — required for generate */}
              <div className={`p-6 md:p-8 group cursor-pointer hover:bg-gray-50/50 transition-colors ${selectedBudget !== 'Standard ($5k - $15k)' ? 'bg-blue-50/80' : ''}`}>
                <label className="block text-xs font-bold uppercase tracking-wider text-gray-500 mb-3">
                  03. Budget range <span className="text-gray-400 font-normal">(required)</span>
                </label>
                <div className="relative">
                  <select
                    value={selectedBudget}
                    onChange={(e) => setSelectedBudget(e.target.value)}
                    className={`w-full bg-transparent text-base md:text-lg font-bold outline-none appearance-none cursor-pointer transition-colors ${selectedBudget !== 'Standard ($5k - $15k)' ? 'text-blue-600' : 'text-gray-900'}`}
                  >
                    <option value="Economy ($1k - $5k)">Economy ($1k - $5k)</option>
                    <option value="Standard ($5k - $15k)">Standard ($5k - $15k)</option>
                    <option value="Premium ($15k - $40k)">Premium ($15k - $40k)</option>
                    <option value="Luxury ($40k+)">Luxury ($40k+)</option>
                  </select>
                  <IconChevronDown className="absolute right-0 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 pointer-events-none group-hover:text-blue-500 transition-colors" />
                </div>
              </div>
            </div>

            {/* USDZ Room Upload Row */}
            <div className="px-8 py-4 shrink-0">
              <div 
                onClick={() => setShowUploadModal(true)}
                className={`group relative w-full rounded-[2rem] border border-gray-200 flex items-center justify-between px-6 py-5 cursor-pointer hover:border-blue-500/30 transition-all ${
                  uploadedUsdzFile ? 'bg-blue-500/5 border-blue-500/30' : 'bg-gray-50'
                }`}
              >
                <div className="flex items-center gap-4">
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center transition-all ${
                    uploadedUsdzFile ? 'bg-blue-500 text-white shadow-lg' : 'bg-gray-200 text-gray-500 group-hover:bg-blue-500 group-hover:text-white group-hover:shadow-lg'
                  }`}>
                    <IconUploadCloud className="w-6 h-6" />
                  </div>
                  <div>
                    <h4 className={`font-bold text-base ${uploadedUsdzFile ? 'text-blue-600' : 'text-gray-900'}`}>Upload room model (USDZ)</h4>
                    <p className="text-sm text-gray-500 font-medium mt-0.5">Add your 3D room file for a personalized layout</p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  {uploadedUsdzFile && (
                    <button 
                      onClick={removeUpload}
                      className="bg-white/80 p-2 rounded-full hover:bg-blue-500 hover:text-white transition-all shadow-sm"
                    >
                      <IconX className="w-4 h-4" />
                    </button>
                  )}
                  <div className={`px-5 py-2.5 rounded-full border text-xs font-bold uppercase tracking-wide transition-all ${
                    uploadedUsdzFile 
                      ? 'bg-blue-500 text-white border-blue-500' 
                      : 'bg-white border-gray-300 text-gray-600 group-hover:text-blue-500 group-hover:border-blue-500/40'
                  }`}>
                    {uploadedUsdzFile ? '✓ USDZ selected' : 'Open USDZ'}
                  </div>
                </div>
              </div>
            </div>

            {/* Describe your design — clean section */}
            <div className="px-8 pb-8 flex flex-col flex-grow min-h-0">
              <div className="rounded-2xl border border-gray-100 bg-gray-50/30 overflow-hidden">
                {/* Section header */}
                <div className="px-6 pt-5 pb-4 border-b border-gray-100">
                  <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-0.5">Describe your design</p>
                  <p className="text-sm text-gray-500">Style, furniture, colors — tell us what you want</p>
                </div>

                {/* Quick picks */}
                <div className="px-6 py-4 bg-white/60">
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 mb-3">Quick picks</p>
                  <div className="flex flex-wrap gap-2">
                    {SUGGESTION_PILLS.map((pill, idx) => (
                      <button
                        key={idx}
                        onClick={() => setUserPrompt(pill)}
                        className={`max-w-full text-left px-3 py-2 rounded-lg border text-[11px] font-medium leading-snug transition-all shrink-0 line-clamp-2 ${
                          userPrompt === pill
                            ? 'bg-blue-500 text-white border-blue-500 shadow-sm'
                            : 'bg-white border-gray-200 text-gray-600 hover:border-blue-300 hover:bg-blue-50/50'
                        }`}
                      >
                        {pill}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Input + CTA */}
                <div className="px-6 pb-6 pt-2">
                  <textarea
                    value={userPrompt}
                    onChange={(e) => setUserPrompt(e.target.value)}
                    placeholder="Or type your own: e.g. Soft modern with curved bouclé sofa and marble coffee table"
                    className="w-full px-4 py-3 rounded-xl border border-gray-200 bg-white text-sm text-gray-900 placeholder:text-gray-400 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20 resize-none min-h-[88px] transition-all"
                  />
                  <div className="flex justify-between items-center mt-4">
                    <div className="flex items-center gap-3">
                      <button
                        type="button"
                        onClick={handleReset}
                        className="px-4 py-2.5 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50 hover:border-gray-300 transition-all"
                      >
                        Reset
                      </button>
                      {!isLivingRoom && (
                        <span className="text-xs text-amber-600 font-medium">Only Living Room is available right now.</span>
                      )}
                    </div>
                    <button
                      onClick={handleGenerate}
                      disabled={!isLivingRoom || !uploadedUsdzFile || !userPrompt.trim() || !selectedBudget || pipelineStatus === 'uploading' || pipelineStatus === 'running'}
                      className="bg-blue-500 text-white px-8 py-3 rounded-xl font-semibold text-sm flex items-center gap-2 hover:bg-blue-600 transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-blue-500/25"
                    >
                      {pipelineStatus === 'uploading' || pipelineStatus === 'running' ? (
                        <IconLoader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <>
                          Generate plan <IconArrowRight className="w-4 h-4" />
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Bottom Badges */}
          <div className="flex justify-center items-center gap-10 text-xs font-bold text-gray-500 uppercase tracking-wider shrink-0">
            <div className="flex items-center gap-2 group hover:text-blue-500 transition-colors">
               <IconShieldCheck className="w-4 h-4" /> Real SKUs
            </div>
            <div className="flex items-center gap-2 group hover:text-blue-500 transition-colors">
               <IconMaximize className="w-4 h-4" /> To-Scale
            </div>
            <div className="flex items-center gap-2 group hover:text-blue-500 transition-colors">
               <IconCheckCircle2 className="w-4 h-4" /> Logic Verified
            </div>
          </div>
        </div>
      </div>
      </div>

      {/* File Upload Modal */}
      {showUploadModal && (
        <FileUploadModal
          isOpen={showUploadModal}
          onClose={() => setShowUploadModal(false)}
          onUpload={handleUsdzSelected}
        />
      )}

      {/* Pipeline Progress Modal */}
      <PipelineProgressModal
        isOpen={['uploading', 'running', 'error'].includes(pipelineStatus)}
        status={pipelineStatus}
        progress={progress}
        error={pipelineError}
        onClose={clearError}
        onRetry={retryPipeline}
        onAbort={abortPipeline}
        isIteration={canIterate && pipelineResult !== null}
      />
      
      {/* Network Status Indicator */}
      <NetworkStatus />
    </div>
  )
}