interface LoadingStateProps {
  label: string
  as?: 'div' | 'main'
  id?: string
  className?: string
}

export function LoadingState({ label, as = 'div', id, className = 'feature-loading' }: LoadingStateProps) {
  const Component = as

  return (
    <Component id={id} className={className} aria-label={label}>
      <span className="spinner" />
    </Component>
  )
}
