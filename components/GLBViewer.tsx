'use client'

import React, { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

interface GLBViewerProps {
  glbBlob: Blob | File
  previewImage?: string // Optional preview image from pipeline
  fileName?: string
}

const GLBViewer: React.FC<GLBViewerProps> = ({ 
  glbBlob, 
  previewImage,
  fileName = 'room.glb'
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const sceneRef = useRef<THREE.Scene>()
  const rendererRef = useRef<THREE.WebGLRenderer>()
  const cameraRef = useRef<THREE.PerspectiveCamera>()
  const controlsRef = useRef<OrbitControls>()
  
  const [objectUrl, setObjectUrl] = useState<string>('')
  const [isLoading, setIsLoading] = useState(true)
  const [isLoaded, setIsLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [previewImageUrl, setPreviewImageUrl] = useState<string>('')

  // Create object URL for GLB blob
  useEffect(() => {
    if (glbBlob) {
      const url = URL.createObjectURL(glbBlob)
      setObjectUrl(url)
      return () => URL.revokeObjectURL(url)
    }
  }, [glbBlob])

  // Create object URL for preview image
  useEffect(() => {
    if (previewImage) {
      setPreviewImageUrl(previewImage)
    }
  }, [previewImage])

  // Initialize Three.js scene and load GLB
  useEffect(() => {
    if (!objectUrl || !containerRef.current) {
      return
    }

    // Capture container ref for cleanup
    const container = containerRef.current

    console.log('🎬 GLBViewer: Initializing Three.js scene...')
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
    camera.position.set(0, 2, 5)
    cameraRef.current = camera

    // Renderer setup
    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setSize(container.clientWidth, container.clientHeight)
    renderer.setPixelRatio(window.devicePixelRatio)
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1
    container.appendChild(renderer.domElement)
    rendererRef.current = renderer

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6)
    scene.add(ambientLight)

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8)
    directionalLight.position.set(5, 5, 5)
    directionalLight.castShadow = true
    directionalLight.shadow.mapSize.width = 2048
    directionalLight.shadow.mapSize.height = 2048
    scene.add(directionalLight)

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.05
    controls.minDistance = 1
    controls.maxDistance = 20
    controlsRef.current = controls

    // Load GLB model
    const loader = new GLTFLoader()
    
    loader.load(
      objectUrl,
      (gltf) => {
        console.log('✅ GLBViewer: GLB loaded successfully!', gltf)
        
        // Add model to scene
        const model = gltf.scene
        scene.add(model)

        // Enable shadows
        model.traverse((child) => {
          if ((child as THREE.Mesh).isMesh) {
            child.castShadow = true
            child.receiveShadow = true
          }
        })

        // Calculate bounding box and center camera
        const box = new THREE.Box3().setFromObject(model)
        const center = box.getCenter(new THREE.Vector3())
        const size = box.getSize(new THREE.Vector3())
        
        // Center the model
        model.position.sub(center)
        
        // Adjust camera to fit model
        const maxDim = Math.max(size.x, size.y, size.z)
        const fov = camera.fov * (Math.PI / 180)
        let cameraZ = Math.abs(maxDim / 2 / Math.tan(fov / 2))
        cameraZ *= 1.5 // Add some padding
        camera.position.set(0, cameraZ * 0.5, cameraZ)
        camera.lookAt(0, 0, 0)
        
        controls.target.set(0, 0, 0)
        controls.update()

        setIsLoading(false)
        setIsLoaded(true)
      },
      (progress) => {
        console.log('📊 GLB loading progress:', (progress.loaded / progress.total * 100) + '%')
      },
      (error) => {
        console.error('❌ GLBViewer: Failed to load GLB:', error)
        setError(`Failed to load GLB file: ${error instanceof Error ? error.message : 'Unknown error'}`)
        setIsLoading(false)
      }
    )

    // Animation loop
    const animate = () => {
      requestAnimationFrame(animate)
      if (controls) controls.update()
      if (renderer && scene && camera) {
        renderer.render(scene, camera)
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

  if (error) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gray-900 text-white">
        <div className="text-center">
          <div className="text-red-400 text-lg mb-2">❌ GLB Load Error</div>
          <div className="text-sm text-gray-400 mb-4">{error}</div>
          <div className="text-xs text-gray-500">
            File: {fileName} | Size: {(glbBlob.size / 1024 / 1024).toFixed(2)} MB
          </div>
        </div>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gray-900 text-white">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mb-4"></div>
          <div className="text-lg">Loading 3D Model...</div>
          <div className="text-sm text-gray-400 mt-2">
            {fileName} ({(glbBlob.size / 1024 / 1024).toFixed(2)} MB)
          </div>
        </div>
      </div>
    )
  }

  return (
    <div 
      ref={containerRef} 
      className="w-full h-full bg-gray-900"
      style={{ minHeight: '400px' }}
    >
      {/* Loading overlay */}
      {!isLoaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-900 bg-opacity-90">
          <div className="text-white text-center">
            <div className="animate-pulse text-lg">Initializing 3D Viewer...</div>
          </div>
        </div>
      )}
    </div>
  )
}

export default GLBViewer