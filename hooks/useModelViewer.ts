/**
 * Custom hook for 3D model viewing with dependency injection
 * Handles USDZ and other 3D file formats with proper error handling
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { modelViewerService, ModelLoadResult, ModelViewerService } from '../services/ModelViewerService';

interface UseModelViewerOptions {
  service?: ModelViewerService;
  autoInit?: boolean;
}

interface UseModelViewerReturn {
  viewerRef: React.RefObject<HTMLDivElement>;
  isViewerReady: boolean;
  isModelLoaded: boolean;
  loadingState: 'idle' | 'initializing' | 'loading' | 'loaded' | 'error' | 'timeout';
  error: string | null;
  loadModel: (file: File) => Promise<ModelLoadResult>;
  metadata: any;
}

export function useModelViewer(options: UseModelViewerOptions = {}): UseModelViewerReturn {
  const { service = modelViewerService, autoInit = true } = options;
  
  const viewerRef = useRef<HTMLDivElement>(null);
  const modelViewerRef = useRef<HTMLElement | null>(null);
  const currentUrlRef = useRef<string | null>(null);
  
  const [isViewerReady, setIsViewerReady] = useState(false);
  const [isModelLoaded, setIsModelLoaded] = useState(false);
  const [loadingState, setLoadingState] = useState<'idle' | 'initializing' | 'loading' | 'loaded' | 'error' | 'timeout'>('idle');
  const [error, setError] = useState<string | null>(null);
  const [metadata, setMetadata] = useState<any>(null);

  // Initialize viewer service
  useEffect(() => {
    if (!autoInit) return;

    const initViewer = async () => {
      setLoadingState('initializing');
      console.log('🚀 Initializing model viewer service...');
      
      try {
        const success = await service.initializeViewer();
        if (success) {
          setIsViewerReady(true);
          setLoadingState('idle');
          console.log('✅ Model viewer service ready');
        } else {
          setError('Failed to initialize 3D viewer');
          setLoadingState('error');
          console.error('❌ Model viewer service initialization failed');
        }
      } catch (err) {
        setError('Viewer initialization error');
        setLoadingState('error');
        console.error('❌ Viewer initialization error:', err);
      }
    };

    initViewer();
  }, [service, autoInit]);

  // Load model function
  const loadModel = useCallback(async (file: File): Promise<ModelLoadResult> => {
    if (!isViewerReady) {
      const errorResult: ModelLoadResult = {
        success: false,
        error: 'Viewer not ready'
      };
      setError(errorResult.error || 'Unknown error');
      return errorResult;
    }

    if (!viewerRef.current) {
      const errorResult: ModelLoadResult = {
        success: false,
        error: 'Viewer container not found'
      };
      setError(errorResult.error || 'Unknown error');
      return errorResult;
    }

    try {
      setLoadingState('loading');
      setError(null);
      setIsModelLoaded(false);
      
      // Clean up previous model
      if (modelViewerRef.current) {
        viewerRef.current.removeChild(modelViewerRef.current);
        modelViewerRef.current = null;
      }
      
      if (currentUrlRef.current) {
        URL.revokeObjectURL(currentUrlRef.current);
        currentUrlRef.current = null;
      }

      // Create blob URL
      const url = URL.createObjectURL(file);
      currentUrlRef.current = url;
      
      // Get file metadata
      const fileMetadata = service.getFileMetadata(file);
      setMetadata(fileMetadata);
      
      console.log('📁 Loading file:', fileMetadata);

      // Create viewer element - returns null for USDZ files
      const viewerElement = service.createViewerElement(url, file);
      
      // Handle USDZ files with alternative viewer
      if (!viewerElement) {
        // USDZ file - use alternative viewer that doesn't trigger GLTFLoader
        const usdzViewer = service.createUSDZViewer(url, file);
        modelViewerRef.current = usdzViewer;
        viewerRef.current.appendChild(usdzViewer);
        
        // USDZ viewer doesn't use model-viewer, so return success immediately
        const result = await service.setupModelLoading(null, file);
        
        if (result.success) {
          setIsModelLoaded(true);
          setLoadingState('loaded');
          console.log('✅ USDZ viewer ready');
        } else {
          setError(result.error || 'Failed to setup USDZ viewer');
          setLoadingState('error');
        }
        
        return result;
      }
      
      // Standard 3D file (GLB, OBJ, etc.) - use model-viewer
      modelViewerRef.current = viewerElement;
      viewerRef.current.appendChild(viewerElement);

      // Setup loading with timeout and error handling
      const result = await service.setupModelLoading(viewerElement, file);
      
      if (result.success) {
        setIsModelLoaded(true);
        setLoadingState('loaded');
        console.log('✅ Model loaded successfully:', result);
      } else {
        setError(result.error || 'Failed to load model');
        setLoadingState('error');
        console.error('❌ Model loading failed:', result);
      }

      return result;
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(errorMsg);
      setLoadingState('error');
      
      const errorResult: ModelLoadResult = {
        success: false,
        error: errorMsg
      };
      
      console.error('❌ Model loading exception:', err);
      return errorResult;
    }
  }, [isViewerReady, service]);

  // Cleanup
  useEffect(() => {
    return () => {
      if (currentUrlRef.current) {
        URL.revokeObjectURL(currentUrlRef.current);
      }
    };
  }, []);

  return {
    viewerRef,
    isViewerReady,
    isModelLoaded,
    loadingState,
    error,
    loadModel,
    metadata
  };
}
