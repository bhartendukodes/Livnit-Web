'use client'

import React, { useState } from 'react'
import { apiClient } from '@/services/ApiClient'

const ApiConnectionTest: React.FC = () => {
  const [testResult, setTestResult] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const testConnection = async () => {
    setIsLoading(true)
    setTestResult(null)
    
    try {
      console.log('🧪 Testing connection to hosted backend...')
      const health = await apiClient.health()
      console.log('✅ Health response:', health)
      setTestResult(`✅ Connected to hosted backend: ${JSON.stringify(health)}`)
    } catch (error: any) {
      console.error('❌ Connection test failed:', error)
      setTestResult(`❌ Connection failed: ${error.message}`)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="fixed bottom-4 right-4 bg-white border border-gray-300 rounded-lg shadow-lg p-4 max-w-sm z-40">
      <h3 className="font-medium text-gray-900 mb-2">Backend Connection</h3>
      
      <div className="text-sm text-gray-600 mb-3">
        <p>API URL: https://pipeline.livinit.ai</p>
      </div>
      
      <button
        onClick={testConnection}
        disabled={isLoading}
        className="w-full px-3 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50 text-sm"
      >
        {isLoading ? 'Testing...' : 'Test Connection'}
      </button>
      
      {testResult && (
        <div className={`mt-3 p-2 rounded text-xs ${
          testResult.startsWith('✅') 
            ? 'bg-green-100 text-green-800'
            : 'bg-red-100 text-red-800'
        }`}>
          {testResult}
        </div>
      )}
    </div>
  )
}

export default ApiConnectionTest