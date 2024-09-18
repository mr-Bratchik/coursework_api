import requests
import json
import config
from tqdm import tqdm


class VkAPI:
    API_BASE_URL_VK = 'https://api.vk.com/method'

    # Функция принимает
    def __init__(self, access_token, owner_id):
        self.access_token = access_token
        self.owner_id = owner_id

    def get_common_params(self, album_id=None, extended='1', version_api='5.199'):
        params = {
            'access_token': self.access_token,
            'owner_id': self.owner_id,
            'album_id': album_id or 'profile',
            'extended': extended,
            'v': version_api
        }
        return params

    # Метод для получения словаря с информацией по фотографиям
    def get_photos(self, extended='1', album_id=None, version_api='5.199'):
        params = self.get_common_params(extended=extended, album_id=album_id)
        response = requests.get(f'{self.API_BASE_URL_VK}/photos.get', params=params)
        return response.json()


class YdAPI:

    def __init__(self, access_token):
        self.access_token = access_token

    def get_common_params(self, path=None, url=None):
        params = {}
        if path:
            params['path'] = path
        if url:
            params['url'] = url
        return params

    def get_common_headers(self):
        return {'Authorization': f'OAuth {self.access_token}'}

    # Метод для создания папки на яндекс диске
    def new_folder(self, folder_name):
        try:
            # Проверка есть ли папка с таким названием на яндекс диске
            if self.check_folder_exists(folder_name):
                return f"Папка '{folder_name}' уже существует."

            params = self.get_common_params(path=folder_name)
            headers = self.get_common_headers()
            # Создаем папку на яндекс диске
            response = requests.put('https://cloud-api.yandex.net/v1/disk/resources', headers=headers, params=params)

            if response.status_code == 201:
                return f"Папка '{folder_name}' успешно создана."
        except Exception as e:
            return f'Ошибка: {e}'

    # Метод для проверки наличия папки на яндекс диске
    def check_folder_exists(self, folder_name):
        try:
            params = self.get_common_params(path=folder_name)
            headers = self.get_common_headers()

            response = requests.get('https://cloud-api.yandex.net/v1/disk/resources', headers=headers, params=params)

            if response.status_code == 200:  # папка успешно создана
                return True
            elif response.status_code == 404:  # папка есть на диске
                return False
            else:
                return f'Ошибка при проверке папки: {response.status_code}'
        except Exception as e:
            return f'Ошибка: {e}'

    # Метод для загрузки файлов на яндекс диск
    def upload_files(self, name_file, url_download, folder_name=None):
        try:
            # Путь для файла на яндекс диске
            file_path = f'{folder_name}/{name_file}' if folder_name else name_file

            params = self.get_common_params(path=file_path)
            headers = self.get_common_headers()

            # Получаем ссылку на загрузку
            response = requests.get('https://cloud-api.yandex.net/v1/disk/resources/upload', headers=headers,
                                    params=params)

            if response.status_code == 200:
                upload_url = response.json().get('href')

                # Скачиваем файл с удаленного URL
                download_response = requests.get(url_download, stream=True)
                if download_response.status_code == 200:
                    upload_response = requests.put(upload_url, data=download_response.content)
                    if upload_response.status_code == 201:
                        return f"Файл '{name_file}' успешно загружен."
                    else:
                        return f'Ошибка при загрузке файла: {upload_response.status_code}'
                else:
                    return f'Ошибка при скачивании файла: {download_response.status_code}'
            else:
                return f'Ошибка при получении ссылки на загрузку: {response.status_code}'

        except Exception as e:
            return f'Ошибка: {e}'


# Функция для сортировки фотографий по качеству
def get_top_photos(photos_vk_all, top_n=5):
    if 'error' in photos_vk_all:
        return f"Ошибка VK API: {photos_vk_all['error']['error_msg']}"
    if 'response' not in photos_vk_all or 'items' not in photos_vk_all['response']:
        return 'Не удалось получить фотографии'

    photos_vk = {}
    for p in photos_vk_all['response']['items']:
        if 'sizes' in p:
            max_size = max(p['sizes'], key=lambda size: size['height'] * size['width'])
            photo_resolution = max_size['height'] * max_size['width']
            photos_vk[max_size['url']] = (photo_resolution, p['likes']['count'])

    photos_top_sorted = sorted(photos_vk.items(), key=lambda item: item[1][0], reverse=True)

    photo_top = {}  # Отсортированный словарь
    for number_photo, (url, (resolution, likes)) in enumerate(photos_top_sorted[:top_n], start=1):
        name_file = f'Photo №{number_photo} Like({likes})'
        photo_top[url] = (name_file, resolution)

    return photo_top


# Функция для загрузки фотографий из ВК в яндекс диск
def top_res_photo_vk_upload_in_yd():
    yd_api = YdAPI(access_token=config.ACCESS_TOKEN_YD)
    vk_api = VkAPI(access_token=config.ACCESS_TOKEN_VK, owner_id=config.OWNER_ID)

    name_folder_yd = input('Введите название папки на яндекс диске, в которую загрузить файлы: ')
    try:
        top_n = int(input('Введите число фотографий с наилучшим разрешением (по умолчанию 5): ') or '5')
    except ValueError:
        print('Введите корректное число.')
        return

    # Проверка и создание папки
    folder_creation_status = yd_api.new_folder(name_folder_yd)
    print(folder_creation_status)

    # Получаем словарь с фотографиями из ВК
    photos_vk = vk_api.get_photos(album_id=config.ALBUM_ID, extended='1')
    photos_top = get_top_photos(photos_vk, top_n)

    # Список для сохранения информации о фотографиях и дальнейшего сохранения в json
    photo_info_list = []

    print('Загрузка фотографий на яндекс диск...')
    with tqdm(total=len(photos_top), desc='Загрузка файлов', unit='file') as pbar:
        for url, (name_file, _) in photos_top.items():
            upload_status = yd_api.upload_files(name_file=name_file, url_download=url, folder_name=name_folder_yd)
            photo_info_list.append({"file_name": name_file, "size": _})
            pbar.update(1)

    # Сохранение информации о загруженных фотографиях в json
    with open('photo_info.json', 'w', encoding='utf-8') as f:
        json.dump(photo_info_list, f, ensure_ascii=False)

    print('Загрузка завершена!')


if __name__ == '__main__':
    top_res_photo_vk_upload_in_yd()
