'use client'

import React from 'react'
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

const PipelineProgressModal: React.FC<PipelineProgressModalProps> = ({
  isOpen,
  status,
  progress,
  error,
  onClose,
  onRetry,
  onAbort
}) => {
  if (!isOpen) return null

  // Map technical node names to user-friendly names
  const getDisplayNodeName = (technicalName: string): string => {
    const nodeNameMap: Record<string, string> = {
      'extract_room': 'Analyzing Your Space',
      'select_assets': 'Curating Your Furniture', 
      'validate_and_cost': 'Confirming Availability & Pricing',
      'initial_layout': 'Drafting Your First Layout',
      'layout_preview': 'Reviewing Your First Preview',
      'refine_layout': 'Refining the Layout',
      'layout_preview_refine': 'Reviewing Final Updates',
      'layoutvlm': 'Finalizing & Rendering',
      'layout_preview_post': 'Your Design Reveal'
    }
    
    return nodeNameMap[technicalName] || technicalName.replace(/_/g, ' ')
  }

  const getStatusMessage = () => {
    switch (status) {
      case 'uploading':
        return 'Uploading USDZ file...'
      case 'running':
        return progress.currentNode 
          ? getDisplayNodeName(progress.currentNode)
          : 'Starting pipeline...'
      case 'completed':
        return 'Pipeline completed successfully!'
      case 'error':
        return 'Pipeline failed'
      case 'aborted':
        return 'Pipeline was aborted'
      default:
        return 'Initializing...'
    }
  }

  const getProgressPercentage = () => {
    if (status === 'completed') return 100
    if (status === 'error' || status === 'aborted') return 0
    if (!progress.totalNodes) return 0
    
    const nodesCompleted = progress.nodesCompleted.length
    const currentNodeProgress = progress.nodeProgress 
      ? (progress.nodeProgress.current / progress.nodeProgress.total)
      : 0
    
    return Math.round(((nodesCompleted + currentNodeProgress) / progress.totalNodes) * 100)
  }

  const formatElapsedTime = (elapsed?: number) => {
    if (!elapsed) return ''
    return `${Math.floor(elapsed / 60)}:${(elapsed % 60).toString().padStart(2, '0')}`
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-[9999]">
      <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-lg w-full mx-4">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-bold text-gray-900">
            {status === 'uploading' ? 'Uploading' : 'Generating Design'}
          </h2>
          {(status === 'completed' || status === 'error') && (
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <path
                  d="M18 6L6 18M6 6L18 18"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          )}
        </div>

        {/* Progress Bar */}
        <div className="mb-6">
          <div className="flex justify-between text-sm text-gray-600 mb-2">
            <span>{getStatusMessage()}</span>
            <span>{getProgressPercentage()}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-3">
            <div 
              className={`h-3 rounded-full transition-all duration-300 ${
                status === 'error' ? 'bg-red-500' : 
                status === 'completed' ? 'bg-green-500' : 
                'bg-purple-600'
              }`}
              style={{ width: `${getProgressPercentage()}%` }}
            />
          </div>
        </div>

        {/* Current Node Info */}
        {status === 'running' && progress.currentNode && (
          <div className="mb-4 p-4 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-3">
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-purple-600"></div>
              <div>
                <p className="font-medium text-gray-900">
                  {getDisplayNodeName(progress.currentNode)}
                </p>
                {progress.nodeProgress && (
                  <p className="text-sm text-gray-600">
                    {progress.nodeProgress.current} of {progress.nodeProgress.total}
                  </p>
                )}
                {progress.elapsedTime && (
                  <p className="text-xs text-gray-500">
                    Elapsed: {formatElapsedTime(progress.elapsedTime)}
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Completed Nodes */}
        {progress.nodesCompleted.length > 0 && (
          <div className="mb-4">
            <p className="text-sm font-medium text-gray-700 mb-2">Completed Steps:</p>
            <div className="space-y-1">
              {progress.nodesCompleted.map((node, index) => (
                <div key={index} className="flex items-center gap-2 text-sm text-green-600">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                    <path
                      d="M20 6L9 17L4 12"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  <span>{getDisplayNodeName(node)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Error Display */}
        {status === 'error' && error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-800 text-sm">{error}</p>
          </div>
        )}

        {/* Success Message */}
        {status === 'completed' && (
          <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
            <p className="text-green-800 text-sm font-medium">
              Design generation completed! Your room is ready to view.
            </p>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-4">
          {status === 'running' && (
            <button
              onClick={onAbort}
              className="flex-1 px-4 py-2 border-2 border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium"
            >
              Cancel
            </button>
          )}
          
          {status === 'error' && (
            <>
              <button
                onClick={onClose}
                className="flex-1 px-4 py-2 border-2 border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium"
              >
                Close
              </button>
              <button
                onClick={onRetry}
                className="flex-1 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors font-medium"
              >
                Retry
              </button>
            </>
          )}
          
          {status === 'completed' && (
            <button
              onClick={onClose}
              className="flex-1 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors font-medium"
            >
              View Results
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default PipelineProgressModal