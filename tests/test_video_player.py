import unittest
from urllib.parse import parse_qs, urlsplit

from tools.vip_parser import ROUTES, playback_target, parser_target


class PlaybackTargetTests(unittest.TestCase):
    def test_verified_route_is_default(self):
        self.assertEqual(urlsplit(parser_target('https://v.qq.com/x/page/p0020fdo3so.html', 0)).hostname, 'jx.xmflv.cc')

    def test_broken_routes_are_removed(self):
        hosts = {urlsplit(route[1]).hostname for route in ROUTES}
        self.assertNotIn('www.1717yun.com', hosts)
        self.assertNotIn('yparse.jn1.cc', hosts)

    def test_parser_keeps_full_video_url_as_one_parameter(self):
        video = 'https://v.qq.com/x/cover/uo1l1j78851me7b/p0020fdo3so.html?a=1&b=2'
        for route in range(len(ROUTES)):
            target = urlsplit(parser_target(video, route))
            self.assertEqual(parse_qs(target.query), {'url': [video]})

    def test_parser_requires_link_and_known_route(self):
        for value, route in [('斗罗大陆', 0), ('file:///C:/test', 0), ('https://v.qq.com/', -1), ('https://v.qq.com/', len(ROUTES))]:
            with self.subTest(value=value, route=route), self.assertRaises(ValueError):
                parser_target(value, route)

    def test_video_link_preserves_query(self):
        url = 'https://v.youku.com/v_show/id_abc==.html?a=1&b=2'
        self.assertEqual(playback_target('  ' + url + '  '), url)

    def test_search_encodes_keyword(self):
        target = urlsplit(playback_target('斗罗大陆 & 电影'))
        self.assertEqual(target.hostname, 'v.qq.com')
        self.assertEqual(parse_qs(target.query), {'q': ['斗罗大陆 & 电影']})

    def test_rejects_empty_or_non_web_link(self):
        for value in (' ', 'file:///C:/test', 'javascript:alert(1)', 'https://'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                playback_target(value)
