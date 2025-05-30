import json
import time
import logging
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import warnings
warnings.filterwarnings('ignore', message='file_cache is only supported with oauth2client')

import trafaret_thread
import common
import config

# Отключение логов selenium и chromedriver
os.environ['WDM_LOG_LEVEL'] = '0'  # Отключение логов webdriver-manager
os.environ['WDM_PRINT_FIRST_LINE'] = 'False'  # Отключение приветственного сообщения
logging.getLogger('selenium').setLevel(logging.ERROR)  # Только критические ошибки selenium
logging.getLogger('urllib3').setLevel(logging.ERROR)  # Отключение логирования HTTP-запросов

# Отключение логов googleapiclient
logging.getLogger('googleapiclient').setLevel(logging.ERROR)

# Словарь соответствия ID категорий YouTube их названиям
YOUTUBE_CATEGORIES = {
    '1': 'Фильмы и анимация',
    '2': 'Автомобили и транспорт',
    '10': 'Музыка',
    '15': 'Животные',
    '17': 'Спорт',
    '18': 'Короткометражное кино',
    '19': 'Путешествия и события',
    '20': 'Игры',
    '21': 'Видеоблоги',
    '22': 'Люди и блоги',
    '23': 'Комедия',
    '24': 'Развлечения',
    '25': 'Новости и политика',
    '26': 'Практические советы и стиль',
    '27': 'Образование',
    '28': 'Наука и техника',
    '29': 'Некоммерческие видео и активизм'
}


def get_category_name(category_id):
    """
    Возвращает название категории по её ID

    Args:
        category_id (str): ID категории YouTube

    Returns:
        str: Название категории или "Неизвестная категория", если ID не найден
    """
    return YOUTUBE_CATEGORIES.get(category_id, "Неизвестная категория")


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('youtube_search.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Константы для YouTube API
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
API_KEY = 'wrjCusO0wqXCvMKxwpHCl8OddcKkwr7CtcOFwpbCu8OgwqLDjsKMwrnCnMK9w4vDgcKgwpLCssOnw4jDocK-wpvCrcK2wp7CrMKkfA=='

def get_video_stats(video_id):
    """
    Получает статистику видео через YouTube API
    """
    # logger.info(f"Получение статистики для видео ID: {video_id}")
    try:
        youtube = build(API_SERVICE_NAME, API_VERSION, developerKey=common.decode(config.kirill, API_KEY))

        # Получаем статистику и метаданные видео
        video_response = youtube.videos().list(
            part="statistics,snippet,contentDetails",
            id=video_id
        ).execute()

        if video_response["items"]:
            stats = video_response["items"][0]["statistics"]
            snippet = video_response["items"][0]["snippet"]
            content_details = video_response["items"][0]["contentDetails"]

            category_id = snippet.get("categoryId", "")
            category_name = get_category_name(category_id)

            # logger.info(f"Успешно получена статистика для видео ID: {video_id}")
            # logger.debug(f"Статистика видео: {json.dumps(stats, indent=2)}")
            # print(video_id, stats.get("commentCount", "0"))
            return {
                "likes": stats.get("likeCount", "0"),
                "dislikes": stats.get("dislikeCount", "0"),
                "comments": stats.get("commentCount", "0"),
                "views": stats.get("viewCount", "0"),
                "published_at": snippet.get("publishedAt", ""),
                "channel_id": snippet.get("channelId", ""),
                "channel_title": snippet.get("channelTitle", ""),
                "description": snippet.get("description", ""),
                "tags": snippet.get("tags", []),
                "category_id": snippet.get("categoryId", ""),
                "category_name": category_name,
                "duration": content_details.get("duration", ""),
                "dimension": content_details.get("dimension", ""),
                "definition": content_details.get("definition", ""),
                "caption": content_details.get("caption", "")
            }
    except HttpError as e:
        logger.error(f"Ошибка при получении статистики видео {video_id}: {str(e)}")
    return None


def get_video_comments(video_id):
    """
    Получает все комментарии к видео через YouTube API с постраничной загрузкой
    """
    def make_result():
        # Добавляем комментарии со страницы
        for item in comments_response["items"]:
            comment = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "author": comment["authorDisplayName"],
                "text": comment["textDisplay"],
                "likes": comment["likeCount"],
                "published_at": comment["publishedAt"],
                "updated_at": comment["updatedAt"]
            })

    comments = []
    try:
        youtube = build(API_SERVICE_NAME, API_VERSION, developerKey=common.decode(config.kirill, API_KEY))

        # Начальный запрос
        comments_response = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=100,  # Максимальное количество комментариев на страницу
            textFormat="plainText"
        ).execute()

        # logger.info(f"Получение комментариев для видео ID: {video_id}")
        make_result()

        # Постраничная загрузка всех оставшихся комментариев
        while "nextPageToken" in comments_response:
            next_page_token = comments_response["nextPageToken"]
            # Запрос следующей страницы с комментариями
            comments_response = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=100,
                pageToken=next_page_token,
                textFormat="plainText"
            ).execute()
            make_result()

            # Логирование прогресса загрузки
            # if len(comments) % 100 == 0:
            #     logger.debug(f"Загружено {len(comments)} комментариев для видео {video_id}...")

        logger.info(f"Получено {len(comments)} комментариев для видео ID: {video_id}")

    except HttpError as e:
        # Обработка ошибки, когда комментарии отключены
        if "commentsDisabled" in str(e):
            logger.info(f"Комментарии отключены для видео {video_id}")
        else:
            logger.error(f"Ошибка при получении комментариев для видео {video_id}: {str(e)}")

    return comments

def get_youtube_search_links(search_query, days_ago=None):
    """
    Извлекает ссылки на видео из результатов поиска YouTube с помощью Selenium,
    исключая прямые трансляции

    Args:
        search_query (str): Поисковый запрос
        days_ago (int, optional): Фильтр по количеству дней назад. Если None, то без ограничения по дате
    """
    logger.info(f"Начало поиска видео по запросу: '{search_query}'" +
                (f" за последние {days_ago} дней" if days_ago else ""))

    # Форматируем поисковый запрос для URL
    search_url = f"https://www.youtube.com/results?search_query={search_query.replace(' ', '+')}"

    # Настройка опций Chrome
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Запуск в фоновом режиме
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    # Отключение логов от Chrome
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--log-level=3")  # Уровень ERROR для Chrome
    chrome_options.add_argument('--silent')

    # Перенаправление логов ChromeDriver в никуда на Windows
    if os.name == 'nt':
        chrome_options.add_argument("--log-file=NUL")
    else:
        chrome_options.add_argument("--log-file=/dev/null")

    # Инициализация драйвера
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    # Добавляем скрипт для имитации обычного пользователя

    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    video_ids = []

    try:
        driver.get(search_url)
        # logger.info(f"Открыта страница поиска: {search_url}")

        # Ждем загрузку страницы
        time.sleep(3)
        # logger.debug("Ожидание загрузки страницы (3 секунды)")

        # Скроллинг для загрузки большего количества результатов
        driver.execute_script("window.scrollBy(0, 1000);")
        time.sleep(2)
        # logger.debug("Выполнен скроллинг страницы")

        # Ищем видео напрямую в DOM
        video_elements = driver.find_elements(By.CSS_SELECTOR, "ytd-video-renderer")
        # logger.info(f"Найдено {len(video_elements)} элементов видео")

        if not video_elements:
            # Пробуем альтернативный селектор
            video_elements = driver.find_elements(By.CSS_SELECTOR, "ytd-compact-video-renderer")
            # logger.info(f"Найдено {len(video_elements)} элементов видео (альтернативный селектор)")

        for i, video in enumerate(video_elements, 1):
            try:
                # logger.debug(f"Обработка видео {i}/{len(video_elements)}")

                # Проверяем, не является ли видео прямой трансляцией
                is_live = False

                # Проверка на метку "В ЭФИРЕ" (русская версия)
                try:
                    live_badges = video.find_elements(By.CSS_SELECTOR,
                                                      "span.style-scope.ytd-badge-supported-renderer, span.ytd-video-meta-block, .badge-style-type-live-now")
                    for badge in live_badges:
                        text = badge.text.strip().lower()
                        if "live" in text or "в эфире" in text or "трансляция" in text:
                            is_live = True
                            break
                except:
                    pass

                # Если это прямая трансляция, пропускаем
                if is_live:
                    continue

                title_element = video.find_element(By.CSS_SELECTOR, "h3 a#video-title")
                title = title_element.get_attribute("title")
                url = title_element.get_attribute("href")

                # Дополнительная проверка на "прямую трансляцию" в заголовке видео
                if "live" in title.lower() or "прямая трансляция" in title.lower() or "в эфире" in title.lower():
                    continue

                if url and "watch?v=" in url:
                    video_id = url.split("watch?v=")[1].split("&")[0]
                    # logger.info(f"Обработка видео ID: {video_id}, заголовок: {title}")

                    # Получаем статистику видео через API
                    stats = get_video_stats(video_id)

                    # Проверяем дату публикации, если указан период
                    if days_ago and stats:
                        from datetime import datetime, timezone
                        published_at = datetime.fromisoformat(stats["published_at"].replace('Z', '+00:00'))
                        now = datetime.now(timezone.utc)
                        days_difference = (now - published_at).days

                        if days_difference > days_ago:
                            # logger.info(f"Видео {video_id} пропущено (старше {days_ago} дней)")
                            continue

                    # Получаем комментарии через API
                    comments = get_video_comments(video_id)

                    video_data = {
                        'id': video_id,
                        'title': title,
                        'url': url,
                        'likes': stats["likes"] if stats else "0",
                        'dislikes': stats["dislikes"] if stats else "0",
                        'comments_count': stats["comments"] if stats else "0",
                        'views': stats["views"] if stats else "0",
                        'published_at': stats["published_at"] if stats else "",
                        'channel_id': stats["channel_id"] if stats else "",
                        'channel_title': stats["channel_title"] if stats else "",
                        'description': stats["description"] if stats else "",
                        'tags': stats["tags"] if stats else [],
                        'category_id': stats["category_id"] if stats else "",
                        'category_name': stats["category_name"] if stats else "",
                        'duration': stats["duration"] if stats else "",
                        'dimension': stats["dimension"] if stats else "",
                        'definition': stats["definition"] if stats else "",
                        'caption': stats["caption"] if stats else "",
                        'comments': comments
                    }

                    video_ids.append(video_data)
                    # logger.info(f"Видео {video_id} успешно обработано")
            except Exception as e:
                logger.error(f"Ошибка при обработке видео {i}: {str(e)}")
                continue

    except Exception as e:
        logger.error(f"Произошла ошибка при поиске видео: {str(e)}")
    finally:
        driver.quit()
        logger.info("Драйвер Chrome закрыт")

    # logger.info(f"Поиск завершен. Найдено {len(video_ids)} видео")
    return video_ids


def main():
    search_query = '"Urban Heat" mobile game'
    days_ago = None  # Убираем ограничение по дням
    videos = get_youtube_search_links(search_query, days_ago)

    if videos:
        print(f"\nНайдено {len(videos)} видео по запросу '{search_query}' за последние {days_ago} дней:\n")
        for i, video in enumerate(videos, 1):
            print(f"{i}. {video['title']}")
            print(f"   URL: {video['url']}")
            print(f"   ID: {video['id']}")
            print(f"   Дата публикации: {video['published_at']}")
            print()

        # Сохранение ссылок в файл
        with open('youtube_search_results.txt', 'w', encoding='utf-8') as f:
            for video in videos:
                f.write(f"{video['title']} - {video['url']} (Опубликовано: {video['published_at']})\n")
        print(f"Результаты сохранены в файл 'youtube_search_results.txt'")
    else:
        print("Видео не найдены или произошла ошибка при извлечении данных.")


class YoutubeList(trafaret_thread.TrafaretThread):
    count = 0  # общее количество считанных видео
    count_insert = 0  # количество вставленных видео
    count_update = 0  # количество обновленных видео
    count_comment = 0  # количество комментариев
    count_comment_insert = 0  # количество вставленных комментариев
    count_comment_update = 0  # количество обновленных комментариев
    driver = None
    wait = None

    def __init__(self, source, code_function, code_period, description):
        super(YoutubeList, self).__init__(source, code_function, code_period, description)

    def save_video_to_db(self, video, video_id, token):
        try:
            values = {
                "id_site": video['id'],
                "sh_name": video['title'],
                "url": video['url'],
                "likes": video['likes'],
                "dislikes": video['dislikes'],
                "comments_count": video['comments_count'],
                "views_count": video['views'],
                "published_at": video['published_at'],
                "channel_id": video['channel_id'],
                "channel_title": video['channel_title'],
                "description": video['description'],
                "category_id": video['category_id'],
                "category_name": video['category_name'],
                "duration": video['duration'],
                "dimension": video['dimension'],
                "definition": video['definition'],
                "caption": video['caption']
            }
            if len(video['tags']) > 0:
                values["tags"] = str(video['tags'])

            # проверяем, есть ли уже это видео в БД
            ans, is_ok, _ = common.send_rest(
                "v2/select/{schema}/nsi_list?where=id_site='{video_id}'".format(
                    schema=config.schema_name, video_id=video['id']))

            if not is_ok:
                logger.error(f"Ошибка при проверке видео в БД: {ans}")
                self.finish_text = 'Ошибка при получении списка видео для загрузки\n' + str(ans)
                return False
            ans = json.loads(ans)
            if len(ans) == 0:
                # logger.info(f"Добавление нового видео в БД: {video['id']}")
                self.count_insert += 1
                values["need_reload"] = 'true'
                values["at_date_time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
            else:
                if common.compare_specific_keys(
                        ans[0], values,
                        ["sh_name", "url", "likes", "dislikes", "comments_count", "views_count",
                         "channel_id", "channel_title", "category_id", "category_name", "description",
                         "duration", "dimension", "definition", "tags"]):
                    # logger.info(f"Видео {video['id']} уже существует в БД")
                    return True
                # logger.info(f"Коррекция видео в БД: {video['id']}")
                values['id'] = ans[0]['id']  # и это будет коррекция (может быть лайки поменялись)
                self.count_update += 1


            params = {
                "schema_name": config.schema_name,
                "object_code": "list",
                "values": values,
            }

            # коррекция или добавление видео в БД
            ans, is_ok, _ = common.send_rest('v2/entity', 'PUT', params=params, token_user=token)

            if is_ok:
                # logger.info(f"Видео {video['id']} успешно зафиксировано в БД")
                pass
            else:
                logger.error(f"Ошибка при фиксации видео в БД: {ans}")
                self.finish_text = 'Ошибка при фиксации видео в БД\n' + str(ans)
                return False
            return True
        except Exception as er:
            logger.error(f"Ошибка при сохранении видео {video_id}: {str(er)}")

    def save_comments_to_db(self, video_id, comments, token):
        """
        Сохраняет комментарии в базу данных
        """
        for i, comment in enumerate(comments, 1):
            self.count_comment += 1
            values = {
                "video_id": video_id,
                "sh_name": comment["author"],
                "text": comment['text'],
                "likes": comment["likes"],
                "published_at": comment["published_at"],
                "updated_at": comment["updated_at"]
            }
            # Проверяем, что комментарий уже существует в базе данных по полям video_id и published_at
            ans, is_ok, _ = common.send_rest(
                "v2/select/{schema}/nsi_comments?where=video_id='{video_id}' and published_at='{published_at}'".format(
                    schema=config.schema_name, video_id=video_id, published_at=comment["published_at"]))
            if not is_ok:
                logger.error(f"Ошибка при проверке комментария в БД: {ans}")
                return False
            ans = json.loads(ans)

            if len(ans) > 0:  # Комментарий уже существует
                if common.compare_specific_keys(
                        ans[0], values,["sh_name", "text", "likes"]):
                    # logger.info(f"Комментарий для {video['id']} с публикацией {values['published_at]} уже существует в БД")
                    continue
                values['id'] = ans[0]['id']  # и это будет коррекция (может быть лайки поменялись)
                self.count_comment_update += 1
            else:  # Комментарий новый
                self.count_comment_insert += 1

            try:
                datas = comment['text']
                values['size_comment'] = len(comment['text'])
                values['text'] = '%s'
                params = {
                    "schema_name": config.schema_name,
                    "object_code": "comments",
                    "values": values,
                    "datas": datas
                }

                ans, is_ok, _ = common.send_rest('v2/entity', 'PUT', params=params, token_user=token)
                if not is_ok:
                    logger.error(f"Ошибка при сохранении комментария {i} для видео {video_id}: {ans}")
                    return False
                # logger.debug(f"Сохранен комментарий {i}/{len(comments)} для видео {video_id}")
            except Exception as e:
                logger.error(f"Ошибка при сохранении комментария {i} для видео {video_id}: {str(e)}")
                return False
        # logger.info(f"Успешно сохранены все комментарии для видео ID: {video_id}")
        return True

    def work(self):
        # logger.info("Начало работы потока YoutubeList")
        super(YoutubeList, self).work()
        if common.get_value_config_param('active', self.par) != 1:
            # logger.warning("Сервис неактивен")
            return False
        # прочитать нужные для работы параметры
        # получить токен для записи в БД
        result = self.make_login()
        self.count, self.count_insert, self.count_update = 0, 0, 0
        self.count_comment, self.count_comment_insert, self.count_comment_update = 0, 0, 0
        if result:
            # logger.info("Успешная авторизация")
            common.write_log_db(
                'Start', self.source, 'Начало работы по опросу списка публикаций на youtube',
                file_name=common.get_computer_name(), token=self.token)
            search_query = '"Urban Heat" mobile game'
            days_ago = None  # Убираем ограничение по дням
            # logger.info(f"Начало поиска видео по запросу: '{search_query}' за последние {days_ago} дней")

            videos = get_youtube_search_links(search_query, days_ago)
            if videos:
                self.count = 0
                logger.info(f"Найдено {len(videos)} видео")
                for i, video in enumerate(videos, 1):
                    self.count += 1
                    if self.save_video_to_db(video, video['id'], self.token):
                        pass
                    else:
                        logger.error(f"Ошибка при сохранении видео {video['id']}")
                    # Сохранение комментариев в БД
                    if video['comments']:
                        logger.info(f" {i} Сохранение {len(video['comments'])} комментариев для видео ID: {video['id']}")
                        if self.save_comments_to_db(video['id'], video['comments'], self.token):
                            pass
                            # logger.info(f"Комментарии для видео {video['id']} успешно сохранены")
                        else:
                            logger.error(f"Ошибка при сохранении комментариев для видео {video['id']}")

                self.finish_text = f'Считано видео {len(videos)}\n' \
                                   f'   новых {self.count_insert}, обновлено {self.count_update}\n' \
                                   f'Считано комментариев {self.count_comment}\n'\
                                   f'   новых {self.count_comment_insert}, обновлено {self.count_comment_update}'
                # logger.info(self.finish_text)
            else:
                self.finish_text = "Видео не найдены или произошла ошибка при извлечении данных."
                logger.warning(self.finish_text)
                result = False
        else:
            logger.error("Ошибка авторизации")
        return result


# if __name__ == "__main__":
#     main()

if __name__ == "__main__":
    YoutubeList('YoutubeList', 'youtube_list', 'period',
                "Поток 'Определение списка ссылок на youtube' по игре URBAN HEAT").start()
    while True:
        time.sleep(5)