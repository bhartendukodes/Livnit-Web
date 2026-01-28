declare namespace JSX {
  interface IntrinsicElements {
    'model-viewer': React.DetailedHTMLProps<
      React.AllHTMLAttributes<HTMLElement> & {
        src?: string
        alt?: string
        ar?: boolean
        'ar-modes'?: string
        'camera-controls'?: boolean
        'auto-rotate'?: boolean
        'interaction-policy'?: string
        'exposure'?: string
        'shadow-intensity'?: string
        'environment-image'?: string
        'skybox-image'?: string
      },
      HTMLElement
    >
  }
}

