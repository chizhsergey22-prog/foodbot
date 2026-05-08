"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-08
"""
from alembic import op

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id           SERIAL PRIMARY KEY,
            telegram_id  BIGINT UNIQUE NOT NULL,
            full_name    VARCHAR(255) NOT NULL,
            username     VARCHAR(255),
            role         VARCHAR(50) NOT NULL DEFAULT 'employee',
            is_active    BOOLEAN NOT NULL DEFAULT TRUE,
            balance_debt NUMERIC(10,2) NOT NULL DEFAULT 0,
            team         VARCHAR(50),
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS invite_codes (
            id           SERIAL PRIMARY KEY,
            code         VARCHAR(32) UNIQUE NOT NULL,
            label        VARCHAR(255),
            created_by   BIGINT NOT NULL,
            used_by      BIGINT,
            is_used      BOOLEAN NOT NULL DEFAULT FALSE,
            role         VARCHAR(50) NOT NULL DEFAULT 'employee',
            initial_debt NUMERIC(10,2) NOT NULL DEFAULT 0,
            expires_at   TIMESTAMPTZ,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id         SERIAL PRIMARY KEY,
            name       VARCHAR(100) NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active  BOOLEAN NOT NULL DEFAULT TRUE
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS menu_items (
            id           SERIAL PRIMARY KEY,
            category_id  INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            name         VARCHAR(255) NOT NULL,
            description  TEXT,
            price        NUMERIC(10,2) NOT NULL,
            photo_url    VARCHAR(500),
            is_active    BOOLEAN NOT NULL DEFAULT TRUE,
            is_stop_list BOOLEAN NOT NULL DEFAULT FALSE,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id           SERIAL PRIMARY KEY,
            user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            order_date   DATE NOT NULL,
            status       VARCHAR(50) NOT NULL DEFAULT 'active',
            total_price  NUMERIC(10,2) NOT NULL DEFAULT 0,
            daily_number INTEGER,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id           SERIAL PRIMARY KEY,
            order_id     INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            menu_item_id INTEGER REFERENCES menu_items(id) ON DELETE SET NULL,
            item_name    VARCHAR(255) NOT NULL,
            quantity     INTEGER NOT NULL DEFAULT 1,
            price        NUMERIC(10,2) NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS cancel_requests (
            id           SERIAL PRIMARY KEY,
            order_id     INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status       VARCHAR(50) NOT NULL DEFAULT 'pending',
            requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            resolved_at  TIMESTAMPTZ,
            resolved_by  BIGINT
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key        VARCHAR(100) PRIMARY KEY,
            value      TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # Indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_telegram_id   ON users(telegram_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_date    ON orders(user_id, order_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_order_items_order   ON order_items(order_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_invite_codes_code   ON invite_codes(code)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_menu_items_category ON menu_items(category_id)")

    # Default settings
    op.execute("""
        INSERT INTO settings (key, value) VALUES
            ('cutoff_time', '17:00'),
            ('timezone', 'Europe/Kyiv')
        ON CONFLICT (key) DO NOTHING
    """)

    # Seed menu (1639 Lounge Bar)
    op.execute("""
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
        ON CONFLICT DO NOTHING
    """)
    op.execute("""
        INSERT INTO menu_items (category_id, name, description, price) VALUES
            ((SELECT id FROM categories WHERE name='Гарніри'), 'Деруни картопляні з куркою та грибами', '220 г', 120),
            ((SELECT id FROM categories WHERE name='Гарніри'), 'Картопля по-селянськи', '200 г', 45),
            ((SELECT id FROM categories WHERE name='Гарніри'), 'Гречка з маслом', '150 г', 35),
            ((SELECT id FROM categories WHERE name='Гарніри'), 'Булгур з овочами', '150 г', 45),
            ((SELECT id FROM categories WHERE name='Гарніри'), 'Пюре', '200 г', 40),
            ((SELECT id FROM categories WHERE name='Овочі'), 'Овочі на пару', 'Броколі, бейбі-морква, цвітна капуста (150 г)', 55),
            ((SELECT id FROM categories WHERE name='Овочі'), 'Овочі гриль', 'Кабачки, перець болгарський, помідори, гриби (200 г)', 70),
            ((SELECT id FROM categories WHERE name='Основні страви'), 'Котлета куряча', '100 г', 50),
            ((SELECT id FROM categories WHERE name='Основні страви'), 'Курячий шніцель', '120 г', 60),
            ((SELECT id FROM categories WHERE name='Основні страви'), 'Куряче стегно смажене', '170 г', 50),
            ((SELECT id FROM categories WHERE name='Основні страви'), 'Фрикадельки в томатному соусі', '150 г', 70),
            ((SELECT id FROM categories WHERE name='Основні страви'), 'Хек смажений', 'Ціна за 100 г', 75),
            ((SELECT id FROM categories WHERE name='Основні страви'), 'Свинячий шашлик', 'Ціна за 100 г', 90),
            ((SELECT id FROM categories WHERE name='Основні страви'), 'Шашлик курячий', 'Ціна за 100 г', 69),
            ((SELECT id FROM categories WHERE name='Млинці та десерти'), 'Млинці з сиром', '200 г', 80),
            ((SELECT id FROM categories WHERE name='Млинці та десерти'), 'Млинці зі згущеним молоком', '230 г', 55),
            ((SELECT id FROM categories WHERE name='Млинці та десерти'), 'Млинці з куркою та грибами', '200 г', 80),
            ((SELECT id FROM categories WHERE name='Млинці та десерти'), 'Чізкейк', NULL, 90),
            ((SELECT id FROM categories WHERE name='Млинці та десерти'), 'Оладки по-домашньому з джемом', '200 г', 60),
            ((SELECT id FROM categories WHERE name='Сніданки'), 'Омлет з беконом та сиром', '160 г', 100),
            ((SELECT id FROM categories WHERE name='Сніданки'), 'Вівсянка солодка', '200 г', 80),
            ((SELECT id FROM categories WHERE name='Сніданки'), 'Вівсянка з яйцем пашот та соусом Голландез', '200 г', 85),
            ((SELECT id FROM categories WHERE name='Салати'), 'Салат крабовий', '150 г', 75),
            ((SELECT id FROM categories WHERE name='Салати'), 'Салат Цезар з куркою', '150 г', 90),
            ((SELECT id FROM categories WHERE name='Салати'), 'Салат овочевий з сиром Фетою', '150 г', 85),
            ((SELECT id FROM categories WHERE name='Салати'), 'Салат із квашеної капусти та огірків', '150 г', 50),
            ((SELECT id FROM categories WHERE name='Перші страви'), 'Борщ з яловичиною', '300 г', 60),
            ((SELECT id FROM categories WHERE name='Перші страви'), 'Солянка', '300 г', 50),
            ((SELECT id FROM categories WHERE name='Перші страви'), 'Мінестроне (овочевий суп)', '200 г', 40),
            ((SELECT id FROM categories WHERE name='Перші страви'), 'Хліб', '3 шт', 10),
            ((SELECT id FROM categories WHERE name='Соус'), 'Кетчуп', NULL, 15),
            ((SELECT id FROM categories WHERE name='Соус'), 'Майонез', NULL, 15),
            ((SELECT id FROM categories WHERE name='Соус'), 'Гірчиця', NULL, 15),
            ((SELECT id FROM categories WHERE name='Соус'), 'Сметана', NULL, 15),
            ((SELECT id FROM categories WHERE name='Соус'), 'Солодкий Чилі', NULL, 15),
            ((SELECT id FROM categories WHERE name='Соус'), 'Барбекю', NULL, 15),
            ((SELECT id FROM categories WHERE name='Соус'), 'Сирний', NULL, 15),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Хамон', NULL, 300),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Оливки', NULL, 150),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Креветки попкорн', 'Хрусткі обсмажені креветки в паніровці', 350),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Начос із сирним соусом', 'Мексиканська закуска з ніжним вершково-сирним соусом', 190),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Антипасти сет', 'Із добірних сирів, хамону та оливок', 320),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Салат із креветкою', 'Мікс свіжих салатів із соковитими креветками', 370),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Салат Цезар', 'Класичний мікс ромену з куркою', 300),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Салат Цезар з креветкою', 'Класичний мікс ромену з креветкою', 380),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Сальморехо', 'Гарячий іспанський суп із томатів', 250),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Паста з креветкою', 'Ніжна паста з соковитими креветками у вершковому соусі', 350),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Паста карбонара', 'Класична італійська паста з беконом', 290),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Темпура суші-бургер', 'Креветка, авокадо, крем-сир', 360),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Сендвіч з рваною яловичиною', 'Рвана яловичина, карамелізований перець і моцарела', 290),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Food Break', 'Картопля фрі з трюфельною пастою та спайсі соусом', 340),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Хот дог класичний', 'Молочна сосиска в булочці бріош. З картоплею фрі', 270),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Бургер із яловичиною', 'Соковита котлета з яловичини у булочці бріош', 380),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Тако з куркою', 'Обсмажене куряче філе з перцем і цибулею', 285),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Тако з креветкою', 'Соковита креветка з перцем і цибулею', 330),
            ((SELECT id FROM categories WHERE name='Рестик'), 'На сніданок', 'Хрусткий тост із вершковим маслом, авокадо, яйцем та беконом', 270),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Пельмені з куркою', 'Подорож до дому', 240),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Млинці зі згущенним молоком та лохиною', 'Подорож до дому', 235),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Нагетси з картоплею фрі', 'Подорож до дому', 290),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Домашні оладки з малиновим варенням', 'Класичні оладки з густим малиновим джемом', 190),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Брауні', NULL, 210),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Морозиво ванільне', NULL, 100),
            ((SELECT id FROM categories WHERE name='Рестик'), 'Чізкейк', NULL, 230)
        ON CONFLICT DO NOTHING
    """)


def downgrade():
    pass
