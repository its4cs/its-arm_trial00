import scrapy
from urllib.parse import urljoin

class DelhiChamberSpider(scrapy.Spider):
    name = "delhi_chamber"
    allowed_domains = ["delhichamber.com", "delhichamber.co.in"]
    start_urls = ["http://www.delhichamber.com/Members-List.asp?ALP=All"]

    custom_settings = {
        "FEED_FORMAT": "csv",
        "FEED_URI": "delhi_chamber_members.csv",
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_TIMEOUT": 60,
        "RETRY_TIMES": 3,
    }

    def parse(self, response):
        links = response.xpath(
            '//a[contains(@href, "ListingDetails.asp?MemID=")]/@href'
        ).getall()

        if not links:
            links = response.xpath(
                '//a[contains(@href, "ListingDetails.asp")]/@href'
            ).getall()

        for href in links:
            yield response.follow(href, callback=self.parse_detail)

    def parse_detail(self, response):
        def clean_text(xpath_expr):
            txt = response.xpath(xpath_expr).get()
            return txt.strip() if txt else ""

        item = {
            "url": response.url,
            "company_name": "",
            "category": "",
            "business_type": "",
            "address": "",
            "phone": "",
            "website": "",
            "contact_person": "",
        }

        text_blocks = response.xpath("//text()").getall()
        full_text = " ".join(t.strip() for t in text_blocks if t.strip())
        full_text = " ".join(full_text.split())

        labels = {
            "company_name": ["company name", "name"],
            "category": ["category"],
            "business_type": ["business type", "type of business"],
            "address": ["address"],
            "phone": ["phone", "tel", "telephone"],
            "website": ["website", "web site"],
            "contact_person": ["contact person", "contact", "contact person(s)"],
        }

        for field, keys in labels.items():
            for key in keys:
                value = self.extract_label_value(response, key)
                if value:
                    item[field] = value
                    break

        if not item["website"]:
            item["website"] = response.xpath('//a[starts-with(@href, "http")]/@href').get(default="").strip()

        if not item["company_name"]:
            h1 = response.xpath("//h1/text() | //h2/text() | //title/text()").get()
            item["company_name"] = h1.strip() if h1 else ""

        yield item

    def extract_label_value(self, response, label):
        xpath_candidates = [
            f'//td[contains(translate(normalize-space(.), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "{label}")]/following-sibling::td[1]//text()',
            f'//*[contains(translate(normalize-space(.), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "{label}")]/following-sibling::*[1]//text()',
        ]

        for xp in xpath_candidates:
            values = response.xpath(xp).getall()
            values = [v.strip() for v in values if v.strip()]
            if values:
                return " ".join(values).strip()
        return ""
