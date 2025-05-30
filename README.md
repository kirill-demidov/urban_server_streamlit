# Urban Server Analytics

Приложение для аналитики видео с YouTube, построенное на Streamlit.

## Установка и запуск локально

1. Клонируйте репозиторий:
```bash
git clone <your-repo-url>
cd urban-server-streamlit
```

2. Создайте виртуальное окружение и установите зависимости:
```bash
python -m venv venv
source venv/bin/activate  # для Linux/Mac
# или
.\venv\Scripts\activate  # для Windows
pip install -r requirements.txt
```

3. Настройте конфигурацию:
- Скопируйте `.streamlit/secrets.toml.example` в `.streamlit/secrets.toml`
- Заполните необходимые параметры в `secrets.toml`

4. Запустите приложение:
```bash
streamlit run app.py
```

## Деплой на Streamlit Cloud

1. Создайте репозиторий на GitHub и загрузите код:
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-github-repo-url>
git push -u origin main
```

2. Перейдите на [Streamlit Cloud](https://streamlit.io/cloud)

3. Нажмите "New app" и выберите ваш репозиторий

4. В настройках деплоя:
   - Укажите путь к файлу: `app.py`
   - Добавьте секреты из вашего локального `secrets.toml`

5. Нажмите "Deploy"

## Структура проекта

```
urban-server-streamlit/
├── app.py              # Основной файл приложения
├── requirements.txt    # Зависимости проекта
├── .streamlit/        # Конфигурация Streamlit
│   └── secrets.toml   # Секреты и конфигурация
└── README.md          # Документация
```

## Описание

Проект представляет собой серверное приложение, которое предоставляет функциональность для:
- Поиска видео на YouTube
- Анализа настроений в комментариях
- Обработки аудио и видео контента
- Интеграции с облачными сервисами

## Требования

- Python 3.8+
- FFmpeg (для обработки аудио/видео)
- Доступ к API OpenAI
- Доступ к Google Cloud Storage

## Основные компоненты

- `youtube_search.py` - Поиск видео на YouTube
- `youtube_sentiment_analyzer.py` - Анализ настроений в комментариях
- `cloud.py` - Интеграция с облачными сервисами
- `common.py` - Общие утилиты и функции
- `config.py` - Конфигурация приложения

## Использование

### Поиск видео на YouTube

```python
from youtube_search import get_youtube_search_links, get_video_stats, get_video_comments

# Поиск видео по запросу
videos = get_youtube_search_links("urban heat gameplay", days_ago=30)

# Получение статистики видео
video_stats = get_video_stats("video_id")

# Получение комментариев к видео
comments = get_video_comments("video_id")
```

### Анализ настроений в видео

```python
from youtube_sentiment_analyzer import transcribe_youtube_video, analyze_sentiment_about_product

# Транскрибирование видео
transcript = transcribe_youtube_video("https://www.youtube.com/watch?v=video_id")

# Анализ настроений относительно продукта
sentiments, error = analyze_sentiment_about_product(transcript, "Urban Heat")

# Вывод результатов
if sentiments:
    for sentiment in sentiments:
        print(f"Текст: {sentiment['text']}")
        print(f"Настроение: {sentiment['sentiment']} (уверенность: {sentiment['score']:.2f})")
```

### Работа с облачным хранилищем

```python
from cloud import save_file_bucket

# Сохранение файла в облачное хранилище
save_file_bucket("transcript_video_id.txt", "Содержимое файла")
```

### Запуск анализатора в фоновом режиме

```python
from youtube_sentiment_analyzer import YoutubeTranscript

# Создание и запуск анализатора
analyzer = YoutubeTranscript(
    source="youtube_analyzer",
    code_function="analyze",
    code_period="daily",
    description="Анализ настроений в YouTube видео"
)
analyzer.start()
```

## Лицензия

MIT License

Copyright (c) 2024 Urban Server

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Авторы

[Укажите авторов проекта] 