'use client'

import React, { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { USDLoader } from 'three/addons/loaders/USDLoader.js'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'

interface ThreeJSUSDZViewerProps {
  usdzBlob: Blob
}

const ThreeJSUSDZViewer: React.FC<ThreeJSUSDZViewerProps> = ({ usdzBlob }) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const sceneRef = useRef<THREE.Scene | null>(null)
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null)
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null)
  const controlsRef = useRef<OrbitControls | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isLoaded, setIsLoaded] = useState(false)
  const [objectUrl, setObjectUrl] = useState<string>('')

  // Create object URL from blob
  useEffect(() => {
    if (usdzBlob && usdzBlob.size > 0) {
      const url = URL.createObjectURL(usdzBlob)
      setObjectUrl(url)
      console.log('🔗 ThreeJSUSDZViewer: Object URL created, size:', (usdzBlob.size / 1024 / 1024).toFixed(1), 'MB')
      
      return () => {
        URL.revokeObjectURL(url)
      }
    }
  }, [usdzBlob])

  // Initialize Three.js scene and load USDZ
  useEffect(() => {
    if (!objectUrl || !containerRef.current) {
      return
    }

    // Capture container ref for cleanup
    const container = containerRef.current

    console.log('🎬 ThreeJSUSDZViewer: Initializing Three.js scene...')
    setIsLoading(true)
    setError(null)

    // Scene setup
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x1f2937) // gray-900
    sceneRef.current = scene

    // Camera setup
    const camera = new THREE.PerspectiveCamera(
      75,
      container.clientWidth / container.clientHeight,
      0.1,
      1000
    )
    camera.position.set(0, 0, 5)
    cameraRef.current = camera

    // Renderer setup
    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setSize(container.clientWidth, container.clientHeight)
    renderer.setPixelRatio(window.devicePixelRatio)
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    container.appendChild(renderer.domElement)
    rendererRef.current = renderer

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6)
    scene.add(ambientLight)

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8)
    directionalLight.position.set(5, 5, 5)
    directionalLight.castShadow = true
    scene.add(directionalLight)

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.05
    controls.minDistance = 1
    controls.maxDistance = 20
    controlsRef.current = controls

    // Load USDZ model (USDLoader supports USDZ files)
    const loader = new USDLoader()
    
    loader.loadAsync(objectUrl)
      .then((group) => {
        console.log('✅ ThreeJSUSDZViewer: USDZ loaded successfully!', group)
        
        // Add model to scene
        scene.add(group)

        // Calculate bounding box and center camera
        const box = new THREE.Box3().setFromObject(group)
        const center = box.getCenter(new THREE.Vector3())
        const size = box.getSize(new THREE.Vector3())
        
        // Center the model
        group.position.sub(center)
        
        // Adjust camera to fit model
        const maxDim = Math.max(size.x, size.y, size.z)
        const fov = camera.fov * (Math.PI / 180)
        let cameraZ = Math.abs(maxDim / 2 / Math.tan(fov / 2))
        cameraZ *= 1.5 // Add some padding
        camera.position.set(0, 0, cameraZ)
        camera.lookAt(0, 0, 0)
        
        controls.target.set(0, 0, 0)
        controls.update()

        setIsLoading(false)
        setIsLoaded(true)
      })
      .catch((err) => {
        console.error('❌ ThreeJSUSDZViewer: Failed to load USDZ:', err)
        setError(err.message || 'Failed to load USDZ file. USDZ files may need to be in USDA format for web preview.')
        setIsLoading(false)
        setIsLoaded(false)
      })

    // Animation loop
    const animate = () => {
      requestAnimationFrame(animate)
      if (controlsRef.current) {
        controlsRef.current.update()
      }
      if (rendererRef.current && sceneRef.current && cameraRef.current) {
        rendererRef.current.render(sceneRef.current, cameraRef.current)
      }
    }
    animate()

    // Handle resize
    const handleResize = () => {
      if (!container || !cameraRef.current || !rendererRef.current) return
      
      cameraRef.current.aspect = container.clientWidth / container.clientHeight
      cameraRef.current.updateProjectionMatrix()
      rendererRef.current.setSize(container.clientWidth, container.clientHeight)
    }
    window.addEventListener('resize', handleResize)

    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize)
      
      // Dispose of Three.js resources
      if (rendererRef.current) {
        rendererRef.current.dispose()
        if (container && rendererRef.current.domElement.parentNode) {
          container.removeChild(rendererRef.current.domElement)
        }
      }
      
      if (controlsRef.current) {
        controlsRef.current.dispose()
      }
      
      // Dispose of scene objects
      if (sceneRef.current) {
        sceneRef.current.traverse((object) => {
          if (object instanceof THREE.Mesh) {
            object.geometry?.dispose()
            if (Array.isArray(object.material)) {
              object.material.forEach(material => material.dispose())
            } else {
              object.material?.dispose()
            }
          }
        })
      }
    }
  }, [objectUrl])

  if (!objectUrl) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gray-900 rounded-lg">
        <div className="text-white">Preparing USDZ viewer...</div>
      </div>
    )
  }

  return (
    <div className="relative w-full h-full bg-gray-900 rounded-lg overflow-hidden">
      <div 
        ref={containerRef}
        className="w-full h-full"
        style={{
          minHeight: '400px',
          backgroundColor: '#1f2937'
        }}
      />
      
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-900/80 z-10">
          <div className="text-center text-white">
            <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
            <p className="text-sm">Loading 3D model...</p>
            <p className="text-xs text-gray-400 mt-2">This may take a moment for large files</p>
          </div>
        </div>
      )}

      {isLoaded && !error && (
        <div className="absolute bottom-4 right-4 bg-black/70 text-white px-3 py-2 rounded-lg text-sm z-30">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span>3D Model Loaded</span>
          </div>
          <p className="text-xs text-gray-400 mt-1">Drag to rotate • Scroll to zoom</p>
        </div>
      )}

      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-900/90 z-10">
          <div className="text-center p-6 max-w-md">
            <div className="mb-4">
              <svg className="w-16 h-16 mx-auto text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.732 15.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
            <h3 className="text-xl font-bold text-white mb-2">USDZ Preview Limited</h3>
            <p className="text-gray-400 text-sm mb-4">{error}</p>
            <p className="text-gray-500 text-xs mb-4">
              USDZ files work best on iOS Safari with AR Quick Look. For web preview, the file needs to be in USDA format.
            </p>
            
            {/* AR Quick Look for iOS/macOS Safari */}
            {typeof window !== 'undefined' && /iPhone|iPad|iPod|Macintosh/.test(navigator.userAgent) && (
              <a
                href={objectUrl}
                rel="ar"
                className="inline-block px-6 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors mb-3"
              >
                🍎 Open in AR Quick Look
              </a>
            )}
            
            <a
              href={objectUrl}
              download="room.usdz"
              className="inline-block px-6 py-3 bg-gray-600 hover:bg-gray-700 text-white rounded-lg font-medium transition-colors"
            >
              Download USDZ File
            </a>
          </div>
        </div>
      )}
    </div>
  )
}

export default ThreeJSUSDZViewer
