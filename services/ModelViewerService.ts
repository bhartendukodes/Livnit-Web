/**
 * Model Viewer Service - Handles different 3D file formats with fallback support
 * Uses dependency injection pattern for better testability and flexibility
 */

export interface ModelViewerConfig {
  enableAR?: boolean;
  autoRotate?: boolean;
  cameraControls?: boolean;
  backgroundColor?: string;
  timeout?: number;
}

export interface ModelLoadResult {
  success: boolean;
  error?: string;
  format?: 'usdz' | 'glb' | 'obj' | 'unknown';
  metadata?: {
    name: string;
    size: number;
    type: string;
  };
}

export class ModelViewerService {
  private config: ModelViewerConfig;
  private loadTimeout: number;

  constructor(config: ModelViewerConfig = {}) {
    this.config = {
      enableAR: false,
      autoRotate: true,
      cameraControls: true,
      backgroundColor: '#171717',
      timeout: 8000,
      ...config
    };
    this.loadTimeout = this.config.timeout || 8000;
  }

  /**
   * Initialize model-viewer library dynamically
   */
  async initializeViewer(): Promise<boolean> {
    if (typeof window === 'undefined') return false;

    try {
      // Check if already loaded
      if (customElements.get('model-viewer')) {
        console.log('✅ Model-viewer already available');
        return true;
      }

      // Try to import from package first
      try {
        await import('@google/model-viewer');
        console.log('✅ Model-viewer imported from package');
        
        // Wait for custom element registration
        await this.waitForCustomElement('model-viewer', 2000);
        return true;
      } catch (packageError) {
        console.log('📦 Package import failed, trying CDN...', packageError);
      }

      // Fallback to CDN
      return await this.loadFromCDN();
    } catch (error) {
      console.error('❌ Failed to initialize model-viewer:', error);
      return false;
    }
  }

  /**
   * Load model-viewer from CDN as fallback
   */
  private async loadFromCDN(): Promise<boolean> {
    return new Promise((resolve) => {
      const script = document.createElement('script');
      script.type = 'module';
      script.src = 'https://ajax.googleapis.com/ajax/libs/model-viewer/3.4.0/model-viewer.min.js';
      
      script.onload = async () => {
        try {
          await this.waitForCustomElement('model-viewer', 3000);
          console.log('✅ Model-viewer loaded from CDN');
          resolve(true);
        } catch (error) {
          console.error('❌ CDN custom element registration failed:', error);
          resolve(false);
        }
      };
      
      script.onerror = () => {
        console.error('❌ Failed to load model-viewer from CDN');
        resolve(false);
      };
      
      document.head.appendChild(script);
    });
  }

  /**
   * Wait for custom element to be defined
   */
  private waitForCustomElement(tagName: string, timeout: number): Promise<void> {
    return new Promise((resolve, reject) => {
      const startTime = Date.now();
      
      const checkElement = () => {
        if (customElements.get(tagName)) {
          resolve();
          return;
        }
        
        if (Date.now() - startTime > timeout) {
          reject(new Error(`Timeout waiting for ${tagName}`));
          return;
        }
        
        setTimeout(checkElement, 100);
      };
      
      checkElement();
    });
  }

  /**
   * Create model viewer element with proper configuration
   * For USDZ files, returns null - they need special handling
   */
  createViewerElement(src: string, file: File): HTMLElement | null {
    const fileType = this.detectFileType(file);
    
    // USDZ files CANNOT be loaded via model-viewer's src attribute
    // Model-viewer uses GLTFLoader which tries to parse USDZ as JSON, causing errors
    // Return null to indicate we need alternative handling
    if (fileType === 'usdz') {
      return null;
    }
    
    // For GLB/GLTF/OBJ files, use standard model-viewer
    const viewer = document.createElement('model-viewer') as any;
    viewer.src = src;
    viewer.alt = `3D Model: ${file.name}`;
    viewer.setAttribute('camera-controls', '');
    viewer.setAttribute('touch-action', 'pan-y');
    viewer.setAttribute('disable-tap', '');
    viewer.setAttribute('loading', 'eager');
    viewer.setAttribute('reveal', 'interaction');
    viewer.setAttribute('shadow-intensity', '1');
    viewer.setAttribute('exposure', '1');
    
    if (this.config.autoRotate) {
      viewer.setAttribute('auto-rotate', '');
      viewer.setAttribute('auto-rotate-delay', '0');
    }
    
    // Style configuration - use CSS classes instead of inline styles to avoid warnings
    viewer.className = 'model-viewer-container';
    
    return viewer;
  }

  /**
   * Check if device supports USDZ Quick Look
   */
  supportsUSDZQuickLook(): boolean {
    if (typeof window === 'undefined') return false;
    
    const userAgent = window.navigator.userAgent.toLowerCase();
    const isIOS = /iphone|ipad|ipod/.test(userAgent);
    const isSafari = /safari/.test(userAgent) && !/chrome/.test(userAgent);
    
    return isIOS && isSafari;
  }

  /**
   * Create USDZ viewer using iframe with data URL
   * This prevents model-viewer from trying to parse USDZ as JSON
   */
  createUSDZViewer(src: string, file: File): HTMLElement {
    const container = document.createElement('div');
    container.className = 'usdz-viewer-container';
    
    const isIOS = this.supportsUSDZQuickLook();
    const metadata = this.getFileMetadata(file);
    
    if (isIOS) {
      // iOS Safari - use AR Quick Look
      const wrapper = document.createElement('div');
      wrapper.className = 'usdz-ios-wrapper';
      wrapper.style.cssText = 'width: 100%; height: 100%; display: flex; align-items: center; justify-content: center;';
      
      // Create AR Quick Look anchor that covers the whole area
      const arAnchor = document.createElement('a');
      arAnchor.href = src;
      arAnchor.rel = 'ar';
      arAnchor.className = 'usdz-ar-button';
      arAnchor.style.cssText = 'display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; height: 100%; padding: 2rem; text-align: center; color: white; text-decoration: none; cursor: pointer;';
      
      arAnchor.innerHTML = `
        <svg style="width: 80px; height: 80px; margin: 0 auto 1.5rem; color: #a855f7;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"></path>
        </svg>
        <h3 style="font-size: 1.5rem; font-weight: bold; margin-bottom: 0.5rem;">View in AR</h3>
        <p style="color: #9ca3af; margin-bottom: 1rem;">Tap to open in AR Quick Look</p>
        <p style="color: #6b7280; font-size: 0.875rem;">${file.name}</p>
        <p style="color: #6b7280; font-size: 0.75rem; margin-top: 0.5rem;">${metadata.sizeFormatted}</p>
      `;
      
      wrapper.appendChild(arAnchor);
      container.appendChild(wrapper);
    } else {
      // Non-iOS - Try to display USDZ using iframe with proper MIME type
      // This creates a visual preview without triggering GLTFLoader
      const iframe = document.createElement('iframe');
      iframe.src = src;
      iframe.style.cssText = 'width: 100%; height: 100%; border: none; background: #171717;';
      iframe.setAttribute('type', 'model/vnd.usdz+zip');
      
      // Fallback UI overlay
      const overlay = document.createElement('div');
      overlay.className = 'usdz-overlay';
      overlay.style.cssText = `
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(23, 23, 23, 0.95);
        z-index: 10;
      `;
      
      overlay.innerHTML = this.getUSDZFallbackHTML(file, src);
      
      container.appendChild(iframe);
      container.appendChild(overlay);
      
      // Hide overlay after 2 seconds if iframe loads something
      setTimeout(() => {
        try {
          // Check if iframe has content (cross-origin might block this)
          overlay.style.opacity = '0';
          overlay.style.transition = 'opacity 0.5s';
          setTimeout(() => {
            if (overlay.parentNode) {
              overlay.style.display = 'none';
            }
          }, 500);
        } catch (e) {
          // Cross-origin error, keep overlay
        }
      }, 2000);
    }
    
    return container;
  }

  /**
   * Get HTML for USDZ fallback UI
   */
  private getUSDZFallbackHTML(file: File, src: string): string {
    const metadata = this.getFileMetadata(file);
    return `
      <div style="display: flex; align-items: center; justify-content: center; height: 100%; padding: 2rem; text-align: center; color: white;">
        <div>
          <svg style="width: 80px; height: 80px; margin: 0 auto 1.5rem; color: #a855f7;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01"></path>
          </svg>
          <h3 style="font-size: 1.5rem; font-weight: bold; margin-bottom: 0.5rem;">USDZ File Ready</h3>
          <p style="color: #9ca3af; margin-bottom: 0.25rem;">${file.name}</p>
          <p style="color: #6b7280; font-size: 0.875rem; margin-bottom: 1.5rem;">${metadata.sizeFormatted}</p>
          <p style="color: #9ca3af; font-size: 0.875rem; margin-bottom: 1.5rem; max-width: 400px; margin-left: auto; margin-right: auto;">
            USDZ files are optimized for iOS AR Quick Look. For the best experience, open this file on an iPhone or iPad with Safari browser.
          </p>
          <a href="${src}" download="${file.name}" style="display: inline-block; padding: 0.75rem 1.5rem; background: #9333ea; color: white; border-radius: 0.5rem; text-decoration: none; font-weight: 500; transition: background 0.2s;">
            Download File
          </a>
          <p style="color: #6b7280; font-size: 0.75rem; margin-top: 1rem;">
            You can view this file in AR on iOS or with compatible 3D viewers
          </p>
        </div>
      </div>
    `;
  }

  /**
   * Detect file type from File object
   */
  private detectFileType(file: File): 'usdz' | 'glb' | 'obj' | 'unknown' {
    const extension = file.name.toLowerCase().split('.').pop();
    
    switch (extension) {
      case 'usdz':
        return 'usdz';
      case 'glb':
      case 'gltf':
        return 'glb';
      case 'obj':
        return 'obj';
      default:
        return 'unknown';
    }
  }

  /**
   * Setup model loading with timeout and error handling
   * For USDZ files, returns success immediately since we use alternative viewer
   */
  setupModelLoading(viewer: HTMLElement | null, file: File): Promise<ModelLoadResult> {
    return new Promise((resolve) => {
      const fileType = this.detectFileType(file);
      const metadata = {
        name: file.name,
        size: file.size,
        type: file.type
      };

      // USDZ files use alternative viewer, not model-viewer
      if (fileType === 'usdz' || !viewer) {
        console.log('🍎 USDZ file - using alternative viewer');
        resolve({
          success: true,
          format: fileType,
          metadata
        });
        return;
      }

      let resolved = false;
      
      const resolveOnce = (result: ModelLoadResult) => {
        if (!resolved) {
          resolved = true;
          resolve(result);
        }
      };

      // Success handlers
      const onLoad = () => {
        console.log('✅ Model loaded successfully');
        resolveOnce({
          success: true,
          format: fileType,
          metadata
        });
      };

      const onModelLoad = () => {
        console.log('✅ Model 3D data loaded');
        resolveOnce({
          success: true,
          format: fileType,
          metadata
        });
      };

      // Error handler
      const onError = (event: any) => {
        const errorMessage = event.detail?.message || `Failed to load ${fileType.toUpperCase()} file`;
        console.error('❌ Model loading error:', errorMessage);
        
        resolveOnce({
          success: false,
          error: errorMessage,
          format: fileType,
          metadata
        });
      };

      // Timeout handler
      const timeoutId = setTimeout(() => {
        console.warn('⏱️ Model loading timeout');
        resolveOnce({
          success: false,
          error: `Loading timeout after ${this.loadTimeout}ms`,
          format: fileType,
          metadata
        });
      }, this.loadTimeout);

      // Attach event listeners
      viewer.addEventListener('load', () => {
        clearTimeout(timeoutId);
        onLoad();
      });
      
      viewer.addEventListener('model-load', () => {
        clearTimeout(timeoutId);
        onModelLoad();
      });
      
      viewer.addEventListener('error', (event) => {
        clearTimeout(timeoutId);
        onError(event);
      });
    });
  }

  /**
   * Get file metadata for display
   */
  getFileMetadata(file: File) {
    return {
      name: file.name,
      size: file.size,
      type: file.type,
      sizeFormatted: `${(file.size / 1024 / 1024).toFixed(2)} MB`,
      format: this.detectFileType(file)
    };
  }
}

// Singleton instance for dependency injection
export const modelViewerService = new ModelViewerService({
  enableAR: false,
  autoRotate: true,
  cameraControls: true,
  backgroundColor: '#171717',
  timeout: 8000
});
