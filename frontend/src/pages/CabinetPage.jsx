import { useEffect, useState } from 'react'
import { useStore } from '../store'

const STATUS_LABELS = {
  active:           'Принят',
  locked:           'На кухне',
  cancel_requested: 'Запрос отмены',
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

const MONTHS = ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь']

const DEFAULT_VISIBLE = 3

export default function CabinetPage() {
  const { orderHistory, monthlyStats, ordersLoading, fetchHistory, updateCart, setPage, cart } = useStore()
  const [visibleCount, setVisibleCount] = useState(DEFAULT_VISIBLE)
  const [repeatingId, setRepeatingId] = useState(null)
  const [repeatError, setRepeatError] = useState(null)

  useEffect(() => {
    fetchHistory()
  }, [])

  const handleRepeat = async (order) => {
    if (cart.is_locked) {
      setRepeatError('Приём заказов закрыт')
      setTimeout(() => setRepeatError(null), 3000)
      return
    }

    const items = order.items
      .filter(i => i.menu_item_id != null)
      .map(i => ({
        menu_item_id: i.menu_item_id,
        name: i.item_name,
        price: i.price,
        quantity: i.quantity,
      }))

    if (!items.length) {
      setRepeatError('Блюда из этого заказа больше недоступны')
      setTimeout(() => setRepeatError(null), 3000)
      return
    }

    setRepeatingId(order.id)
    try {
      await updateCart(items)
      setPage('cart')
    } catch (e) {
      const msg = e?.response?.status === 423
        ? 'Приём заказов закрыт'
        : 'Не удалось добавить в корзину'
      setRepeatError(msg)
      setTimeout(() => setRepeatError(null), 3000)
    } finally {
      setRepeatingId(null)
    }
  }

  if (ordersLoading) {
    return <div className="flex justify-center py-12 text-sm" style={{ color: 'var(--tg-theme-hint-color, #888)' }}>Загрузка...</div>
  }

  const tgUser = window.Telegram?.WebApp?.initDataUnsafe?.user
  const visibleOrders = orderHistory.slice(0, visibleCount)

  return (
    <div className="pb-4">
      {/* Шапка профиля */}
      <div
        className="px-4 py-5 flex items-center gap-3 border-b"
        style={{ borderColor: 'var(--tg-theme-hint-color, #e5e7eb)', background: 'var(--tg-theme-secondary-bg-color, #f3f4f6)' }}
      >
        <div
          className="w-14 h-14 rounded-full flex items-center justify-center text-2xl"
          style={{ background: 'var(--tg-theme-button-color, #2481cc)' }}
        >
          {tgUser?.first_name?.[0] || '👤'}
        </div>
        <div>
          <p className="font-semibold">{tgUser ? `${tgUser.first_name} ${tgUser.last_name || ''}`.trim() : 'Сотрудник'}</p>
          {tgUser?.username && (
            <p className="text-sm" style={{ color: 'var(--tg-theme-hint-color, #888)' }}>@{tgUser.username}</p>
          )}
        </div>
      </div>

      {/* Статистика за месяц */}
      {monthlyStats && (
        <div className="px-4 py-4">
          <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--tg-theme-hint-color, #888)' }}>
            {MONTHS[monthlyStats.month - 1]} {monthlyStats.year}
          </p>
          <div className="grid grid-cols-2 gap-3">
            <StatCard label="Заказов" value={monthlyStats.orders_count} />
            <StatCard label="Потрачено" value={`${monthlyStats.total.toFixed(0)} ₴`} />
          </div>
        </div>
      )}

      {/* Ошибка повтора */}
      {repeatError && (
        <div className="mx-4 mb-2 px-3 py-2 rounded-xl text-xs text-center text-white" style={{ background: '#ef4444' }}>
          {repeatError}
        </div>
      )}

      {/* История */}
      <div className="px-4">
        <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--tg-theme-hint-color, #888)' }}>
          История заказов
        </p>

        {!orderHistory.length ? (
          <p className="text-center py-8 text-sm" style={{ color: 'var(--tg-theme-hint-color, #888)' }}>
            Нет заказов
          </p>
        ) : (
          <>
            <div className="flex flex-col gap-3">
              {visibleOrders.map(order => (
                <div
                  key={order.id}
                  className="rounded-2xl overflow-hidden"
                  style={{ background: 'var(--tg-theme-secondary-bg-color, #f3f4f6)' }}
                >
                  <div className="px-4 py-3 flex items-center justify-between border-b" style={{ borderColor: 'var(--tg-theme-hint-color, #e5e7eb)' }}>
                    <div>
                      <p className="text-sm font-medium">
                        {new Date(order.order_date).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })}
                      </p>
                      <p className="text-xs mt-0.5 font-semibold" style={{ color: 'var(--tg-theme-button-color, #2481cc)' }}>
                        {order.items.reduce((s, i) => s + i.price * i.quantity, 0).toFixed(0)} ₴
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span
                        className="text-xs px-2 py-0.5 rounded-full text-white"
                        style={{ background: STATUS_COLORS[order.status] || '#888' }}
                      >
                        {STATUS_LABELS[order.status] || order.status}
                      </span>
                    </div>
                  </div>
                  <div className="px-4 py-2">
                    {order.items.map(item => (
                      <p key={item.id} className="text-xs py-1" style={{ color: 'var(--tg-theme-hint-color, #555)' }}>
                        • {item.item_name}{item.quantity > 1 ? ` ×${item.quantity}` : ''}
                      </p>
                    ))}
                  </div>
                  <div className="px-4 pb-3">
                    <button
                      onClick={() => handleRepeat(order)}
                      disabled={repeatingId === order.id}
                      className="w-full py-1.5 rounded-xl text-xs font-medium"
                      style={{
                        background: repeatingId === order.id ? 'var(--tg-theme-hint-color, #aaa)' : 'var(--tg-theme-button-color, #2481cc)',
                        color: 'var(--tg-theme-button-text-color, #fff)',
                      }}
                    >
                      {repeatingId === order.id ? 'Добавляем...' : '🔁 Повторить'}
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {visibleCount < orderHistory.length && (
              <button
                onClick={() => setVisibleCount(c => c + DEFAULT_VISIBLE)}
                className="w-full mt-3 py-2.5 rounded-2xl text-sm"
                style={{
                  background: 'var(--tg-theme-secondary-bg-color, #f3f4f6)',
                  color: 'var(--tg-theme-button-color, #2481cc)',
                }}
              >
                Показать ещё ({orderHistory.length - visibleCount})
              </button>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function StatCard({ label, value, accent }) {
  return (
    <div
      className="rounded-2xl p-3 text-center"
      style={{ background: 'var(--tg-theme-secondary-bg-color, #f3f4f6)' }}
    >
      <p
        className="text-base font-bold"
        style={{ color: accent ? '#ef4444' : 'var(--tg-theme-text-color, #000)' }}
      >
        {value}
      </p>
      <p className="text-xs mt-0.5" style={{ color: 'var(--tg-theme-hint-color, #888)' }}>
        {label}
      </p>
    </div>
  )
}
