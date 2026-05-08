-- Food Ordering Bot — PostgreSQL schema

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Пользователи
CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    full_name   VARCHAR(255) NOT NULL,
    username    VARCHAR(255),
    role        VARCHAR(50) NOT NULL DEFAULT 'employee',  -- employee | restaurant_admin | super_admin
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    balance_debt NUMERIC(10,2) NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Инвайт-коды
CREATE TABLE IF NOT EXISTS invite_codes (
    id          SERIAL PRIMARY KEY,
    code        VARCHAR(32) UNIQUE NOT NULL,
    created_by  BIGINT NOT NULL,    -- telegram_id суперадмина
    used_by     BIGINT,             -- telegram_id пользователя
    is_used     BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Категории меню
CREATE TABLE IF NOT EXISTS categories (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE
);

-- Позиции меню
CREATE TABLE IF NOT EXISTS menu_items (
    id          SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    price       NUMERIC(10,2) NOT NULL,
    photo_url   VARCHAR(500),
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    is_stop_list BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Заказы
CREATE TABLE IF NOT EXISTS orders (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    order_date  DATE NOT NULL,           -- дата доставки
    status      VARCHAR(50) NOT NULL DEFAULT 'active',
    -- active | locked | cancel_requested | cancelled | delivered
    total_price  NUMERIC(10,2) NOT NULL DEFAULT 0,
    daily_number INTEGER,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Позиции заказа
CREATE TABLE IF NOT EXISTS order_items (
    id              SERIAL PRIMARY KEY,
    order_id        INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    menu_item_id    INTEGER REFERENCES menu_items(id) ON DELETE SET NULL,
    item_name       VARCHAR(255) NOT NULL,   -- снапшот названия на момент заказа
    quantity        INTEGER NOT NULL DEFAULT 1,
    price           NUMERIC(10,2) NOT NULL   -- снапшот цены
);

-- Запросы на отмену заказа (после 17:00)
CREATE TABLE IF NOT EXISTS cancel_requests (
    id          SERIAL PRIMARY KEY,
    order_id    INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status      VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending | approved | rejected
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at  TIMESTAMPTZ,
    resolved_by  BIGINT   -- telegram_id суперадмина
);

-- Системные настройки
CREATE TABLE IF NOT EXISTS settings (
    key     VARCHAR(100) PRIMARY KEY,
    value   TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_users_telegram_id    ON users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_orders_user_date     ON orders(user_id, order_date);
CREATE INDEX IF NOT EXISTS idx_order_items_order    ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_invite_codes_code    ON invite_codes(code);
CREATE INDEX IF NOT EXISTS idx_menu_items_category  ON menu_items(category_id);

-- Настройки по умолчанию
INSERT INTO settings (key, value) VALUES
    ('cutoff_time', '17:00'),
    ('timezone', 'Europe/Kyiv')
ON CONFLICT (key) DO NOTHING;

-- Категорії меню 1639 Lounge Bar
INSERT INTO categories (name, sort_order) VALUES
    ('Гарніри',           1),
    ('Овочі',             2),
    ('Основні страви',    3),
    ('Млинці та десерти', 4),
    ('Сніданки',          5),
    ('Салати',            6),
    ('Перші страви',      7),
    ('Соус',              8),
    ('Рестик',            9)
ON CONFLICT DO NOTHING;

-- Меню 1639 Lounge Bar
INSERT INTO menu_items (category_id, name, description, price) VALUES
    -- Гарніри
    ((SELECT id FROM categories WHERE name='Гарніри'), 'Деруни картопляні з куркою та грибами', '220 г', 120),
    ((SELECT id FROM categories WHERE name='Гарніри'), 'Картопля по-селянськи', '200 г', 45),
    ((SELECT id FROM categories WHERE name='Гарніри'), 'Гречка з маслом', '150 г', 35),
    ((SELECT id FROM categories WHERE name='Гарніри'), 'Булгур з овочами', '150 г', 45),
    ((SELECT id FROM categories WHERE name='Гарніри'), 'Пюре', '200 г', 40),
    -- Овочі
    ((SELECT id FROM categories WHERE name='Овочі'), 'Овочі на пару', 'Броколі, бейбі-морква, цвітна капуста (150 г)', 55),
    ((SELECT id FROM categories WHERE name='Овочі'), 'Овочі гриль', 'Кабачки, перець болгарський, помідори, гриби (200 г)', 70),
    -- Основні страви
    ((SELECT id FROM categories WHERE name='Основні страви'), 'Котлета куряча', '100 г', 50),
    ((SELECT id FROM categories WHERE name='Основні страви'), 'Курячий шніцель', '120 г', 60),
    ((SELECT id FROM categories WHERE name='Основні страви'), 'Куряче стегно смажене', '170 г', 50),
    ((SELECT id FROM categories WHERE name='Основні страви'), 'Фрикадельки в томатному соусі', '150 г', 70),
    ((SELECT id FROM categories WHERE name='Основні страви'), 'Хек смажений', 'Ціна за 100 г', 75),
    ((SELECT id FROM categories WHERE name='Основні страви'), 'Свинячий шашлик', 'Ціна за 100 г', 90),
    ((SELECT id FROM categories WHERE name='Основні страви'), 'Шашлик курячий', 'Ціна за 100 г', 69),
    -- Млинці та десерти
    ((SELECT id FROM categories WHERE name='Млинці та десерти'), 'Млинці з сиром', '200 г', 80),
    ((SELECT id FROM categories WHERE name='Млинці та десерти'), 'Млинці зі згущеним молоком', '230 г', 55),
    ((SELECT id FROM categories WHERE name='Млинці та десерти'), 'Млинці з куркою та грибами', '200 г', 80),
    ((SELECT id FROM categories WHERE name='Млинці та десерти'), 'Чізкейк', NULL, 90),
    ((SELECT id FROM categories WHERE name='Млинці та десерти'), 'Оладки по-домашньому з джемом', '200 г', 60),
    -- Сніданки
    ((SELECT id FROM categories WHERE name='Сніданки'), 'Омлет з беконом та сиром', '160 г', 100),
    ((SELECT id FROM categories WHERE name='Сніданки'), 'Вівсянка солодка', '200 г', 80),
    ((SELECT id FROM categories WHERE name='Сніданки'), 'Вівсянка з яйцем пашот та соусом Голландез', '200 г', 85),
    -- Салати
    ((SELECT id FROM categories WHERE name='Салати'), 'Салат крабовий', '150 г', 75),
    ((SELECT id FROM categories WHERE name='Салати'), 'Салат Цезар з куркою', '150 г', 90),
    ((SELECT id FROM categories WHERE name='Салати'), 'Салат овочевий з сиром Фетою', '150 г', 85),
    ((SELECT id FROM categories WHERE name='Салати'), 'Салат із квашеної капусти та огірків', '150 г', 50),
    -- Перші страви
    ((SELECT id FROM categories WHERE name='Перші страви'), 'Борщ з яловичиною', '300 г', 60),
    ((SELECT id FROM categories WHERE name='Перші страви'), 'Солянка', '300 г', 50),
    ((SELECT id FROM categories WHERE name='Перші страви'), 'Мінестроне (овочевий суп)', '200 г', 40),
    ((SELECT id FROM categories WHERE name='Перші страви'), 'Хліб', '3 шт', 10),
    -- Соус
    ((SELECT id FROM categories WHERE name='Соус'), 'Кетчуп', NULL, 15),
    ((SELECT id FROM categories WHERE name='Соус'), 'Майонез', NULL, 15),
    ((SELECT id FROM categories WHERE name='Соус'), 'Гірчиця', NULL, 15),
    ((SELECT id FROM categories WHERE name='Соус'), 'Сметана', NULL, 15),
    ((SELECT id FROM categories WHERE name='Соус'), 'Солодкий Чилі', NULL, 15),
    ((SELECT id FROM categories WHERE name='Соус'), 'Барбекю', NULL, 15),
    ((SELECT id FROM categories WHERE name='Соус'), 'Сирний', NULL, 15),
    -- Рестик — Закуски
    ((SELECT id FROM categories WHERE name='Рестик'), 'Хамон', NULL, 300),
    ((SELECT id FROM categories WHERE name='Рестик'), 'Оливки', NULL, 150),
    ((SELECT id FROM categories WHERE name='Рестик'), 'Креветки попкорн', 'Хрусткі обсмажені креветки в паніровці, з пікантним соусом світ чілі', 350),
    ((SELECT id FROM categories WHERE name='Рестик'), 'Начос із сирним соусом', 'Мексиканська закуска з ніжним вершково-сирним соусом на основі дор блю, чедеру та моцарели', 190),
    ((SELECT id FROM categories WHERE name='Рестик'), 'Антипасти сет', 'Із добірних сирів, хамону та оливок', 320),
    -- Рестик — Салати
    ((SELECT id FROM categories WHERE name='Рестик'), 'Салат із креветкою', 'Мікс свіжих салатів із соковитими креветками, з гуакамоле та кисло-солодким соусом', 370),
    ((SELECT id FROM categories WHERE name='Рестик'), 'Салат Цезар', 'Класичний мікс ромену з куркою, хрусткими крутонами та пармезаном', 300),
    ((SELECT id FROM categories WHERE name='Рестик'), 'Салат Цезар з креветкою', 'Класичний мікс ромену з креветкою, хрусткими крутонами та пармезаном', 380),
    -- Рестик — Супи
    ((SELECT id FROM categories WHERE name='Рестик'), 'Сальморехо', 'Гарячий іспанський суп із томатів піллаті з тонкими скибками хамону', 250),
    -- Рестик — Паста
    ((SELECT id FROM categories WHERE name='Рестик'), 'Паста з креветкою', 'Ніжна паста з соковитими креветками у вершковому соусі, присипана пармезаном', 350),
    ((SELECT id FROM categories WHERE name='Рестик'), 'Паста карбонара', 'Класична італійська паста з беконом і яйцем у ніжному вершковому соусі', 290),
    -- Рестик — Основні страви
    ((SELECT id FROM categories WHERE name='Рестик'), 'Темпура суші-бургер', 'Креветка, авокадо, крем-сир, спайсі соус, норі в паніровці', 360),
    ((SELECT id FROM categories WHERE name='Рестик'), 'Сендвіч з рваною яловичиною', 'Рвана яловичина, карамелізований печений перець і тягуча моцарела', 290),
    ((SELECT id FROM categories WHERE name='Рестик'), 'Food Break', 'Картопля фрі з трюфельною пастою та спайсі соусом, з битими огірками та криспі куркою, плавлений чедер', 340),
    ((SELECT id FROM categories WHERE name='Рестик'), 'Хот дог класичний', 'Молочна сосиска в булочці бріош з морквою по-корейськи, кетчупом та гірчицею. З картоплею фрі', 270),
    ((SELECT id FROM categories WHERE name='Рестик'), 'Бургер із яловичиною', 'Соковита котлета з яловичини у булочці бріош із вершково-сирним соусом із чедером. З картоплею фрі', 380),
    ((SELECT id FROM categories WHERE name='Рестик'), 'Тако з куркою', 'Обсмажене куряче філе з перцем і цибулею, моцарела, вершково-сирний соус чедер', 285),
    ((SELECT id FROM categories WHERE name='Рестик'), 'Тако з креветкою', 'Соковита креветка з перцем і цибулею під пікантним вершковим соусом том ям', 330),
    ((SELECT id FROM categories WHERE name='Рестик'), 'На сніданок', 'Хрусткий тост із вершковим маслом, авокадо, смаженим яйцем та беконом', 270),
    -- Рестик — Подорож до дому
    ((SELECT id FROM categories WHERE name='Рестик'), 'Пельмені з куркою', 'Подорож до дому', 240),
    ((SELECT id FROM categories WHERE name='Рестик'), 'Млинці зі згущенним молоком та лохиною', 'Подорож до дому', 235),
    ((SELECT id FROM categories WHERE name='Рестик'), 'Нагетси з картоплею фрі', 'Подорож до дому', 290),
    ((SELECT id FROM categories WHERE name='Рестик'), 'Домашні оладки з малиновим варенням', 'Класичні оладки з густим малиновим джемом', 190),
    -- Рестик — Десерти
    ((SELECT id FROM categories WHERE name='Рестик'), 'Брауні', NULL, 210),
    ((SELECT id FROM categories WHERE name='Рестик'), 'Морозиво ванільне', NULL, 100),
    ((SELECT id FROM categories WHERE name='Рестик'), 'Чізкейк', NULL, 230)
ON CONFLICT DO NOTHING;
