'use client'

import React from 'react'
import AnimatedSection from './AnimatedSection'

const HeroSection: React.FC = () => {
  return (
    <div className="relative overflow-hidden py-20">
      {/* Background decorations */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute top-0 left-0 w-72 h-72 bg-primary-200 rounded-full opacity-20 animate-float" 
             style={{ backgroundColor: 'rgb(var(--primary-200))', animationDelay: '0s' }}></div>
        <div className="absolute top-20 right-0 w-96 h-96 bg-primary-300 rounded-full opacity-15 animate-float" 
             style={{ backgroundColor: 'rgb(var(--primary-300))', animationDelay: '2s' }}></div>
        <div className="absolute bottom-0 left-1/2 w-64 h-64 bg-primary-100 rounded-full opacity-25 animate-float" 
             style={{ backgroundColor: 'rgb(var(--primary-100))', animationDelay: '4s' }}></div>
      </div>

      <div className="max-w-4xl mx-auto text-center px-6">
        {/* Main Heading */}
        <AnimatedSection animation="slide-up" className="mb-8">
          <h1 className="text-6xl md:text-8xl font-bold leading-tight">
            <span className="text-gradient">Design Your</span>
            <br />
            <span className="text-gradient">Dream Space</span>
          </h1>
          <div className="mt-6 w-32 h-1 bg-gradient-to-r from-primary-400 to-primary-600 mx-auto rounded-full"
               style={{ background: `linear-gradient(to right, rgb(var(--primary-400)), rgb(var(--primary-600)))` }}></div>
        </AnimatedSection>

        {/* Subtitle */}
        <AnimatedSection animation="fade-in" delay={200} className="mb-12">
          <p className="text-xl md:text-2xl text-secondary leading-relaxed max-w-3xl mx-auto"
             style={{ color: 'rgb(var(--text-secondary))' }}>
            Transform your living space with AI-powered interior design. Upload your room layout and let 
            <span className="font-semibold text-primary-600" style={{ color: 'rgb(var(--primary-600))' }}> Livi </span>
            create personalized designs with real furniture and decor.
          </p>
        </AnimatedSection>

        {/* Stats */}
        <AnimatedSection animation="slide-up" delay={400}>
          <div className="grid grid-cols-3 gap-8 max-w-2xl mx-auto">
            {[
              { number: '12K+', label: 'Rooms Designed' },
              { number: '98%', label: 'Satisfaction Rate' },
              { number: '24/7', label: 'AI Available' }
            ].map((stat, index) => (
              <div key={index} className="group">
                <div className="text-4xl md:text-5xl font-bold text-primary-600 group-hover:scale-110 transition-transform duration-300"
                     style={{ color: 'rgb(var(--primary-600))' }}>
                  {stat.number}
                </div>
                <div className="text-sm md:text-base text-muted mt-2" style={{ color: 'rgb(var(--text-muted))' }}>
                  {stat.label}
                </div>
              </div>
            ))}
          </div>
        </AnimatedSection>

        {/* Trust indicators */}
        <AnimatedSection animation="fade-in" delay={600} className="mt-16">
          <div className="flex items-center justify-center gap-8 opacity-60">
            <div className="text-sm font-medium text-muted" style={{ color: 'rgb(var(--text-muted))' }}>
              TRUSTED BY DESIGNERS WORLDWIDE
            </div>
          </div>
        </AnimatedSection>
      </div>
    </div>
  )
}

export default HeroSection