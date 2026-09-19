# 🐧  cat de.py
import ipaddress

# --- НАСТРОЙКИ ---

# 1. Имя входного файла
INPUT_FILE = 'input_proxies.txt'

# 2. Имя выходного файла
OUTPUT_FILE = 'new_lir_proxies.txt'

# 3. Список подсетей "Новый лир" (скопируйте сюда все подсети с картинки)
# Я добавил те, что увидел в описании и вашем примере.
# Вам нужно дописать сюда остальные, если на картинке их больше.
SUBNETS_STR = [
    "185.201.136.0/24",
    "185.201.137.0/24",
    "185.168.28.0/24",
    "185.168.29.0/24",


    "77.95.172.0/24",

    "185.201.138.0/24",
    "185.201.139.0/24",

    "185.168.30.0/24",
    "185.168.31.0/24",

]

# --- ОСНОВНОЙ КОД ---

def main():
    # Преобразуем строки подсетей в объекты IPv4Network для быстрой проверки
    # strict=False позволяет вводить сетевые адреса без ошибок формата
    target_networks = []
    try:
        for sub in SUBNETS_STR:
            target_networks.append(ipaddress.ip_network(sub.strip(), strict=False))
    except ValueError as e:
        print(f"Ошибка в одной из подсетей: {e}")
        return

    print(f"Загружено подсетей для поиска: {len(target_networks)}")
    print(f"Читаем файл: {INPUT_FILE}...")

    found_count = 0
    processed_count = 0

    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f_in, \
             open(OUTPUT_FILE, 'w', encoding='utf-8') as f_out:

            for line in f_in:
                line = line.strip()
                if not line:
                    continue

                processed_count += 1

                # Извлекаем IP (разделяем строку по двоеточию)
                # Формат "IP:PORT", берем первую часть
                parts = line.split(':')
                if len(parts) < 2:
                    continue # Пропускаем строки без порта

                ip_str = parts[0]

                try:
                    ip_obj = ipaddress.ip_address(ip_str)

                    # Проверяем, входит ли IP в одну из целевых подсетей
                    # any() остановится при первом же совпадении (быстро)
                    if any(ip_obj in net for net in target_networks):
                        f_out.write(line + '\n')
                        found_count += 1

                except ValueError:
                    # Если строка не является валидным IP, просто пропускаем
                    continue

        print(f"\nГотово!")
        print(f"Обработано строк: {processed_count}")
        print(f"Найдено совпадений: {found_count}")
        print(f"Результат сохранен в файл: {OUTPUT_FILE}")

    except FileNotFoundError:
        print(f"Ошибка: Файл '{INPUT_FILE}' не найден.")
    except Exception as e:
        print(f"Произошла непредвиденная ошибка: {e}")

if __name__ == "__main__":
    main()
