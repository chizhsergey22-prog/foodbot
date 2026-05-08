import { useStore } from '../store'

const TABS = [
  { id: 'menu',    label: 'Меню',    icon: '🍽' },
  { id: 'cart',    label: 'Заказ',   icon: '🛒' },
  { id: 'cabinet', label: 'Профиль', icon: '👤' },
]

export default function Navigation() {
  const { activePage, setPage, cart } = useStore()
  const cartCount = cart.items.reduce((s, i) => s + i.quantity, 0)

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 flex border-t"
      style={{
        background: 'var(--tg-theme-secondary-bg-color, #f1f1f1)',
        borderColor: 'var(--tg-theme-hint-color, #ccc)',
        paddingBottom: 'env(safe-area-inset-bottom, 0px)',
      }}
    >
      {TABS.map(tab => (
        <button
          key={tab.id}
          onClick={() => setPage(tab.id)}
          className="flex-1 flex flex-col items-center py-2 text-xs gap-0.5 transition-opacity"
          style={{
            color: activePage === tab.id
              ? 'var(--tg-theme-button-color, #2481cc)'
              : 'var(--tg-theme-hint-color, #888)',
          }}
        >
          <span className="text-xl relative">
            {tab.icon}
            {tab.id === 'cart' && cartCount > 0 && (
              <span
                className="absolute -top-1 -right-2 text-white text-xs w-4 h-4 rounded-full flex items-center justify-center leading-none"
                style={{ background: 'var(--tg-theme-button-color, #2481cc)', fontSize: 10 }}
              >
                {cartCount > 9 ? '9+' : cartCount}
              </span>
            )}
          </span>
          <span>{tab.label}</span>
        </button>
      ))}
    </nav>
  )
}
