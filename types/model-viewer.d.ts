declare namespace JSX {
  interface IntrinsicElements {
    'model-viewer': React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement> & {
      src?: string
      alt?: string
      'auto-rotate'?: boolean
      'camera-controls'?: boolean
      'touch-action'?: string
      'shadow-intensity'?: string
      exposure?: string
      'tone-mapping'?: string
      ar?: boolean
      'ar-modes'?: string
      'environment-image'?: string
      'skybox-image'?: string
      poster?: string
      loading?: string
      reveal?: string
      'animation-name'?: string
      'animation-crossfade-duration'?: string
      'auto-play'?: boolean
      style?: React.CSSProperties
      className?: string
    }
  }
}