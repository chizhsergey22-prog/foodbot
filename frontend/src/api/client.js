import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({ baseURL: BASE_URL })

api.interceptors.request.use((config) => {
  const tg = window.Telegram?.WebApp
  if (tg?.initData) {
    config.headers['Authorization'] = `tma ${tg.initData}`
  }
  return config
})

export default api
