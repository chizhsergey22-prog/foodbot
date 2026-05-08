import { useStore } from '../store'

export default function CartItem({ item }) {
  const { addToCart, removeFromCart, cart } = useStore()

  return (
    <div
      className="flex items-center gap-3 px-4 py-3 border-b"
      style={{ borderColor: 'var(--tg-theme-hint-color, #e5e7eb)' }}
    >
      <div className="flex-1">
        <p className="text-sm font-medium">{item.name}</p>
        <p className="text-xs mt-0.5" style={{ color: 'var(--tg-theme-hint-color, #888)' }}>
          {item.price} ₴ × {item.quantity} = {(item.price * item.quantity).toFixed(0)} ₴
        </p>
      </div>

      {!cart.is_locked && (
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => removeFromCart(item.menu_item_id)}
            className="w-8 h-8 rounded-full flex items-center justify-center text-lg"
            style={{ background: 'var(--tg-theme-secondary-bg-color, #f3f4f6)' }}
          >
            −
          </button>
          <span className="w-5 text-center text-sm font-semibold">{item.quantity}</span>
          <button
            onClick={() => addToCart({ id: item.menu_item_id, name: item.name, price: item.price })}
            className="w-8 h-8 rounded-full flex items-center justify-center text-lg"
            style={{ background: 'var(--tg-theme-button-color, #2481cc)', color: '#fff' }}
          >
            +
          </button>
        </div>
      )}

      {cart.is_locked && (
        <span className="text-sm font-semibold" style={{ color: 'var(--tg-theme-hint-color, #888)' }}>
          ×{item.quantity}
        </span>
      )}
    </div>
  )
}
