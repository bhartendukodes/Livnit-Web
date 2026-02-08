'use client'

import React, { useEffect, useRef, useState, useCallback } from 'react'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

interface SimpleGLBViewerProps {
  file: Blob | File
  onLoadComplete?: () => void
  onError?: () => void
  className?: string
  style?: React.CSSProperties
}

const SimpleGLBViewer: React.FC<SimpleGLBViewerProps> = ({
  file,
  onLoadComplete,
  onError,
  className = '',
  style = {}
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const sceneRef = useRef<THREE.Scene>()
  const rendererRef = useRef<THREE.WebGLRenderer>()
  const cameraRef = useRef<THREE.PerspectiveCamera>()
  const controlsRef = useRef<OrbitControls>()
  const animationFrameRef = useRef<number>()

  const [objectUrl, setObjectUrl] = useState<string>('')
  const [isLoading, setIsLoading] = useState(true)
  const [isLoaded, setIsLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isWebGLSupported, setIsWebGLSupported] = useState(true)

  // Check WebGL support
  useEffect(() => {
    const canvas = document.createElement('canvas')
    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl')
    setIsWebGLSupported(!!gl)
  }, [])

  // Create object URL and reset load state when file changes (e.g. new design after iteration)
  useEffect(() => {
    if (file) {
      console.log('📦 SimpleGLBViewer: Creating object URL for file size:', file.size, 'bytes')
      setIsLoaded(false)
      setIsLoading(true)
      const url = URL.createObjectURL(file)
      console.log('✅ SimpleGLBViewer: Object URL created:', url.substring(0, 50))
      setObjectUrl(url)
      return () => {
        console.log('🧹 SimpleGLBViewer: Revoking object URL')
        URL.revokeObjectURL(url)
      }
    } else {
      console.warn('⚠️ SimpleGLBViewer: No file provided')
    }
  }, [file])

  // Initialize Three.js scene
  const initScene = useCallback(() => {
    console.log('📐 [initScene] Starting scene initialization...')
    
    if (!containerRef.current) {
      console.error('❌ [initScene] No container ref available')
      return
    }
    
    if (!isWebGLSupported) {
      console.error('❌ [initScene] WebGL not supported')
      return
    }

    const container = containerRef.current
    const width = container.clientWidth
    const height = container.clientHeight
    
    console.log('📐 [initScene] Container dimensions:', { width, height })

    // Scene
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0xf8fafc) // Light blue-gray background
    sceneRef.current = scene
    console.log('✅ [initScene] Scene created')

    // Camera
    const camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 1000)
    camera.position.set(0, 0, 5)
    cameraRef.current = camera
    console.log('✅ [initScene] Camera created and positioned')

    // Renderer
    const renderer = new THREE.WebGLRenderer({ 
      antialias: true,
      alpha: false,
      powerPreference: 'high-performance'
    })
    renderer.setSize(width, height)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)) // Limit pixel ratio for performance
    renderer.shadowMap.enabled = false // Disable shadows for better performance on large models
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.0
    renderer.outputColorSpace = THREE.SRGBColorSpace
    
    // Ensure canvas is visible
    renderer.domElement.style.display = 'block'
    renderer.domElement.style.width = '100%'
    renderer.domElement.style.height = '100%'
    renderer.domElement.style.position = 'absolute'
    renderer.domElement.style.top = '0'
    renderer.domElement.style.left = '0'
    
    container.appendChild(renderer.domElement)
    rendererRef.current = renderer
    console.log('✅ [initScene] Renderer created and added to DOM')
    console.log('📐 [initScene] Canvas dimensions:', {
      width: renderer.domElement.width,
      height: renderer.domElement.height,
      style: renderer.domElement.style.cssText
    })

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.05
    controls.minDistance = 0.1
    controls.maxDistance = 100
    controlsRef.current = controls
    console.log('✅ [initScene] Controls created')

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6)
    scene.add(ambientLight)

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8)
    directionalLight.position.set(5, 5, 5)
    directionalLight.castShadow = false // Disable shadows for performance
    scene.add(directionalLight)

    const fillLight = new THREE.DirectionalLight(0xffffff, 0.3)
    fillLight.position.set(-5, 0, 5)
    scene.add(fillLight)
    
    console.log('✅ [initScene] Scene fully initialized with lighting')
  }, [isWebGLSupported])

  // Auto-frame model: center in view (no tight fit/crop)
  const autoFrameModel = useCallback((model: THREE.Group) => {
    if (!cameraRef.current || !controlsRef.current) return

    const box = new THREE.Box3().setFromObject(model)
    const center = box.getCenter(new THREE.Vector3())
    const size = box.getSize(new THREE.Vector3())

    if (size.length() === 0) return

    // Center model at origin so it sits in the middle of the view
    model.position.sub(center)

    // Camera distance: enough to see full model with padding (no crop)
    const maxDim = Math.max(size.x, size.y, size.z)
    const fov = cameraRef.current.fov * (Math.PI / 180)
    let cameraZ = Math.abs(maxDim / 2 / Math.tan(fov / 2))
    cameraZ *= 2.0 // Extra padding so model is centered and fully visible, not fit-cropped

    // Camera straight in front of center (model centered in frame)
    cameraRef.current.position.set(0, 0, cameraZ)
    cameraRef.current.lookAt(0, 0, 0)

    controlsRef.current.target.set(0, 0, 0)
    controlsRef.current.update()

    console.log('📐 Model auto-framed (centered), camera at:', cameraRef.current.position)
  }, [])

  // Load GLB model
  const loadModel = useCallback(async () => {
    console.log('📥 [loadModel] Starting GLB model loading...')
    
    if (!objectUrl) {
      console.error('❌ [loadModel] No objectUrl available')
      return
    }
    
    if (!sceneRef.current) {
      console.error('❌ [loadModel] Scene not initialized yet')
      return
    }

    console.log('📥 [loadModel] Object URL:', objectUrl.substring(0, 50) + '...')
    setError(null)

    try {
      const loader = new GLTFLoader()
      const dracoLoader = new DRACOLoader()
      dracoLoader.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.6/')
      loader.setDRACOLoader(dracoLoader)
      console.log('✅ [loadModel] GLTFLoader created with DRACOLoader')

      try {
      // For large files (37MB), increase timeout to 60 seconds
      const fileSizeMB = file.size / 1024 / 1024
      const timeoutDuration = fileSizeMB > 30 ? 60000 : 30000
      console.log(`⏱️ [loadModel] Timeout set to ${timeoutDuration / 1000}s for ${fileSizeMB.toFixed(1)}MB file`)

      const gltf = await new Promise<any>((resolve, reject) => {
        const startTime = Date.now()
        const timeout = setTimeout(() => {
          const elapsed = ((Date.now() - startTime) / 1000).toFixed(1)
          console.error(`⏱️ [loadModel] GLB loading timeout after ${elapsed}s`)
          reject(new Error(`GLB loading timeout after ${timeoutDuration / 1000} seconds`))
        }, timeoutDuration)

        console.log('📥 [loadModel] Calling loader.load()...')
        loader.load(
          objectUrl,
          (gltf) => {
            const elapsed = ((Date.now() - startTime) / 1000).toFixed(1)
            console.log(`✅ [loadModel] GLTF loader success callback fired (${elapsed}s)`)
            clearTimeout(timeout)
            resolve(gltf)
          },
          (progress) => {
            if (progress.total > 0) {
              const percent = (progress.loaded / progress.total * 100).toFixed(1)
              const loadedMB = (progress.loaded / 1024 / 1024).toFixed(1)
              const totalMB = (progress.total / 1024 / 1024).toFixed(1)
              console.log(`📊 [loadModel] Progress: ${percent}% (${loadedMB}/${totalMB} MB)`)
            } else {
              console.log(`📊 [loadModel] Progress: ${(progress.loaded / 1024 / 1024).toFixed(1)} MB loaded`)
            }
          },
          (error) => {
            const elapsed = ((Date.now() - startTime) / 1000).toFixed(1)
            console.error(`❌ [loadModel] GLTF loader error callback (${elapsed}s):`, error)
            clearTimeout(timeout)
            reject(error)
          }
        )
      })

      console.log('✅ [loadModel] GLB loaded successfully, processing...')
      console.log('📊 [loadModel] GLTF data:', {
        scenes: gltf.scenes?.length || 0,
        animations: gltf.animations?.length || 0,
        cameras: gltf.cameras?.length || 0
      })

      // Add model to scene
      const model = gltf.scene
      console.log('📦 [loadModel] Adding model to scene...')
      sceneRef.current.add(model)
      console.log('✅ [loadModel] Model added to scene')

      // Auto-frame model
      console.log('📐 [loadModel] Auto-framing model...')
      autoFrameModel(model)
      console.log('✅ [loadModel] Model auto-framed')

      // Force multiple renders to ensure visibility
      if (rendererRef.current && sceneRef.current && cameraRef.current) {
        console.log('🎨 [loadModel] Forcing initial renders...')
        // Render multiple times to ensure it's visible
        for (let i = 0; i < 5; i++) {
          rendererRef.current.render(sceneRef.current, cameraRef.current)
        }
        console.log('✅ [loadModel] Initial renders complete')
        
        // Verify canvas is in DOM
        const canvas = rendererRef.current.domElement
        console.log('🔍 [loadModel] Canvas check:', {
          inDOM: canvas.parentNode === containerRef.current,
          visible: canvas.offsetWidth > 0 && canvas.offsetHeight > 0,
          width: canvas.width,
          height: canvas.height,
          style: window.getComputedStyle(canvas).display
        })
      }

      // Immediately hide loader
      console.log('🎯 [loadModel] Hiding loader and calling onLoadComplete...')
      setIsLoading(false)
      setIsLoaded(true)
      
      // Call onLoadComplete immediately - animation loop will keep rendering
      onLoadComplete?.()
      console.log('✅ [loadModel] Load complete - GLB should be visible now!')
      } finally {
        dracoLoader.dispose()
      }

    } catch (loadError) {
      console.error('❌ [loadModel] Failed to load GLB:', loadError)
      const errorMessage = loadError instanceof Error ? loadError.message : 'Unknown error'
      console.error('❌ [loadModel] Error details:', {
        message: errorMessage,
        stack: loadError instanceof Error ? loadError.stack : undefined,
        fileSize: (file.size / 1024 / 1024).toFixed(1) + ' MB'
      })
      setError(errorMessage)
      setIsLoading(false)
      onError?.()
    }
  }, [objectUrl, autoFrameModel, onLoadComplete, onError, file])

  // Animation loop - render continuously for smooth display
  const animate = useCallback(() => {
    if (!rendererRef.current || !sceneRef.current || !cameraRef.current) {
      console.warn('⚠️ [animate] Missing refs, stopping animation')
      return
    }

    animationFrameRef.current = requestAnimationFrame(animate)

    // Update controls
    if (controlsRef.current) {
      controlsRef.current.update()
    }

    try {
      rendererRef.current.render(sceneRef.current, cameraRef.current)
    } catch (e) {
      console.error('❌ [animate] Render error:', e)
    }
  }, [])

  // Handle resize
  const handleResize = useCallback(() => {
    if (!containerRef.current || !cameraRef.current || !rendererRef.current) return

    const width = containerRef.current.clientWidth
    const height = containerRef.current.clientHeight

    cameraRef.current.aspect = width / height
    cameraRef.current.updateProjectionMatrix()
    rendererRef.current.setSize(width, height)
  }, [])

  // Initialize everything - only once per objectUrl
  useEffect(() => {
    const container = containerRef.current
    console.log('🔄 [SimpleGLBViewer] useEffect triggered:', {
      hasObjectUrl: !!objectUrl,
      hasContainer: !!container,
      containerWidth: container?.clientWidth,
      containerHeight: container?.clientHeight,
      isLoaded,
      isLoading,
      fileSizeMB: (file.size / 1024 / 1024).toFixed(1)
    })
    
    // Only initialize if we have objectUrl, container, and haven't loaded yet
    if (objectUrl && container && !isLoaded) {
      console.log('🎬 [SimpleGLBViewer] Starting initialization sequence...')
      console.log('📦 [SimpleGLBViewer] File details:', {
        size: (file.size / 1024 / 1024).toFixed(1) + ' MB',
        type: file.type || 'unknown',
        hasName: 'name' in file
      })
      
      setIsLoading(true)
      setError(null)
      
      const initialize = async () => {
        try {
          console.log('📐 [SimpleGLBViewer] Step 1: Initializing scene...')
          initScene()
          
          console.log('📥 [SimpleGLBViewer] Step 2: Loading GLB model...')
          await loadModel()
          
          console.log('🎬 [SimpleGLBViewer] Step 3: Starting animation loop...')
          animate()
          
          console.log('✅ [SimpleGLBViewer] Initialization complete!')
        } catch (err) {
          console.error('❌ [SimpleGLBViewer] Initialization failed:', err)
          setError(err instanceof Error ? err.message : 'Initialization failed')
          setIsLoading(false)
          onError?.()
        }
      }
      
      initialize()
    } else {
      console.log('⏭️ [SimpleGLBViewer] Skipping initialization:', {
        reason: !objectUrl ? 'No objectUrl' : !container ? 'No container' : 'Already loaded'
      })
    }

    // Cleanup on unmount or when objectUrl changes (use container captured at effect run time)
    return () => {
      console.log('🧹 [SimpleGLBViewer] Cleanup triggered')
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
        animationFrameRef.current = undefined
      }
      if (rendererRef.current && container) {
        try {
          const domElement = rendererRef.current.domElement
          if (domElement && domElement.parentNode === container) {
            container.removeChild(domElement)
          }
          rendererRef.current.dispose()
          rendererRef.current = undefined
        } catch (e) {
          // Silently ignore cleanup errors - element might already be removed
        }
      }
      if (controlsRef.current) {
        controlsRef.current.dispose()
        controlsRef.current = undefined
      }
      if (sceneRef.current) {
        sceneRef.current.traverse((object) => {
          if ((object as THREE.Mesh).isMesh) {
            const mesh = object as THREE.Mesh
            mesh.geometry?.dispose()
            if (Array.isArray(mesh.material)) {
              mesh.material.forEach(m => m.dispose())
            } else {
              mesh.material?.dispose()
            }
          }
        })
        sceneRef.current = undefined
      }
    }
    // Intentionally run only when objectUrl changes; initScene/loadModel/animate are stable callbacks
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once per objectUrl, avoid re-run on isLoaded/isLoading
  }, [objectUrl])

  // Handle resize separately
  useEffect(() => {
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [handleResize])

  // WebGL not supported
  if (!isWebGLSupported) {
    return (
      <div className={`w-full h-full flex items-center justify-center bg-gray-100 ${className}`} style={style}>
        <div className="text-center p-8">
          <div className="text-red-500 text-2xl mb-4">⚠️</div>
          <h3 className="text-lg font-semibold mb-2">WebGL Not Supported</h3>
          <p className="text-gray-600">Your browser doesn&apos;t support WebGL required for 3D graphics.</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`relative w-full h-full ${className}`} style={style}>
      <div 
        ref={containerRef} 
        className="w-full h-full bg-gradient-to-br from-slate-50 to-slate-100 rounded-lg"
        style={{ minHeight: '400px', position: 'relative' }}
      />

      {/* Loading State */}
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-50 bg-opacity-95 z-10 rounded-lg">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500 mx-auto mb-4"></div>
            <div className="text-lg font-medium text-gray-800">Loading 3D Model</div>
            <div className="text-sm text-gray-600 mt-2">
              {'name' in file ? file.name : 'room.glb'} ({(file.size / 1024 / 1024).toFixed(1)} MB)
            </div>
          </div>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-50/95 z-10 rounded-lg p-4">
          <div className="text-center max-w-md p-5 rounded-2xl bg-white border border-red-200 shadow-sm">
            <div className="text-red-500 text-2xl mb-3">⚠️</div>
            <h3 className="text-base font-semibold mb-1 text-gray-800">Model couldn’t be loaded</h3>
            <p className="text-red-700 text-sm mb-3">{error}</p>
            <p className="text-xs text-gray-500">
              {'name' in file ? file.name : 'room.glb'} ({(file.size / 1024 / 1024).toFixed(1)} MB)
            </p>
            <p className="text-xs text-gray-500 mt-2">Try refreshing or generating the design again.</p>
          </div>
        </div>
      )}

    </div>
  )
}

export default SimpleGLBViewer