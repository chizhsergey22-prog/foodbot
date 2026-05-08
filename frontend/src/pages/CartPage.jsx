import { useState, useEffect } from 'react'
import { useStore } from '../store'
import CartItemCard from '../components/CartItem'

const STATUS_LABELS = {
  active:           'Принят',
  locked:           'Передан на кухню',
  cancel_requested: 'Запрос на отмену',
  cancelled:        'Отменён',
  delivered:        'Доставлен',
}

const STATUS_COLORS = {
  active:           '#22c55e',
  locked:           '#f59e0b',
  cancel_requested: '#f97316',
  cancelled:        '#ef4444',
  delivered:        '#2481cc',
}

export default function CartPage() {
  const { cart, cartLoading, currentOrders, fetchCart, fetchCurrentOrder, submitOrder, requestCancel, setPage } = useStore()
  const [submitting, setSubmitting] = useState(false)
  const [cancellingId, setCancellingId] = useState(null)
  const [message, setMessage] = useState(null)

  useEffect(() => {
    fetchCart()
    fetchCurrentOrder()
  }, [])

  const handleSubmit = async () => {
    setSubmitting(true)
    setMessage(null)
    try {
      await submitOrder()
      setMessage({ type: 'success', text: '✅ Заказ оформлен!' })
    } catch (e) {
      const detail = e.response?.data?.detail || 'Ошибка оформления заказа'
      setMessage({ type: 'error', text: `❌ ${detail}` })
    } finally {
      setSubmitting(false)
    }
  }

  const handleCancelRequest = async (orderId, status) => {
    setCancellingId(orderId)
    try {
      const res = await requestCancel(orderId)
      if (res.status === 'cancelled') {
        setMessage({ type: 'success', text: '✅ Заказ отменён' })
      } else {
        setMessage({ type: 'success', text: '⏳ Запрос на отмену отправлен администратору' })
      }
    } catch (e) {
      setMessage({ type: 'error', text: e.response?.data?.detail || 'Ошибка' })
    } finally {
      setCancellingId(null)
    }
  }

  if (cartLoading) {
    return <div className="flex justify-center py-12 text-tg-hint text-sm">Загрузка...</div>
  }

  const orderDate = cart.order_date
    ? new Date(cart.order_date).toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })
    : '...'

  const hasCartItems = cart.items && cart.items.length > 0

  // Корзина с товарами — показываем форму нового заказа
  if (hasCartItems) {
    return (
      <div className="px-4 py-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-base">Заказ на {orderDate}</h2>
          {cart.is_locked && (
            <span className="text-xs px-2 py-1 rounded-full" style={{ background: '#fef3c7', color: '#d97706' }}>
              🔒 Приём закрыт
            </span>
          )}
        </div>

        <div
          className="rounded-2xl overflow-hidden mb-4"
          style={{ background: 'var(--tg-theme-secondary-bg-color, #f3f4f6)' }}
        >
          {cart.items.map(item => (
            <CartItemCard key={item.menu_item_id} item={item} />
          ))}
        </div>

        <div
          className="rounded-2xl p-4 mb-4 flex justify-between items-center"
          style={{ background: 'var(--tg-theme-secondary-bg-color, #f3f4f6)' }}
        >
          <span className="font-semibold">Итого</span>
          <span className="font-bold text-lg" style={{ color: 'var(--tg-theme-button-color, #2481cc)' }}>
            {(cart.total || 0).toFixed(0)} ₴
          </span>
        </div>

        {message && (
          <p className="text-center text-sm mb-3" style={{ color: message.type === 'error' ? '#ef4444' : '#22c55e' }}>
            {message.text}
          </p>
        )}

        {!cart.is_locked && (
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="w-full py-3.5 rounded-2xl font-semibold text-sm disabled:opacity-60"
            style={{ background: 'var(--tg-theme-button-color, #2481cc)', color: 'var(--tg-theme-button-text-color, #fff)' }}
          >
            {submitting ? 'Оформляем...' : `Оформить заказ — ${(cart.total || 0).toFixed(0)} ₴`}
          </button>
        )}

        {cart.is_locked && (
          <p className="text-center text-sm" style={{ color: 'var(--tg-theme-hint-color, #888)' }}>
            Приём заказов на сегодня завершён
          </p>
        )}
      </div>
    )
  }

  // Корзина пуста — показываем все оформленные заказы на эту дату
  if (currentOrders.length > 0) {
    const dateLabel = new Date(currentOrders[0].order_date).toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })
    return (
      <div className="px-4 py-4">
        <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--tg-theme-hint-color, #888)' }}>
          Заказы на {dateLabel}
        </p>

        {message && (
          <p className="text-center text-sm mb-3" style={{ color: message.type === 'error' ? '#ef4444' : '#22c55e' }}>
            {message.text}
          </p>
        )}

        <div className="flex flex-col gap-3">
          {currentOrders.map(order => (
            <div
              key={order.id}
              className="rounded-2xl overflow-hidden"
              style={{ background: 'var(--tg-theme-secondary-bg-color, #f3f4f6)' }}
            >
              <div className="px-4 py-3 flex items-center justify-between border-b" style={{ borderColor: 'var(--tg-theme-hint-color, #e5e7eb)' }}>
                <div>
                  <p className="font-semibold text-sm">
                    {order.status === 'active' ? 'Заказ' : `Заказ №${order.daily_number ?? order.id}`}
                  </p>
                  <p className="text-xs mt-0.5 font-semibold" style={{ color: 'var(--tg-theme-button-color, #2481cc)' }}>
                    {order.items.reduce((s, i) => s + i.price * i.quantity, 0).toFixed(0)} ₴
                  </p>
                </div>
                <span
                  className="text-xs font-medium px-2 py-0.5 rounded-full text-white"
                  style={{ background: STATUS_COLORS[order.status] || '#888' }}
                >
                  {STATUS_LABELS[order.status] || order.status}
                </span>
              </div>

              <div className="px-4 py-2">
                {order.items.map(item => (
                  <div key={item.id} className="flex justify-between py-1.5 border-b last:border-0" style={{ borderColor: 'var(--tg-theme-hint-color, #e5e7eb)' }}>
                    <span className="text-sm">{item.item_name}</span>
                    <span className="text-sm font-medium">{item.quantity > 1 ? `×${item.quantity}  ` : ''}{(item.price * item.quantity).toFixed(0)} ₴</span>
                  </div>
                ))}
              </div>

              {(order.status === 'active' || order.status === 'locked') && (
                <div className="px-4 pb-3">
                  <button
                    onClick={() => handleCancelRequest(order.id, order.status)}
                    disabled={cancellingId === order.id}
                    className="w-full py-2 rounded-xl text-sm font-medium disabled:opacity-50 mt-1"
                    style={{ background: '#fee2e2', color: '#ef4444' }}
                  >
                    {order.status === 'locked' ? 'Запросить отмену' : 'Отменить'}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    )
  }

  // Нет ни корзины, ни заказов
  return (
    <div className="px-4 py-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold text-base">Заказ на {orderDate}</h2>
      </div>
      <div className="text-center py-12">
        <p className="text-4xl mb-3">🛒</p>
        <p className="text-sm mb-4" style={{ color: 'var(--tg-theme-hint-color, #888)' }}>
          Корзина пуста
        </p>
        <button
          onClick={() => setPage('menu')}
          className="px-6 py-2 rounded-full text-sm font-medium"
          style={{ background: 'var(--tg-theme-button-color, #2481cc)', color: '#fff' }}
        >
          Перейти в меню
        </button>
      </div>
    </div>
  )
}
