import datetime
import vk_api
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
from texts import instraction
from config import community_token, access_token, db_url_object
from core import VkTools
from data import check_user_in_db, add_user

engine = create_engine(db_url_object)
session = Session(engine)


class Interface:

    def __init__(self, community_token, access_token):
        self.vk = vk_api.VkApi(token=community_token)
        self.vk_tools = VkTools(access_token)
        self.longpoll = VkLongPoll(self.vk)
        self.params = {}
        self.worksheets = []
        self.count = 10
        self.offset = 0
        self.keyboard = VkKeyboard(one_time=True)
        self.sex = None

    def fetch_profiles(self):
        if self.sex:
            profiles = self.vk_tools.search_users(self.params, self.offset, self.count, self.sex)
        else:
            profiles = self.vk_tools.search_users(self.params, self.offset, self.count, None)
        self.offset += self.count
        return profiles

    def valid_date(self, bdate):
        try:
            datetime.datetime.strptime(bdate, '%d.%m.%Y')
            return True
        except ValueError:
            return False

    def process_search(self, user_id):
        profiles = []
        if not profiles:
            profiles = self.fetch_profiles()

        not_found_profiles = []

        while not not_found_profiles:
            for profile in profiles:
                if check_user_in_db(engine, self.params['id'], profile['id']):
                    continue
                else:
                    not_found_profiles.append(profile)

            if not not_found_profiles:
                profiles = self.fetch_profiles()

        user = not_found_profiles.pop()
        photos_user = self.vk_tools.get_photos(user['id'])
        user_url = f"https://vk.com/id{user['id']}"
        attachments = []
        for num, photo in enumerate(photos_user[:3]):
            attachments.append(f'photo{photo["owner_id"]}_{photo["id"]}')
            if num == 2:
                break
        status = self.vk_tools.get_status(user['id'])
        self.message_send(user_id,
                          (f'Встречайте {user["name"]}. '
                           f'Профиль: {user_url},\nстатус: {status}'),
                          attachment=','.join(attachments))
        add_user(engine, self.params['id'], user['id'])

    def message_send(self, user_id, message, attachment=None, keyboard=None):
        post = {'user_id': user_id,
                'message': message,
                'attachment': attachment,
                'random_id': get_random_id()
                }

        if keyboard is not None:
            post['keyboard'] = keyboard.get_keyboard()
        self.vk.method('messages.send', post)

    def change_search_params(self, user_id):
        params = self.vk_tools.get_profile_info(user_id)
        all_params_received = True
        for param in params:
            if params[param] is None:
                all_params_received = False
                if param == 'sex':
                    self.message_send(user_id, 'Давайте уточним ваш пол? Ответьте "да" или "нет".')
                    self.user_response(user_id, 'sex')
                    self.fetch_profiles()
                elif param == 'bdate':
                    self.message_send(user_id, 'Давайте изменим дату рождения? Ответьте "да" или "нет".')
                    self.user_response(user_id, 'bdate')
                elif param == 'сity':
                    self.message_send(user_id, 'Изменить город? Ответьте "да" или "нет".')
                    self.user_response(user_id, 'city')
                else:
                    self.message_send(user_id, f'Изменить ваш {param} в поисковых параметрах? Ответьте "да" или "нет".')
                    self.user_response(user_id, param)

        if all_params_received:
            self.message_send(user_id, 'Параметры поиска получены')
            return self.params

    def change_bdate(self, user_id):
        while True:
            for response_event in self.longpoll.listen():
                if (response_event.type == VkEventType.MESSAGE_NEW and response_event.to_me
                        and response_event.user_id == user_id):
                    bdate = response_event.text.lower()
                    if bdate == 'отмена':
                        self.message_send(user_id, 'Отменено изменение параметров поиска.')
                        return  # Выход из метода после отмены команды
                    elif self.valid_date(bdate):
                        self.params['bdate'] = bdate
                        self.message_send(user_id, f"Параметр даты рождения успешно изменен на: {bdate}")
                        self.fetch_profiles()
                        return  # Выход из метода после успешного изменения параметра
                    else:
                        self.message_send(user_id, f"Некорректное значение для даты рождения.\n"
                                                   f"Повторите ввод или отмените команду, написав 'отмена'")
                        break  # Повтор цикла для запроса правильного значения

    def change_city(self, user_id):
        for response_event in self.longpoll.listen():
            if (response_event.type == VkEventType.MESSAGE_NEW and response_event.to_me
                    and response_event.user_id == user_id):
                if response_event.text.lower() == 'отмена':
                    self.message_send(user_id, 'Отменено изменение параметров поиска.')
                    break
                else:
                    city_name = response_event.text
                    if len(city_name) < 2:
                        self.message_send(user_id,
                                          'Слишком короткое название города. '
                                          'Попробуйте еще раз или отмените команду.')
                        return
                    city_id = self.vk_tools.get_city_id(city_name)
                    if city_id:
                        self.params['city'] = city_id
                        self.fetch_profiles()
                        self.message_send(user_id, f"Город успешно изменен на: {city_name}")
                        return
                    else:
                        self.message_send(user_id,
                                          f"Город '{city_name}' не найден. Проверьте правильность "
                                          f"ввода или отмените команду.")
                        break

    def change_sex(self, user_id):
        while True:
            for response_event in self.longpoll.listen():
                if (response_event.type == VkEventType.MESSAGE_NEW and response_event.to_me
                        and response_event.user_id == user_id):
                    new_value = response_event.text.lower()
                    if new_value == 'отмена':
                        self.message_send(user_id, 'Отменено изменение параметров поиска.')
                        return
                    elif new_value in ['1', '2']:
                        self.sex = new_value
                        self.message_send(user_id, f"Параметр пола успешно изменен на: {new_value}")
                        return
                    else:
                        self.message_send(user_id, f"Некорректное значение для пола: {new_value}")
                        break

    def user_response(self, user_id, param):
        while True:
            for event in self.longpoll.listen():
                if event.type == VkEventType.MESSAGE_NEW and event.to_me and event.user_id == user_id:
                    if event.text.lower() == 'да':
                        if param == 'sex':
                            self.message_send(user_id, 'Введите новое значение для пола только число'
                                                       '(1 - женский, 2 - мужской):')
                            self.change_sex(user_id)
                            self.fetch_profiles()
                            return
                        elif param == 'bdate':
                            self.message_send(user_id, 'Введите вашу дату рождения (в формате ДД.ММ.ГГГГ):')
                            self.change_bdate(user_id)
                            return
                        elif param == 'city':
                            self.message_send(user_id, 'Введите название города для поиска: ')
                            self.change_city(user_id)
                            return
                    elif event.text.lower() == 'нет':
                        self.message_send(user_id, f'Параметр {param} остается без изменений.')
                        return
                    elif event.text.lower() == '':
                        self.message_send(user_id, f'Не понял вас, повторите.')
                        break

    def event_handler(self):
        for event in self.longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                command = event.text.lower()
                if command == 'привет':
                    self.keyboard.add_button('поиск', VkKeyboardColor.PRIMARY)
                    self.params = self.vk_tools.get_profile_info(event.user_id)
                    self.change_search_params(event.user_id)
                    self.message_send(event.user_id, f'Здравствуй {self.params["name"]}\n'
                                                     f'Нажмите "поиск" или "инструкция"', self.keyboard)
                elif command == 'поиск':
                    if not self.params:
                        self.params = self.vk_tools.get_profile_info(event.user_id)
                    self.process_search(event.user_id)
                elif command == 'инструкция':
                    self.message_send(event.user_id, instraction)
                elif command == 'пока':
                    self.message_send(event.user_id, 'пока')
                elif command == 'город':
                    self.message_send(event.user_id, 'Хотите сменить город поиска? да/нет')
                    self.user_response(event.user_id, 'city')
                elif command == 'др':
                    self.message_send(event.user_id, 'Хотите сменить дату рождения? да/нет')
                    self.user_response(event.user_id, 'bdate')
                else:
                    self.message_send(event.user_id, 'Неизвестная команда')

if __name__ == '__main__':
    bot = Interface(community_token, access_token)
    bot.event_handler()
