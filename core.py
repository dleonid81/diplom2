from datetime import datetime
import vk_api
import pprint
from vk_api import ApiError
from config import access_token


class VkTools:
    def __init__(self, access_token):
        self.api = vk_api.VkApi(token=access_token)

    def get_city_id(self, city_name):
        response = self.api.method('database.getCities', {
            'country_id': 1, 'q': city_name, 'need_all': 0, 'count': 1})
        cities = response['items']
        if cities:
            return cities[0]['id']
        else:
            return None

    def get_status(self, user_id):
        text = self.api.method('status.get', {'user_id': user_id})
        return text['text']

    def get_profile_info(self, user_id):
        try:
            info, = self.api.method('users.get', {'user_id': user_id, 'fields': 'city,bdate,sex,relation,home_town'})
        except ApiError as e:
            info = {}
            print(f'error = {e}')

        param = {
            'name': info.get('first_name', '') + ' ' + info.get('last_name', ''),
            'id': info.get('id'),
            'bdate': info.get('bdate'),
            'home_town': info.get('home_town'),
            'sex': info.get('sex'),
            'city': info.get('city', {}).get('id')
        }
        return param

    def search_users(self, params, offset, count, new_sex):
        sex = params.get('sex') or new_sex
        if sex == 1:
            sex = 2
        else:
            sex = 1
        city = params['city']
        curent_year = datetime.now().year
        user_year = int(params['bdate'].split('.')[2])
        age = curent_year - user_year
        age_from = age - 1
        age_to = age + 1
        offset = offset

        try:
            users_found = self.api.method('users.search', {
                'count': count,
                'offset': offset,
                'age_from': age_from,
                'age_to': age_to,
                'sex': sex,
                'city': city,
                'status': 6,
                'is_closed': False,
                'has_photo': 1
                }
                )
            users = users_found['items']
        except KeyError:
            return []
        result = []
        for user in users:
            if user['is_closed'] is False:
                result.append({'id': user['id'],
                               'name': user['first_name'] + ' ' + user['last_name']})
        return result

    def get_photos(self, user_id):
        try:
            photos = self.api.method('photos.get',
                                     {'owner_id': user_id,
                                      'album_id': 'profile',
                                      'extended': 1,

                                      }
                                     )
        except ApiError as e:
            photos = {}
            print(f'error {e}')
            return photos

        result = [{'owner_id': photo['owner_id'],
                   'id': photo['id'],
                   'likes': photo['likes']['count'],
                   'comments': photo['comments']['count']}for photo in photos['items']]
        result.sort(key=lambda x: x['likes'] + x['comments'] * 10, reverse=True)
        return result


if __name__ == '__main__':
    bot = VkTools(access_token)
    params = bot.get_profile_info(554435412)
    users = bot.search_users(params, offset=100, count=50)
    user = users.pop()
    photos = bot.get_photos(user['id'])
    pprint.pprint(params)
