import socket
import time
import json
import base64

import requests
from requests.exceptions import HTTPError

import config


def get_value_config_param(key, par):
    for unit in par:
        if unit['code'] == key:
            if 'is_number' not in unit or unit['is_number']:
                return int(unit['value']) if unit['value'] is not None else 0
            return unit['value']
    return None


def get_difference(caption, value_old, value):
    if value != value_old:
        return caption + ': ' + str(value_old) + ' -> ' + str(value) + '; \n'
    else:
        return ''


def get_param_work(caption, value):
    return caption + ': ' + str(value) + '; \n'


def get_difference_config_params(par, answer):
    st_difference = ''
    st_param_work = ''
    for data in par:
        for unit in answer:
            if unit['code'] == data['code']:
                data['is_number'] = unit['is_number']
                if data['value'] != unit['value']:
                    st_difference += get_difference(unit['sh_name'], data['value'], unit['value'])
                data['value'] = unit['value']
                st_param_work += get_param_work(unit['sh_name'], unit['value'])
                break
    return st_difference, st_param_work


def load_config_params(name_function):
    url = "v1/select/{schema}/v_nsi_functions_params?where=name_function='{name_function}'".format(
        schema=config.schema_name, name_function=name_function)
    answer, is_ok, status_code = send_rest(url)
    if is_ok:
        answer = json.loads(answer)
        return answer
    return []


def get_computer_name():
    st = socket.gethostbyname(socket.gethostname())
    st = '' if st == '127.0.0.1' else st
    return socket.gethostname() + '; ' + st


def write_log_db(level, src, msg, page=None, file_name='', law_id='', td=None, write_to_db=True,
                         write_to_console=True, token=None):
    """
    Логирует сообщение в консоль и/или базу данных.

    Args:
        level (str): Уровень логирования (например, ERROR, INFO).
        src (str): Источник сообщения.
        msg (str): Текст сообщения.
        page (str, optional): Номер страницы (если применимо).
        file_name (str, optional): Имя файла (если применимо).
        law_id (str, optional): Идентификатор закона (если применимо).
        td (float, optional): Длительность операции в секундах.
        write_to_db (bool): Логировать ли в базу данных.
        write_to_console (bool): Логировать ли в консоль.
        token (str, optional): Токен для авторизации.
    """
    # Формируем части сообщения
    st_td = f"td={td:.1f} sec;" if td else ''
    st_file_name = f"file={file_name};" if file_name else ''
    st_law_id = f"law_id={law_id};" if law_id else ''
    st_page = f"page={page};" if page else ''

    # Логирование в консоль
    if write_to_console:
        print(f"{time.asctime(time.gmtime())}: {level}; {src}; {st_td} {st_page} {st_law_id} ",
              st_file_name.replace('\n', ''), msg.replace('\m', ''), flush=True)

    # Если логирование в базу данных не требуется
    if not write_to_db:
        return

    # Получение токена, если он не передан
    answer = ''
    if token is None:
        answer, is_ok, token, _ = login_admin()
    else:
        is_ok = True

    # Логирование в базу данных
    if is_ok:
        page = page or 'NULL'
        law_id = law_id or ''
        file_name = file_name or ''
        td = 'NULL' if td is None else f"{td:.1f}"
        query = f"select {config.schema_name}.pw_logs('{level}', '{src}', %s, {page}, '{law_id}', %s, {td})"
        params = {"script": query, "datas": f"{msg}~~~{file_name}"}
        answer, is_ok, _ = send_rest('v2/execute', 'PUT', params=params, lang=config.app_lang, token_user=token)

        if not is_ok:
            print(f"{time.ctime()} ERROR write_log_db {answer}", flush=True)
    else:
        print(f"{time.ctime()} ERROR write_log_db {answer}", flush=True)


def decode(key, enc):
    # раскодировать
    dec = []
    enc = base64.urlsafe_b64decode(enc).decode()
    for i in range(len(enc)):
        key_c = key[i % len(key)]
        dec_c = chr((256 + ord(enc[i]) - ord(key_c)) % 256)
        dec.append(dec_c)
    return "".join(dec)


def encode(key, text):
    enc = []
    for i in range(len(text)):
        key_c = key[i % len(key)]
        enc_c = chr((ord(text[i]) + ord(key_c)) % 256)
        enc.append(enc_c)
    return base64.urlsafe_b64encode("".join(enc).encode()).decode()


def login_admin():
    result = False
    token_admin = ''
    lang_admin = ''
    txt_z = {"login": "superadmin", "password": decode('abcd', config.kirill), "rememberMe": True}
    try:
        headers = {"Accept": "application/json"}
        response = requests.request(
            'POST', config.URL + 'v1/login', headers=headers,
            json={"params": txt_z}
            )
    except HTTPError as err:
        txt = f'HTTP error occurred: {err}'
    except Exception as err:
        txt = f'Other error occurred: : {err}'
    else:
        try:
            txt = response.text
            result = response.ok
            if result:
                js = json.loads(txt)
                if "accessToken" in js:
                    token_admin = js["accessToken"]
                if 'lang' in js:
                    lang_admin = js['lang']
            else:
                token = None
                return txt, result, token
        except Exception as err:
            txt = f'Error occurred: : {err}'
    return txt, result, token_admin, lang_admin


def send_rest(mes, directive="GET", params=None, lang='', token_user=None):
    js = {}
    if token_user is not None:
        js['token'] = token_user
    if lang == '':
        lang = config.app_lang
    if directive == 'GET' and 'lang=' not in mes:
        if '?' in mes:
            mes = mes + '&lang=' + lang
        else:
            mes = mes + '?lang=' + lang
    else:
        js['lang'] = lang   # код языка пользователя
    if params:
        if type(params) is not str:
            params = json.dumps(params, ensure_ascii=False)
        js['params'] = params  # дополнительно заданные параметры
    try:
        headers = {"Accept": "application/json"}
        response = requests.request(directive, config.URL + mes.replace(' ', '+'), headers=headers, json=js)
    except HTTPError as err:
        txt = f'HTTP error occurred: {err}'
        return txt, False, None
    except Exception as err:
        txt = f'Other error occurred: {err}'
        return txt, False, None
    else:
        return response.text, response.ok, '<' + str(response.status_code) + '> - ' + response.reason


def get_duration(td):
    """
    Преобразует длительность в секундах в строку формата "дни часы:минуты:секунды".

    Args:
        td (float or int): Длительность в секундах. Может быть None.

    Returns:
        str: Строка, представляющая длительность в формате:
             - "< 0.5 sec", если длительность меньше 0.5 секунды.
             - "X days HH:MM:SS", если длительность включает дни.
             - "HH:MM:SS", если длительность не включает дни.
             - Пустая строка, если входное значение None.
    """
    if td is None:
        return ''  # Возвращает пустую строку, если длительность не задана.
    if '<' in str(td):
        return f"{td} sec"  # Возвращает строку с символом "<", если он есть в значении.

    # Округляем длительность до ближайшего целого числа.
    tdr = int(td + 0.5)
    if tdr == 0:
        return '< 0.5 sec'  # Возвращает "< 0.5 sec", если длительность меньше 0.5 секунды.

    # Вычисляем количество дней, часов, минут и секунд.
    days = tdr // 86400  # Количество дней.
    tdr %= 86400
    hours = tdr // 3600  # Количество часов.
    minutes = (tdr % 3600) // 60  # Количество минут.
    seconds = tdr % 60  # Количество секунд.

    # Формируем строку результата.
    result = f"{days} day{'s' if days != 1 else ''}" if days else ''  # Добавляем дни, если они есть.
    if hours or result:
        # Добавляем часы, минуты и секунды, если есть дни или часы.
        result += f" {hours:02}:{minutes:02}:{seconds:02}"
    else:
        # Если дней нет, добавляем только минуты и секунды.
        result = f"{minutes:02}:{seconds:02}"

    return result  # Возвращаем строку с длительностью.


def compare_specific_keys(dict1, dict2, keys_to_compare):
    """Сравнивает только указанные ключи в словарях"""
    for key in keys_to_compare:
        if key not in dict1 or key not in dict2:
            return False
        if str(dict1[key]) != str(dict2[key]):
            return False
    return True