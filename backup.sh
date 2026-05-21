#!/bin/bash

# Настройки
BACKUP_DIR="/opt/backups"
PROJECT_DIR="/opt/foodbot"
DB_CONTAINER="foodbot-postgres-1"
DB_USER="postgres"
DB_NAME="food_bot"
DATE=$(date +%Y-%m-%d_%H-%M-%S)

# Файлы бэкапа
DB_BACKUP_FILE="${BACKUP_DIR}/db_backup_${DATE}.sql"
ARCHIVE_FILE="${BACKUP_DIR}/foodbot_full_backup_${DATE}.tar.gz"

echo "=== Старт бэкапа: $(date) ==="

# 1. Создаем дамп базы данных из Docker
echo "Создание дампа базы данных..."
docker exec -t ${DB_CONTAINER} pg_dump -U ${DB_USER} ${DB_NAME} > ${DB_BACKUP_FILE}

if [ $? -eq 0 ]; then
    echo "Дамп БД успешно создан: ${DB_BACKUP_FILE}"
else
    echo "Ошибка при создании дампа БД!" >&2
    exit 1
fi

# 2. Архивируем проект, конфиги и дамп БД
echo "Архивация файлов проекта..."
tar -czf ${ARCHIVE_FILE} -C /opt foodbot /var/www/foodbot.site ${DB_BACKUP_FILE}

if [ $? -eq 0 ]; then
    echo "Архив успешно создан: ${ARCHIVE_FILE}"
    # Удаляем промежуточный sql-файл, так как он уже внутри архива
    rm -f ${DB_BACKUP_FILE}
else
    echo "Ошибка архивации файлов!" >&2
    exit 1
fi

# 3. Ротация бэкапов (удаляем файлы старше 7 дней)
echo "Удаление старых бэкапов (старше 7 дней)..."
find ${BACKUP_DIR} -type f -name "foodbot_full_backup_*.tar.gz" -mtime +7 -delete

echo "=== Бэкап завершен успешно: $(date) ==="
