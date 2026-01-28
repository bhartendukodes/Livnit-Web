'use client'

import React, { useEffect, useRef, useState } from 'react'

interface AnimatedSectionProps {
  children: React.ReactNode
  animation?: 'slide-up' | 'slide-left' | 'slide-right' | 'fade-in' | 'scale-in'
  delay?: number
  className?: string
  threshold?: number
  triggerOnce?: boolean
}

const AnimatedSection: React.FC<AnimatedSectionProps> = ({
  children,
  animation = 'slide-up',
  delay = 0,
  className = '',
  threshold = 0.1,
  triggerOnce = true
}) => {
  const [isVisible, setIsVisible] = useState(false)
  const elementRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const element = elementRef.current
    if (!element) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setTimeout(() => {
            setIsVisible(true)
          }, delay)
          
          if (triggerOnce) {
            observer.unobserve(element)
          }
        } else if (!triggerOnce) {
          setIsVisible(false)
        }
      },
      {
        threshold,
        rootMargin: '50px 0px -50px 0px'
      }
    )

    observer.observe(element)

    return () => {
      observer.unobserve(element)
    }
  }, [delay, threshold, triggerOnce])

  const getAnimationClass = () => {
    switch (animation) {
      case 'slide-left':
        return 'animate-slide-left'
      case 'slide-right':
        return 'animate-slide-right'
      case 'fade-in':
        return 'animate-fade-in'
      case 'scale-in':
        return 'animate-scale-in'
      default:
        return 'animate-slide-up'
    }
  }

  return (
    <div
      ref={elementRef}
      className={`${className} ${
        isVisible ? getAnimationClass() : 'opacity-0'
      }`}
    >
      {children}
    </div>
  )
}

export default AnimatedSection