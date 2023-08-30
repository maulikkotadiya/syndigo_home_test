import json
import re

import scrapy
from random_user_agent.user_agent import UserAgent
from random_user_agent.params import SoftwareName, OperatingSystem


def get_useragent():
    software_names = [SoftwareName.CHROME.value]
    operating_systems = [OperatingSystem.WINDOWS.value, OperatingSystem.LINUX.value]
    user_agent_rotator = UserAgent(software_names=software_names, operating_systems=operating_systems, limit=1000)
    return user_agent_rotator.get_random_user_agent()


class TargetCrawlerSpider(scrapy.Spider):
    name = "target_crawler"
    allowed_domains = []
    start_urls = [
        'https://www.target.com/p/-/A-79344798',
        'https://www.target.com/p/-/A-13493042',
        'https://www.target.com/p/-/A-85781566'
    ]

    output = list()


    def start_requests(self):
        for link in self.start_urls:
            headers = {
                "user-agent": get_useragent()
            }
            yield scrapy.Request(
                url=link,
                callback=self.parse,
                headers=headers
            )

    def parse(self, response):
        data = re.findall(r'deepFreeze\(JSON\.parse\((.*?)\)\), writable', response.text)
        product_data = None
        if data:
            data = json.loads(json.loads(data[-1]))

            for query in data["__PRELOADED_QUERIES__"]["queries"]:
                for sub_q in query:
                    if 'product' in sub_q:
                        product_data = sub_q
                        break
                if product_data:
                    break
            if product_data:

                url = product_data["product"]["item"]["enrichment"]["buy_url"]
                tcin = product_data["product"]["tcin"]
                upc = product_data["product"]["item"].get('primary_barcode', '')
                price_amount = product_data["product"]["price"]["current_retail"] if 'current_retail' in product_data["product"]["price"] else product_data["product"]["price"]["current_retail_min"]
                currency = 'USD'
                description = response.xpath('//*[@name="description"]/@content').get('')

                specs = dict()
                for spec in product_data["product"]["item"]["product_description"]["bullet_descriptions"]:
                    specs[spec.split(':')[0].replace('<B>', "").strip()] = spec.split(':')[-1].replace('</B>', "").strip()


                ingredients = []
                ingredients_data = product_data["product"]["item"]["enrichment"]
                if 'nutrition_facts' in ingredients_data:
                    ingredients_data = ingredients_data["nutrition_facts"]["ingredients"]
                    ingredients = ingredients_data.replace('ingredients: ', '').split(',')
                    ingredients = [ing.strip() for ing in ingredients]
                bullets = product_data["product"]["item"]["product_description"]["soft_bullet_description"]
                features = [feature.replace('<B>', "").replace('</B>', "").strip() for feature in product_data["product"]["item"]["product_description"]["bullet_descriptions"]]
                questions = []

                item = dict()
                item["url"] = url
                item["tcin"] = tcin
                item["upc"] = upc
                item["price_amount"] = price_amount
                item["currency"] = currency
                item["description"] = description
                item["specs"] = specs
                item["ingredients"] = ingredients
                item["bullets"] = bullets
                item["features"] = features
                item["questions"] = questions


                questions_url = f'https://r2d2.target.com/ggc/Q&A/v1/question-answer?key=9f36aeafbe60771e321a7cc95a78140772ab3e96&page=0&questionedId={tcin}&type=product&size=100&sortBy=MOST_ANSWERS&errorTag=drax_domain_questions_api_error'
                headers = {
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,ar;q=0.6",
                    "Origin": "https://www.target.com",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
                }
                yield scrapy.Request(
                    url=questions_url,
                    callback=self.parse_questions,
                    headers=headers,
                    meta={
                        'item': item
                    }

                )

    def parse_questions(self, response):
        data = json.loads(response.text)
        item = response.meta['item']
        questions = dict()
        for result in data["results"]:
            questions["question_id"] = result["id"]
            questions["submission_date"] = result["submitted_at"]
            questions["question_summary"] = result["text"]
            questions["user_nickname"] = result["author"].get("nickname", '')
            questions["answers"] = []
            for ans in result["answers"]:
                questions["answers"].append(
                    {
                        'answer_id': ans["id"],
                        'answer_summary': ans["text"],
                        'submission_date': ans["submitted_at"],
                        'user_nickname': ans["author"].get("nickname", '')
                    }
                )
            item['questions'].append(questions)

        self.output.append(item)


    def close(spider, reason):
        with open('target_output.json', 'w') as f:
            f.write(json.dumps(spider.output))
            f.close()



if __name__ == '__main__':
    from scrapy.cmdline import execute
    execute('scrapy crawl target_crawler'.split())
