import { useEffect, useState } from 'react'
import { useStore } from './store'
import MenuPage from './pages/MenuPage'
import CartPage from './pages/CartPage'
import CabinetPage from './pages/CabinetPage'
import Navigation from './components/Navigation'
import LoadingScreen from './components/LoadingScreen'

export default function App() {
  const [ready, setReady] = useState(false)
  const [error, setError] = useState(null)
  const { activePage, fetchMenu, fetchCart } = useStore()

  useEffect(() => {
    const tg = window.Telegram?.WebApp
    if (!tg) {
      setError('Откройте приложение через Telegram')
      return
    }
    tg.ready()
    tg.expand()

    Promise.all([fetchMenu(), fetchCart()])
      .then(() => setReady(true))
      .catch(() => setError('Ошибка загрузки. Попробуйте позже.'))
  }, [])

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen text-center px-6">
        <p className="text-tg-hint text-sm">{error}</p>
      </div>
    )
  }

  if (!ready) return <LoadingScreen />

  return (
    <div className="flex flex-col h-screen bg-tg-bg">
      <main className="flex-1 overflow-y-auto pb-16">
        {activePage === 'menu'    && <MenuPage />}
        {activePage === 'cart'    && <CartPage />}
        {activePage === 'cabinet' && <CabinetPage />}
      </main>
      <Navigation />
    </div>
  )
}
