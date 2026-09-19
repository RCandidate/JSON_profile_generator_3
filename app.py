import json
import random
import os
import re
import requests
from collections import OrderedDict
from flask import Flask, request, jsonify, render_template, Response, stream_with_context

app = Flask(__name__)

# ==============================================================================
# [ ИСПРАВЛЕНИЕ ПОРЯДКА КЛЮЧЕЙ ]
# ==============================================================================
# Запрещаем Flask сортировать ключи JSON по алфавиту при отправке в браузер!
app.config['JSON_SORT_KEYS'] = False

# ==============================================================================
# [ КОНФИГУРАЦИЯ MISTRAL API ]
# ==============================================================================
MISTRAL_MODEL = 'mistral-small-latest'
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"

# Загружаем ключи из файла mistral.txt (одна строка = один ключ)
MISTRAL_KEYS = []
KEYS_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mistral.txt')
if os.path.exists(KEYS_FILE_PATH):
    with open(KEYS_FILE_PATH, 'r', encoding='utf-8') as f:
        MISTRAL_KEYS = [line.strip() for line in f if line.strip()]
else:
    print("ВНИМАНИЕ: Файл mistral.txt не найден. Функции LLM (Mistral) будут отключены.")

# ==============================================================================
# [ КОНФИГУРАЦИЯ LLM7 API ]
# ==============================================================================
LLM7_MODEL = 'mistral-Nemo-Instruct-2407' # Рабочая модель из списка LLM7.io (turbo tier)
LLM7_API_URL = "https://api.llm7.io/v1/chat/completions"

LLM7_KEYS = []
LLM7_KEYS_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'llm7.io.txt')
if os.path.exists(LLM7_KEYS_FILE_PATH):
    with open(LLM7_KEYS_FILE_PATH, 'r', encoding='utf-8') as f:
        LLM7_KEYS = [line.strip() for line in f if line.strip()]
else:
    print("ВНИМАНИЕ: Файл llm7.io.txt не найден. Функции LLM (LLM7) будут отключены.")

# ==============================================================================
# [ КОНФИГУРАЦИЯ ПУТЕЙ ]
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROXY_DIR = os.path.join(BASE_DIR, 'generator', 'proxy')
PROFILE_DIR = os.path.join(BASE_DIR, 'generator', 'profiles')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

# Обязательные поля для валидации шаблона пользователя
REQUIRED_FIELDS = [
    "gender", "age", "interests", "intention",
    "useragent", "resolution"
]

# Стоп-слова для функции усечения intention
SHRINK_STOP_WORDS = {
    "i", "me", "my", "we", "our", "you", "your", "he", "she", "it", "they", "them",
    "is", "are", "am", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might", "shall", "can",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "as", "into", "about",
    "a", "an", "the", "and", "or", "but", "if", "that", "this", "which", "who", "what"
}

# ==============================================================================
# [ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ]
# ==============================================================================

def get_proxy_protocol_by_port(port_str):
    """Определяет протокол прокси (HTTP или SOCKS5) на основе номера порта."""
    try:
        port = int(port_str)
        if port in (8085, 8444):
            return "http://"
        else:
            return "socks5://"
    except ValueError:
        return "socks5://"

def get_first_octet(ip_port_str):
    """Извлекает первый октет IP-адреса для проверки подсети."""
    try:
        return ip_port_str.split(':')[0].split('.')[0]
    except Exception:
        return None

def is_profile_valid(profile):
    """Проверяет наличие всех обязательных полей в шаблоне профиля."""
    if not isinstance(profile, dict):
        return False
    return all(key in profile for key in REQUIRED_FIELDS)

def normalize_gender(profile):
    """Жёсткая логика нормализации пола."""
    gender = profile.get('gender')
    profile['gender'] = 'female' if isinstance(gender, str) and gender.lower() == 'female' else 'male'

def prepare_proxy(raw_proxy):
    """Форматирует строку прокси, добавляя нужный протокол."""
    try:
        ip, port = raw_proxy.split(':')
        return get_proxy_protocol_by_port(port) + raw_proxy
    except ValueError:
        return f"socks5://{raw_proxy}"

def shrink_intention_python(intention):
    """Нативное усечение intention до 2-3 значащих слов средствами Python."""
    if not intention or not isinstance(intention, str):
        return intention

    words = re.findall(r'[a-zA-Z0-9]+', intention.lower())
    meaningful_words = [w for w in words if w not in SHRINK_STOP_WORDS and len(w) > 2]

    if not meaningful_words:
        return intention

    meaningful_words.sort(key=len, reverse=True)
    result_words = meaningful_words[:random.choice([2, 3])]

    final_words = []
    for w in result_words:
        match = re.search(r'\b' + re.escape(w) + r'\b', intention, re.IGNORECASE)
        if match:
            final_words.append(match.group())
        else:
            final_words.append(w)

    return " ".join(final_words)

def generate_dummy_interests(existing_interests, intention, target_count):
    """Нативная (без LLM) генерация фейковых interests."""
    if not existing_interests and not intention:
        return []

    base_words = set()
    for interest in existing_interests:
        words = re.findall(r'[a-zA-Z0-9]{3,}', interest.lower())
        base_words.update(words)

    if intention:
        int_words = re.findall(r'[a-zA-Z0-9]{3,}', intention.lower())
        int_words = [w for w in int_words if w not in SHRINK_STOP_WORDS]
        base_words.update(int_words)

    if not base_words:
        return []

    base_words = list(base_words)

    prefixes = [
        "how to choose ", "best ", "buy ", "list of ", "find ",
        "reviews for ", "top ", "price of ", "compare ", "where to buy ",
        "what is ", "guide to ", "info about ", "best sites to learn ", "rating of platforms to read ", "list of the best "
    ]

    dummies = []
    attempts = 0
    max_attempts = target_count * 5

    while len(dummies) < target_count and attempts < max_attempts:
        attempts += 1
        num_words = random.randint(1, 3)
        chunk = random.sample(base_words, min(num_words, len(base_words)))

        if random.random() < 0.7:
            prefix = random.choice(prefixes)
            dummy = f"{prefix}{' '.join(chunk)}"
        else:
            dummy = " ".join(chunk)

        if dummy not in dummies and dummy not in existing_interests:
            dummies.append(dummy)

    return dummies

def modify_interests_with_llm(intention, interests, llm_provider="llm7"):
    """Отправляет interests и intention в выбранное LLM API (LLM7 или Mistral)."""
    if llm_provider == "mistral":
        if not MISTRAL_KEYS:
            print("Ошибка: Список ключей mistral.txt пуст!")
            return interests, False, "Ошибка: Список ключей mistral.txt пуст!"
        api_url = MISTRAL_API_URL
        model = MISTRAL_MODEL
        keys_to_try = MISTRAL_KEYS * 2 if len(MISTRAL_KEYS) > 1 else MISTRAL_KEYS
    else: # По умолчанию используем LLM7
        if not LLM7_KEYS:
            print("Ошибка: Список ключей llm7.io.txt пуст!")
            return interests, False, "Ошибка: Список ключей llm7.io.txt пуст!"
        api_url = LLM7_API_URL
        model = LLM7_MODEL
        keys_to_try = LLM7_KEYS * 2 if len(LLM7_KEYS) > 1 else LLM7_KEYS

    system_prompt = (
        "You are an SEO and search behavior expert. Your task is to modify a list of user interests "
        "so that they perfectly match the user's specific 'intention' AND look exactly like informational "
        "search engine queries (e.g., starting with 'how to', 'list of', 'best way to', etc.), "
        "rather than just raw keywords or e-commerce categories."
    )

    user_prompt = (
        f"User Intention: {intention}\n"
        f"Original Interests: {json.dumps(interests)}\n\n"
        "Return ONLY a valid JSON array of strings. The number of interests should be 4-5, not more. No markdown, no explanations, just the JSON array."
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7
    }

    attempts_allowed = 2
    last_error = None

    for i, key in enumerate(keys_to_try):
        if i >= attempts_allowed:
            break

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}"
        }

        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()

            content = response.json()['choices'][0]['message']['content'].strip()

            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            modified = json.loads(content)
            if isinstance(modified, list):
                # Успех! Сдвигаем ключи
                if llm_provider == "mistral" and len(MISTRAL_KEYS) > 1:
                    MISTRAL_KEYS.append(MISTRAL_KEYS.pop(0))
                elif llm_provider == "llm7" and len(LLM7_KEYS) > 1:
                    LLM7_KEYS.append(LLM7_KEYS.pop(0))
                return modified, True, None
            else:
                raise ValueError("LLM returned not a list")

        except Exception as e:
            last_error = f"[{llm_provider.upper()}] Key ...{key[-4:]} failed: {e}"
            continue

    fail_msg = f"[{llm_provider.upper()}] All attempts exhausted. Interests kept as is. Last error: {last_error}"
    print(fail_msg)
    return interests, False, fail_msg

# ==============================================================================
# [ WEB-ИНТЕРФЕЙС ]
# ==============================================================================
@app.route('/')
def index():
    """Рендерит главную страницу с выбором файлов и настройками."""
    proxy_files = sorted(
        [f for f in os.listdir(PROXY_DIR) if f.endswith('.txt')]
    ) if os.path.exists(PROXY_DIR) else []

    profile_files = []
    if os.path.exists(PROFILE_DIR):
        for f in sorted(os.listdir(PROFILE_DIR)):
            if f.endswith('.json'):
                display_name = f.replace("profile", "").replace("__", "_").strip("_") or f
                profile_files.append({'value': f, 'name': display_name})

    return render_template('index.html',
                          proxy_files=proxy_files,
                          profile_files=profile_files)

# ==============================================================================
# [ ЭНДПОИНТ СТАТИСТИКИ ]
# ==============================================================================
@app.route('/stats', methods=['POST'])
def stats():
    data = request.get_json(silent=True) or {}
    proxy_file   = data.get('proxy_file', '')
    profile_file = data.get('profile_file', '')

    if not proxy_file or not profile_file:
        return jsonify({"error": "Files not specified"}), 400

    proxy_path = os.path.join(PROXY_DIR, proxy_file)
    if not os.path.exists(proxy_path):
        return jsonify({"error": f"Proxy file not found: {proxy_file}"}), 404
    with open(proxy_path, 'r', encoding='utf-8-sig') as f:
        proxy_count = sum(1 for line in f if line.strip())

    profile_path = os.path.join(PROFILE_DIR, profile_file)
    if not os.path.exists(profile_path):
        return jsonify({"error": f"Profile file not found: {profile_file}"}), 404
    try:
        with open(profile_path, 'r', encoding='utf-8-sig') as f:
            profiles = json.load(f)
        if not isinstance(profiles, list):
            return jsonify({"error": "Profile file must contain a JSON list"}), 400
        valid_count = sum(1 for p in profiles if is_profile_valid(p))
        return jsonify({
            "proxy_count":   proxy_count,
            "profile_total": len(profiles),
            "profile_valid": valid_count,
        })
    except json.JSONDecodeError as e:
        return jsonify({"error": f"JSON error: {e}"}), 400

# ==============================================================================
# [ ОСНОВНОЙ ЭНДПОИНТ ГЕНЕРАЦИИ (SSE STREAMING) ]
# ==============================================================================
@app.route('/generate', methods=['POST'])
def generate():
    """Основной обработчик генерации профилей с потоковой передачей (SSE)."""

    # --- 1. Сбор и валидация входных параметров ---
    if request.is_json:
        data           = request.get_json(silent=True) or {}
        proxy_file     = data.get('proxy_file', '')
        profile_file   = data.get('profile_file', '')
        count_raw      = data.get('count', 0)
        allow_dup      = data.get('allow_dup', False)
        max_reuse      = data.get('max_reuse', 1)
        modify_int     = data.get('modify_interests', False)
        llm_provider   = data.get('llm_provider', 'llm7')
        shrink_int     = data.get('shrink_intention', False)
        limit_int      = data.get('limit_interests', 0)
        dummy_int      = data.get('dummy_interests', 0)
    else:
        proxy_file     = request.form.get('proxy_file', '')
        profile_file   = request.form.get('profile_file', '')
        count_raw      = request.form.get('count', 0)
        allow_dup      = request.form.get('allow_dup', '') == 'true'
        limit_int      = int(request.form.get('limit_interests', 0))
        modify_int     = request.form.get('modify_interests', '') == 'true'
        llm_provider   = request.form.get('llm_provider', 'llm7')
        shrink_int     = request.form.get('shrink_intention', '') == 'true'
        dummy_int      = int(request.form.get('dummy_interests', 0))
        try:
            max_reuse = int(request.form.get('max_reuse', 1))
        except (ValueError, TypeError):
            max_reuse = 1

    try:
        max_profiles = int(count_raw)
        if max_profiles <= 0:
            return jsonify({"error": "Count must be > 0"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Enter an integer"}), 400

    try:
        max_reuse = int(max_reuse)
        if max_reuse < 1:
            max_reuse = 1
    except (ValueError, TypeError):
        max_reuse = 1

    limit_int = max(0, int(limit_int))
    dummy_int = max(0, int(dummy_int))

    # --- 2. Загрузка данных из файлов ---
    proxy_path = os.path.join(PROXY_DIR, proxy_file)
    if not os.path.exists(proxy_path):
        return jsonify({"error": f"Proxy file not found: {proxy_file}"}), 404
    with open(proxy_path, 'r', encoding='utf-8-sig') as f:
        proxies = [line.strip() for line in f if line.strip()]

    profile_path = os.path.join(PROFILE_DIR, profile_file)
    if not os.path.exists(profile_path):
        return jsonify({"error": f"Profile file not found: {profile_file}"}), 404
    try:
        with open(profile_path, 'r', encoding='utf-8-sig') as f:
            profiles_templates = json.load(f)
        if not isinstance(profiles_templates, list):
            return jsonify({"error": "Profile file must contain a JSON list"}), 400
    except json.JSONDecodeError as e:
        return jsonify({"error": f"JSON read error: {e}"}), 400

    if not proxies:
        return jsonify({"error": "Proxy file is zero length"}), 400
    if not profiles_templates:
        return jsonify({"error": "Profile file is empty"}), 400

    # --- 3. Инициализация механизма распределения прокси ---
    random.shuffle(proxies)

    used_proxies = set()
    main_proxies = set()
    backup_usage = {}

    def get_available_proxies(exclude=None):
        exclude = exclude or set()
        return [p for p in proxies if p not in used_proxies and p not in exclude]

    def pick_main_proxy():
        available = get_available_proxies()
        if not available:
            return None
        proxy = available[0]
        used_proxies.add(proxy)
        main_proxies.add(proxy)
        return proxy

    def pick_backup_proxy(exclude_ips, exclude_octet=None):
        available_fresh = get_available_proxies(exclude_ips)

        if exclude_octet is not None:
            available_fresh = [p for p in available_fresh if get_first_octet(p) != exclude_octet]

        if available_fresh:
            proxy = random.choice(available_fresh)
            used_proxies.add(proxy)
            backup_usage[proxy] = 1
            return proxy

        if allow_dup:
            candidates = []
            for p in proxies:
                if p in main_proxies or p in exclude_ips:
                    continue
                if exclude_octet is not None and get_first_octet(p) == exclude_octet:
                    continue
                if backup_usage.get(p, 0) < max_reuse:
                    candidates.append(p)

            if candidates:
                candidates.sort(key=lambda x: backup_usage.get(x, 0))
                slice_size = max(1, len(candidates) // 3)
                pool = candidates[:slice_size]
                proxy = random.choice(pool)
                backup_usage[proxy] = backup_usage.get(proxy, 0) + 1
                return proxy

        fallback_any = get_available_proxies(exclude_ips)
        if fallback_any:
            proxy = random.choice(fallback_any)
            used_proxies.add(proxy)
            backup_usage[proxy] = 1
            return proxy

        return None

    # --- 4. ГЕНЕРАТОР ДЛЯ STREAMING (SSE) ---
    def generate_stream():
        warning_msg = ""
        output_profiles = []
        llm_modified_count = 0

        for i in range(max_profiles):
            main_raw = pick_main_proxy()
            if main_raw is None:
                warning_msg = f"Not enough unique proxies for main. Generated {i} profiles."
                break

            main_octet = get_first_octet(main_raw)
            profile_proxies = {main_raw}
            backup_list = []

            b1_raw = pick_backup_proxy(profile_proxies, exclude_octet=main_octet)
            if b1_raw is not None:
                profile_proxies.add(b1_raw)
                backup_list.append(prepare_proxy(b1_raw))

                b2_raw = pick_backup_proxy(profile_proxies, exclude_octet=main_octet)
                if b2_raw is not None:
                    profile_proxies.add(b2_raw)
                    backup_list.append(prepare_proxy(b2_raw))

            valid_template = None
            for _ in range(100):
                temp = random.choice(profiles_templates)
                if is_profile_valid(temp):
                    valid_template = temp.copy()
                    break

            if not valid_template:
                warning_msg = f"No valid profile templates left. Generated {i} profiles."
                break

            # --- Логика модификации и усечения ---
            if modify_int:
                new_interests, was_modified, err_msg = modify_interests_with_llm(
                    valid_template.get('intention', ''),
                    valid_template.get('interests', []),
                    llm_provider=llm_provider
                )
                valid_template['interests'] = new_interests
                if was_modified:
                    llm_modified_count += 1
                else:
                    # Отправляем лог с ошибкой в консоль браузера
                    log_data = {
                        "type": "log",
                        "level": "err",
                        "text": err_msg
                    }
                    yield f"data: {json.dumps(log_data)}\n\n"

            if shrink_int:
                valid_template['intention'] = shrink_intention_python(valid_template.get('intention', ''))

            current_interests = valid_template.get('interests', [])
            if limit_int > 0 and len(current_interests) > limit_int:
                valid_template['interests'] = current_interests[:limit_int]

            current_interests = valid_template.get('interests', [])
            if dummy_int > 0 and len(current_interests) < dummy_int:
                needed = dummy_int - len(current_interests)
                dummies = generate_dummy_interests(current_interests, valid_template.get('intention', ''), needed)
                valid_template['interests'] = current_interests + dummies

            normalize_gender(valid_template)

            ordered_profile = OrderedDict([
                ("age", valid_template.get('age')),
                ("proxy", prepare_proxy(main_raw)),
                ("backupProxies", backup_list),
            ])

            for key, value in valid_template.items():
                if key not in ordered_profile:
                    ordered_profile[key] = value

            output_profiles.append(ordered_profile)

            # ============ ОТПРАВКА ПРОГРЕССА В БРАУЗЕР ============
            progress_data = {
                "type": "progress",
                "current": i + 1,
                "total": max_profiles
            }
            yield f"data: {json.dumps(progress_data)}\n\n"

        # --- Сохранение результата на сервере ---
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(os.path.join(OUTPUT_DIR, 'output.json'), 'w', encoding='utf-8') as f:
            json.dump(output_profiles, f, indent=2, ensure_ascii=False)

        stats_info = {
            "total_profiles": len(output_profiles),
            "unique_main_proxies": len(main_proxies),
            "backup_usage_stats": dict(sorted(backup_usage.items(), key=lambda x: x[1], reverse=True)[:10]),
            "llm_modified_count": llm_modified_count
        }
        message = warning_msg or f"Successfully generated: {len(output_profiles)} profiles."

        # ============ ОТПРАВКА ФИНАЛЬНОГО РЕЗУЛЬТАТА ============
        final_data = {
            "type": "complete",
            "profiles": output_profiles,
            "message": message,
            "stats": stats_info
        }
        yield f"data: {json.dumps(final_data)}\n\n"

    # Возвращаем потоковый ответ (text/event-stream)
    return Response(stream_with_context(generate_stream()), mimetype='text/event-stream')

# ==============================================================================
# [ ЗАПУСК ПРИЛОЖЕНИЯ ]
# ==============================================================================
if __name__ == "__main__":
    os.makedirs(PROXY_DIR,   exist_ok=True)
    os.makedirs(PROFILE_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR,  exist_ok=True)

    app.run(host="0.0.0.0", port=8182, debug=True)
    