import { useState, useRef } from 'react'
import { useStore } from '../store'
import MenuItemCard from '../components/MenuItem'

export default function MenuPage() {
  const { categories, menuLoading } = useStore()
  const [activeTab, setActiveTab] = useState(0)
  const tabsRef = useRef(null)

  const scroll = (dir) => {
    if (tabsRef.current) tabsRef.current.scrollLeft += dir * 120
  }

  if (menuLoading) {
    return <div className="flex justify-center py-12 text-tg-hint">Загрузка меню...</div>
  }

  if (!categories.length) {
    return <div className="flex justify-center py-12 text-sm text-tg-hint">Меню недоступно</div>
  }

  const currentCat = categories[activeTab]

  return (
    <div>
      {/* Вкладки категорий */}
      <div
        className="sticky top-0 z-10 flex items-center border-b"
        style={{
          background: 'var(--tg-theme-bg-color, #fff)',
          borderColor: 'var(--tg-theme-hint-color, #e5e7eb)',
        }}
      >
        <button
          onClick={() => scroll(-1)}
          className="shrink-0 px-2 py-3 text-lg leading-none"
          style={{ color: 'var(--tg-theme-hint-color, #aaa)' }}
        >
          ‹
        </button>

        <div
          ref={tabsRef}
          className="flex overflow-x-auto gap-2 py-3 scrollbar-hide"
          style={{ scrollBehavior: 'smooth' }}
        >
          {categories.map((cat, idx) => (
            <button
              key={cat.id}
              onClick={() => setActiveTab(idx)}
              className="shrink-0 px-4 py-1.5 rounded-full text-sm font-medium transition-colors"
              style={
                activeTab === idx
                  ? { background: 'var(--tg-theme-button-color, #2481cc)', color: 'var(--tg-theme-button-text-color, #fff)' }
                  : { background: 'var(--tg-theme-secondary-bg-color, #f3f4f6)', color: 'var(--tg-theme-text-color, #000)' }
              }
            >
              {cat.name}
            </button>
          ))}
        </div>

        <button
          onClick={() => scroll(1)}
          className="shrink-0 px-2 py-3 text-lg leading-none"
          style={{ color: 'var(--tg-theme-hint-color, #aaa)' }}
        >
          ›
        </button>
      </div>

      {/* Позиции текущей категории */}
      <div>
        {currentCat?.items.map(item => (
          <MenuItemCard key={item.id} item={item} />
        ))}
        {!currentCat?.items.length && (
          <p className="text-center py-8 text-sm text-tg-hint">Нет доступных блюд</p>
        )}
      </div>
    </div>
  )
}
