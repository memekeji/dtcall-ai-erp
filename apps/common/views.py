from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import random
from datetime import datetime

DAILY_QUOTES = [
    {"text": "每一发奋努力的背后，必有加倍的赏赐。", "author": "拿破仑·希尔"},
    {"text": "成功不是将来才有的，而是从决定去做的那一刻起，持续累积而成。", "author": "佚名"},
    {"text": "人生没有彩排，每一天都是现场直播。", "author": "佚名"},
    {"text": "与其临渊羡鱼，不如退而结网。", "author": "佚名"},
    {"text": "昨天的辉煌已过去，今天的奋斗更重要。", "author": "佚名"},
    {"text": "态度决定高度，细节决定成败。", "author": "佚名"},
    {"text": "不为失败找借口，只为成功找方法。", "author": "佚名"},
    {"text": "世界上只有一种英雄主义，就是在认清生活真相之后依然热爱生活。", "author": "罗曼·罗兰"},
    {"text": "人生的价值，并不是用时间，而是用深度去衡量的。", "author": "列夫·托尔斯泰"},
    {"text": "我唯一知道的就是我一无所知。", "author": "苏格拉底"},
    {"text": "成功的关键在于相信自己有成功的能力。", "author": "拿破仑·希尔"},
    {"text": "不要等待机会，而要创造机会。", "author": "佚名"},
    {"text": "你的时间有限，不要浪费于重复别人的生活。", "author": "乔布斯"},
    {"text": "即使是不成熟的尝试，也胜于胎死腹中的策略。", "author": "佚名"},
    {"text": "生活不是等待暴风雨过去，而是学会在雨中跳舞。", "author": "佚名"},
    {"text": "失败只有一种，那就是放弃。", "author": "佚名"},
    {"text": "当你停止尝试的时候，就是你失败的时候。", "author": "佚名"},
    {"text": "没有口水与汗水，就没有成功的泪水。", "author": "佚名"},
    {"text": "目标的坚定是性格中最必要的力量源泉之一。", "author": "佚名"},
    {"text": "人之所以能，是相信能。", "author": "佚名"},
]


@method_decorator(csrf_exempt, name='dispatch')
class DailyQuoteView(View):
    def get(self, request):
        try:
            today = datetime.now().date()
            day_of_year = today.timetuple().tm_yday
            random.seed(day_of_year)
            quote = random.choice(DAILY_QUOTES)
            random.seed()

            return JsonResponse({
                'code': 0,
                'data': {
                    'text': quote['text'],
                    'author': quote['author']
                }
            })
        except Exception as e:
            return JsonResponse({
                'code': 1,
                'msg': str(e)
            })
