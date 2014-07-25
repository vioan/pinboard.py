import datetime
import json
import operator
import urllib
import urllib2

PINBOARD_API_ENDPOINT = "https://api.pinboard.in/v1/"
PINBOARD_DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

class Bookmark(object):
    def __init__(self, payload, token):
        self.description = payload['description']
        self.extended = payload['extended']
        self.url = payload['href']
        self.meta = payload['meta']
        self.hash = payload['hash']
        self.shared = payload['shared'] == "yes"
        self.toread = payload['toread'] == "yes"
        self.tags = payload['tags'].split(' ')
        self.time = Pinboard.datetime_from_string(payload['time'])
        self.token = token

    @property
    def pinboard(self):
        return Pinboard(self.token)

    def __repr__(self):
        parse_result = urllib2.urlparse.urlparse(self.url)
        return "<Bookmark description=\"{}\" url=\"{}\">".format(self.description.encode("utf-8"), parse_result.netloc)

    def save(self, update_time=False):
        params = {
            'url': self.url,
            'description': self.description,
            'extended': self.extended,
            'tags': self.tags,
            'shared': "yes" if self.shared else "no",
            'toread': "yes" if self.toread else "no",
        }

        if update_time:
            params['dt'] = self.time

        return self.pinboard.posts.add(**params)

    def delete(self):
        return self.pinboard.posts.delete(url=self.url)


class Tag(object):
    def __init__(self, key, value):
        self.name = key
        self.count = int(value)

    def __repr__(self):
        return "<Tag name=\"{}\" count={}>".format(self.name, self.count)


class Pinboard(object):
    DATE_FIELDS = ["dt", "date", "update_time"]
    BOOLEAN_FIELDS = ["meta", "replace", "shared", "toread"]
    SPACE_DELIMITED_FIELDS = ["tag", "tags"]

    def __init__(self, token):
        self.token = token

    def __getattr__(self, k):
        return PinboardCall(self.token, k)

    @staticmethod
    def datetime_from_string(value):
        return datetime.datetime.strptime(value, PINBOARD_DATE_FORMAT)

    @staticmethod
    def string_from_datetime(dt):
        return dt.strftime(PINBOARD_DATE_FORMAT)


class PinboardCall(object):
    def __init__(self, token, path):
        self.token = token
        self.components = [path]

    def __getattr__(self, k):
        self.components.append(k)
        return self

    def __call__(self, *args, **kwargs):
        url = "{}{}".format(PINBOARD_API_ENDPOINT, "/".join(self.components))

        parse_response = kwargs.get('parse_response', True)

        params = kwargs.copy()

        if 'parse_response' in params:
            del params['parse_response']

        for field in Pinboard.DATE_FIELDS:
            if field in kwargs:
                try:
                    params[field] = Pinboard.string_from_datetime(kwargs[field])
                except:
                    params[field] = kwargs[field]

        for field in Pinboard.BOOLEAN_FIELDS:
            if field in kwargs:
                if isinstance(kwargs[field], bool):
                    params[field] = "yes" if kwargs[field] else "no"
                else:
                    params[field] = kwargs[field]

        for field in Pinboard.SPACE_DELIMITED_FIELDS:
            if field in kwargs:
                if isinstance(kwargs[field], list):
                    params[field] = ' '.join(kwargs[field])
                else:
                    params[field] = kwargs[field]

        params['format'] = "json"
        params['auth_token'] = self.token

        query_string = urllib.urlencode(params)

        url = "{}?{}".format(url, query_string)

        request = urllib2.Request(url)

        opener = urllib2.build_opener(urllib2.HTTPSHandler)
        response = opener.open(request)

        if parse_response:
            json_response = json.load(response)

            for field in Pinboard.DATE_FIELDS:
                if field in json_response:
                    json_response[field] = Pinboard.datetime_from_string(json_response[field])

            if self.components == ["posts", "all"]:
                return map(lambda k: Bookmark(k, self.token), json_response)
            elif self.components in [["posts", "get"], ["posts", "recent"]]:
                json_response['posts'] = map(lambda k: Bookmark(k, self.token), json_response['posts'])
            elif self.components == ["posts", "dates"]:
                json_response['dates'] = {datetime.datetime.strptime(k, "%Y-%m-%d").date(): int(v) \
                        for k, v in json_response['dates'].iteritems()}
            elif self.components == ["tags", "get"]:
                tags = [Tag(k, v) for k, v in json_response.iteritems()]
                tags.sort(key=operator.attrgetter('name'))
                return tags

            return json_response
        else:
            return response

