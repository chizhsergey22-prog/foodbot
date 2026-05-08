import { useStore } from '../store'

export default function MenuItem({ item }) {
  const { getItemQty, addToCart, removeFromCart, cart } = useStore()
  const qty = getItemQty(item.id)

  const handleAdd = () => addToCart(item)
  const handleRemove = () => removeFromCart(item.id)

  return (
    <div
      className="flex items-center gap-3 px-4 py-3 border-b"
      style={{ borderColor: 'var(--tg-theme-hint-color, #e5e7eb)' }}
    >
      {item.photo_url ? (
        <img src={item.photo_url} alt={item.name} className="w-14 h-14 rounded-xl object-cover shrink-0" />
      ) : (
        <div
          className="w-14 h-14 rounded-xl flex items-center justify-center text-2xl shrink-0"
          style={{ background: 'var(--tg-theme-secondary-bg-color, #f3f4f6)' }}
        >
          🍽
        </div>
      )}

      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm leading-tight">{item.name}</p>
        {item.description && (
          <p className="text-xs mt-0.5 line-clamp-2" style={{ color: 'var(--tg-theme-hint-color, #888)' }}>
            {item.description}
          </p>
        )}
        <p className="text-sm font-semibold mt-1" style={{ color: 'var(--tg-theme-button-color, #2481cc)' }}>
          {item.price} ₴
        </p>
      </div>

      <div className="shrink-0">
        {qty === 0 ? (
          <button
            onClick={handleAdd}
            disabled={cart.is_locked}
            className="w-8 h-8 rounded-full flex items-center justify-center text-lg font-bold disabled:opacity-40"
            style={{ background: 'var(--tg-theme-button-color, #2481cc)', color: 'var(--tg-theme-button-text-color, #fff)' }}
          >
            +
          </button>
        ) : (
          <div className="flex items-center gap-2">
            <button
              onClick={handleRemove}
              className="w-8 h-8 rounded-full flex items-center justify-center text-lg font-bold"
              style={{ background: 'var(--tg-theme-secondary-bg-color, #f3f4f6)', color: 'var(--tg-theme-text-color, #000)' }}
            >
              −
            </button>
            <span className="w-5 text-center text-sm font-semibold">{qty}</span>
            <button
              onClick={handleAdd}
              disabled={cart.is_locked}
              className="w-8 h-8 rounded-full flex items-center justify-center text-lg font-bold disabled:opacity-40"
              style={{ background: 'var(--tg-theme-button-color, #2481cc)', color: 'var(--tg-theme-button-text-color, #fff)' }}
            >
              +
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
