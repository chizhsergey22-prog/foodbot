import { create } from 'zustand'
import api from '../api/client'

export const useStore = create((set, get) => ({
  // ── Меню ────────────────────────────────────────────────────────────────
  categories: [],
  menuLoading: false,

  fetchMenu: async () => {
    set({ menuLoading: true })
    try {
      const { data } = await api.get('/menu/')
      set({ categories: data })
    } finally {
      set({ menuLoading: false })
    }
  },

  // ── Корзина ─────────────────────────────────────────────────────────────
  cart: { items: [], total: 0, order_date: null, is_locked: false },
  cartLoading: false,

  fetchCart: async () => {
    set({ cartLoading: true })
    try {
      const { data } = await api.get('/cart/')
      set({ cart: data })
    } finally {
      set({ cartLoading: false })
    }
  },

  updateCart: async (items) => {
    const { data } = await api.put('/cart/', { items })
    set({ cart: data })
    return data
  },

  clearCart: async () => {
    await api.delete('/cart/')
    await get().fetchCart()
  },

  addToCart: async (menuItem) => {
    const cart = get().cart
    const existing = cart.items.find(i => i.menu_item_id === menuItem.id)
    let newItems
    if (existing) {
      newItems = cart.items.map(i =>
        i.menu_item_id === menuItem.id ? { ...i, quantity: i.quantity + 1 } : i
      )
    } else {
      newItems = [...cart.items, {
        menu_item_id: menuItem.id,
        name: menuItem.name,
        price: menuItem.price,
        quantity: 1,
      }]
    }
    await get().updateCart(newItems)
  },

  removeFromCart: async (menuItemId) => {
    const cart = get().cart
    const newItems = cart.items
      .map(i => i.menu_item_id === menuItemId ? { ...i, quantity: i.quantity - 1 } : i)
      .filter(i => i.quantity > 0)
    await get().updateCart(newItems)
  },

  getItemQty: (menuItemId) => {
    const cart = get().cart
    return cart.items.find(i => i.menu_item_id === menuItemId)?.quantity || 0
  },

  // ── Заказы ──────────────────────────────────────────────────────────────
  currentOrders: [],
  orderHistory: [],
  monthlyStats: null,
  ordersLoading: false,

  fetchCurrentOrder: async () => {
    const { data } = await api.get('/orders/current')
    set({ currentOrders: data || [] })
  },

  fetchHistory: async () => {
    set({ ordersLoading: true })
    try {
      const [histRes, statsRes] = await Promise.all([
        api.get('/orders/history'),
        api.get('/orders/stats/monthly'),
      ])
      set({ orderHistory: histRes.data, monthlyStats: statsRes.data })
    } finally {
      set({ ordersLoading: false })
    }
  },

  submitOrder: async () => {
    const { data } = await api.post('/orders/')
    await get().fetchCart()
    try { await get().fetchCurrentOrder() } catch (_) {}
    return data
  },

  requestCancel: async (orderId) => {
    const { data } = await api.post(`/orders/${orderId}/cancel-request`)
    try { await get().fetchCurrentOrder() } catch (_) {}
    return data
  },

  // ── UI ──────────────────────────────────────────────────────────────────
  activePage: 'menu',
  setPage: (page) => set({ activePage: page }),
}))
