# JSON Profile Generator 3.0

Веб-окружение для генерации профилей (Python/Flask), запускаемое в Docker.

## Запуск через Docker

1. Убедитесь, что у вас созданы нужные папки (`proxy`, `profiles`) и файлы конфигурации.

2. Соберите и запустите контейнер:
   docker-compose up -d --build

3.   По умолчанию приложение поднимается на внутреннем порту 8182.


4. Настройка Reverse Proxy (Angie / Nginx)



Для доступа к приложению извне через виртуальную "папку" (например, http://your-domain.com:8080/generator/) используется веб-сервер Angie.
Пример конфигурации (файл /etc/angie/http.d/your_domain.conf):

server {
    listen 8080;
    server_name tarja.drach.pro;

    # Логи для отладки
    access_log /var/log/angie/tarja.access.log;
    error_log  /var/log/angie/tarja.error.log;

    # Основной маршрут: проксируем всё на Flask приложение
    location / {
        proxy_pass http://127.0.0.1:5000;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 10s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;

        proxy_cache off;
        proxy_store off;
    }

    # Запрет доступа к скрытым файлам
    location ~ /\.ht {
        deny all;
    }

    location /adminer/ {
        proxy_pass http://127.0.0.1:8081/;
    }

    # Основной маршрут к Генератору профилей
    location /generator/ {
        proxy_pass http://127.0.0.1:8182/;

        # Стандартные заголовки для Flask
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Таймауты (генерация может занять время)
        proxy_connect_timeout 10s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # Отключаем кэш
        proxy_cache off;
        proxy_store off;
    }

    # ВАЖНО: Проксирование статики Flask
    # Так как Flask отдает файлы (CSS, JS, иконки) по пути /static/, 
    # а мы зашли через /generator/, браузер запрашивает статику по абсолютному пути.
    # Этот блок перенаправляет статику на порт генератора.
    location /static/ {
        proxy_pass http://127.0.0.1:8182/static/;
    }
}




