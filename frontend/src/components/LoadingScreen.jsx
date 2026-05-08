export default function LoadingScreen() {
  return (
    <div className="flex items-center justify-center h-screen">
      <div className="flex flex-col items-center gap-3">
        <div
          className="w-10 h-10 rounded-full border-4 border-t-transparent animate-spin"
          style={{ borderColor: 'var(--tg-theme-button-color, #2481cc)', borderTopColor: 'transparent' }}
        />
        <p className="text-sm" style={{ color: 'var(--tg-theme-hint-color, #888)' }}>
          Загрузка...
        </p>
      </div>
    </div>
  )
}
