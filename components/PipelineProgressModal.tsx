'use client'

import React, { useState, useEffect, useRef } from 'react'
import { PipelineProgress, PipelineStatus } from '@/hooks/usePipeline'

interface PipelineProgressModalProps {
  isOpen: boolean
  status: PipelineStatus
  progress: PipelineProgress
  error: string | null
  onClose: () => void
  onRetry: () => void
  onAbort: () => void
}

const PIPELINE_STEPS = [
  { id: 'extract_room', name: 'Analyzing Space', icon: '🏠' },
  { id: 'select_assets', name: 'Curating Furniture', icon: '🛋️' },
  { id: 'validate_and_cost', name: 'Checking Availability', icon: '✅' },
  { id: 'initial_layout', name: 'First Layout', icon: '📐' },
  { id: 'layout_preview', name: 'Preview', icon: '🖼️' },
  { id: 'refine_layout', name: 'Refining Design', icon: '✨' },
  { id: 'layout_preview_refine', name: 'Updating Preview', icon: '🎨' },
  { id: 'layoutvlm', name: 'AI Optimization', icon: '🤖' },
  { id: 'layout_preview_post', name: 'Final Preview', icon: '📸' },
  { id: 'render_scene', name: 'Render Scene', icon: '🎬' },
]

const PipelineProgressModal: React.FC<PipelineProgressModalProps> = ({
  isOpen,
  status,
  progress,
  error,
  onClose,
  onRetry,
  onAbort
}) => {
  const [currentStepIndex, setCurrentStepIndex] = useState(0)
  const [displayPercent, setDisplayPercent] = useState(0)
  const startTimeRef = useRef<number | null>(null)

  useEffect(() => {
    if (progress.currentNode) {
      const idx = PIPELINE_STEPS.findIndex(s => s.id === progress.currentNode)
      if (idx >= 0) setCurrentStepIndex(idx)
    }
  }, [progress.currentNode])

  // Step-based + smooth crawl so bar never looks stuck (1, 2, 3... every ~2 sec)
  const totalNodes = progress.totalNodes || PIPELINE_STEPS.length
  const completedCount = progress.nodesCompleted.length
  const currentProgress = progress.nodeProgress && progress.nodeProgress.total > 0
    ? progress.nodeProgress.current / progress.nodeProgress.total
    : 0
  const stepPercent = totalNodes > 0 ? ((completedCount + currentProgress) / totalNodes) * 100 : 0
  const targetPercent = status === 'completed' ? 100 : Math.min(99, stepPercent)

  // Crawl: bar increases ~1% every 2 sec so it never looks stuck
  useEffect(() => {
    if (!isOpen) return
    if (status === 'completed') {
      setDisplayPercent(100)
      return
    }
    if (status !== 'running') return
    if (!startTimeRef.current) startTimeRef.current = Date.now()

    const interval = setInterval(() => {
      const elapsed = (Date.now() - (startTimeRef.current || 0)) / 1000
      const timeBased = Math.min(98, Math.floor(elapsed / 0.8)) // +1% every ~0.8 sec so bar keeps moving
      const percent = Math.max(targetPercent, timeBased)
      setDisplayPercent(Math.round(percent))
    }, 800) // Update every 800ms for smoother feel

    return () => clearInterval(interval)
  }, [isOpen, status, targetPercent])

  useEffect(() => {
    if (!isOpen) {
      startTimeRef.current = null
      setDisplayPercent(0)
    }
  }, [isOpen])

  // Sync when step completes (target jumps)
  useEffect(() => {
    setDisplayPercent(p => (targetPercent > p ? Math.round(targetPercent) : p))
  }, [targetPercent])

  if (!isOpen) return null

  const currentStep = PIPELINE_STEPS[currentStepIndex] || PIPELINE_STEPS[0]

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={status === 'completed' ? onClose : undefined}
      />

      {/* Card */}
      <div 
        className="relative w-full max-w-lg overflow-hidden rounded-3xl"
        style={{
          background: 'linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(250,252,255,0.95) 100%)',
          border: '1px solid rgba(var(--primary-500), 0.1)',
          boxShadow: '0 1px 0 0 rgba(255,255,255,0.9) inset, 0 24px 48px rgba(0,0,0,0.12), 0 0 0 1px rgba(0,0,0,0.03)'
        }}
      >
        {/* Header */}
        <div 
          className="px-6 pt-8 pb-6 text-center relative overflow-hidden rounded-t-3xl"
          style={{ 
            background: status === 'completed' 
              ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)' 
              : status === 'error'
              ? 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)'
              : 'linear-gradient(135deg, rgb(var(--primary-500)) 0%, rgb(var(--primary-600)) 100%)'
          }}
        >
          <div className="absolute inset-0">
            <div className="absolute -top-6 -right-6 w-32 h-32 bg-white/10 rounded-full" />
            <div className="absolute -bottom-10 -left-10 w-40 h-40 bg-white/5 rounded-full" />
          </div>
          
          <div className="relative">
            <div 
              className="w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center"
              style={{ backgroundColor: 'rgba(255,255,255,0.2)', backdropFilter: 'blur(8px)' }}
            >
              <span className="text-3xl">
                {status === 'completed' ? '🎉' : status === 'error' ? '😔' : currentStep.icon}
              </span>
            </div>
            <h2 className="text-xl font-bold text-white">
              {status === 'uploading' && 'Uploading...'}
              {status === 'running' && 'Creating Design'}
              {status === 'completed' && 'All Done!'}
              {status === 'error' && 'Something Went Wrong'}
              {status === 'aborted' && 'Cancelled'}
            </h2>
            {status === 'running' && (
              <p className="text-white/80 text-sm mt-1">{currentStep.name}</p>
            )}
          </div>
        </div>

        {/* Body */}
        <div className="px-6 py-6">
          {/* Progress bar - step based */}
          <div className="mb-6">
            <div className="flex justify-between text-sm mb-2">
              <span className="font-medium" style={{ color: 'rgb(var(--text-primary))' }}>
                {status === 'running' && `Step ${completedCount + 1} of ${totalNodes}`}
                {status === 'completed' && 'Your design is ready'}
                {status === 'error' && 'Please try again'}
              </span>
              <span className="font-bold tabular-nums" style={{ color: 'rgb(var(--primary-600))' }}>
                {displayPercent}%
              </span>
            </div>
            <div 
              className="w-full rounded-full h-3 overflow-hidden"
              style={{ backgroundColor: 'rgb(var(--surface-muted))' }}
            >
              <div 
                className="h-3 rounded-full transition-all duration-500 ease-out"
                style={{ 
                  width: `${displayPercent}%`,
                  background: status === 'completed' 
                    ? 'linear-gradient(90deg, #10b981, #059669)' 
                    : status === 'error'
                    ? 'linear-gradient(90deg, #ef4444, #dc2626)'
                    : 'linear-gradient(90deg, rgb(var(--primary-400)), rgb(var(--primary-600)))'
                }}
              />
            </div>
          </div>

          {/* Step dots */}
          {status === 'running' && (
            <div className="flex gap-1.5 mb-6">
              {PIPELINE_STEPS.map((step, idx) => (
                <div
                  key={step.id}
                  className="h-2 flex-1 rounded-full transition-all duration-300"
                  style={{
                    backgroundColor: idx < completedCount 
                      ? 'rgb(var(--primary-500))' 
                      : idx === completedCount 
                      ? 'rgb(var(--primary-300))'
                      : 'rgb(var(--surface-muted))'
                  }}
                />
              ))}
            </div>
          )}

          {/* Completed steps list */}
          {status === 'running' && progress.nodesCompleted.length > 0 && (
            <div className="mb-5 max-h-24 overflow-y-auto">
              <div className="flex flex-wrap gap-2">
                {progress.nodesCompleted.map((nodeId) => {
                  const step = PIPELINE_STEPS.find(s => s.id === nodeId)
                  return step ? (
                    <span 
                      key={nodeId}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium"
                      style={{ 
                        backgroundColor: 'rgb(var(--primary-50))',
                        color: 'rgb(var(--primary-700))'
                      }}
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <path d="M20 6L9 17L4 12" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                      {step.name}
                    </span>
                  ) : null
                })}
              </div>
            </div>
          )}

          {/* Error */}
          {status === 'error' && error && (
            <div 
              className="mb-5 p-4 rounded-2xl"
              style={{ backgroundColor: 'rgb(254 242 242)', border: '1px solid rgb(254 202 202)' }}
            >
              <p className="text-red-700 text-sm">{error}</p>
            </div>
          )}

          {/* Success */}
          {status === 'completed' && (
            <div 
              className="mb-5 p-4 rounded-2xl text-center"
              style={{ backgroundColor: 'rgb(240 253 244)', border: '1px solid rgb(187 247 208)' }}
            >
              <p className="text-green-700 font-medium text-sm">
                Your personalized room design is ready to explore!
              </p>
            </div>
          )}

          {/* Tip */}
          {status === 'running' && (
            <div 
              className="mb-5 p-4 rounded-2xl"
              style={{ backgroundColor: 'rgb(var(--surface-soft))' }}
            >
              <p className="text-xs" style={{ color: 'rgb(var(--text-muted))' }}>
                💡 AI is analyzing your room and selecting the perfect furniture for your style.
              </p>
            </div>
          )}

          {/* Buttons */}
          <div className="flex gap-3">
            {status === 'running' && (
              <button
                onClick={onAbort}
                className="flex-1 py-3 rounded-2xl font-medium transition-all hover:opacity-90"
                style={{ 
                  border: '1.5px solid rgb(var(--surface-muted))', 
                  color: 'rgb(var(--text-secondary))' 
                }}
              >
                Cancel
              </button>
            )}
            
            {status === 'error' && (
              <>
                <button
                  onClick={onClose}
                  className="flex-1 py-3 rounded-2xl font-medium transition-all"
                  style={{ border: '1.5px solid rgb(var(--surface-muted))', color: 'rgb(var(--text-secondary))' }}
                >
                  Close
                </button>
                <button
                  onClick={onRetry}
                  className="flex-1 py-3 rounded-2xl font-semibold text-white transition-all hover:opacity-90"
                  style={{ background: 'linear-gradient(135deg, rgb(var(--primary-500)), rgb(var(--primary-600)))' }}
                >
                  Try Again
                </button>
              </>
            )}
            
            {status === 'completed' && (
              <button
                onClick={onClose}
                className="flex-1 py-3.5 rounded-2xl font-semibold text-white transition-all hover:scale-[1.02] active:scale-[0.98]"
                style={{ background: 'linear-gradient(135deg, rgb(var(--primary-500)), rgb(var(--primary-600)))' }}
              >
                View Your Design ✨
              </button>
            )}

            {status === 'uploading' && (
              <div className="flex-1 py-3.5 rounded-2xl font-semibold text-center"
                   style={{ color: 'rgb(var(--text-muted))' }}>
                Uploading...
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default PipelineProgressModal
