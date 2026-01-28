declare namespace JSX {
  interface IntrinsicElements {
    'model-viewer': React.DetailedHTMLProps<
      React.AllHTMLAttributes<HTMLElement> & {
        src?: string
        alt?: string
        'ios-src'?: string
        'auto-rotate'?: boolean
        'camera-controls'?: boolean
        'shadow-intensity'?: string
        'touch-action'?: string
        'interaction-policy'?: string
        'loading'?: string
        'reveal'?: string
        onLoad?: (event: any) => void
        onError?: (event: any) => void
        onModelLoad?: (event: any) => void
      },
      HTMLElement
    >
  }
}
