import re
import scrapy
from urllib.parse import urljoin
from itemloaders.processors import MapCompose, TakeFirst, Join
from scrapy.loader import ItemLoader


def clean_text(value):
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def clean_phone(value):
    value = clean_text(value)
    value = re.sub(r"(?i)^(phone|tel|telephone)\s*[:\-]?\s*", "", value)
    return value.strip(" ,;|")


def clean_website(value):
    value = clean_text(value)
    value = re.sub(r"(?i)^(website|web site)\s*[:\-]?\s*", "", value)
    return value.strip(" ,;|")


class DelhiChamberSpider(scrapy.Spider):
    name = "delhi_chamber_v2"
    allowed_domains = ["delhichamber.com", "delhichamber.co.in"]
    start_urls = ["http://www.delhichamber.com/Members-List.asp?ALP=All"]

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_TIMEOUT": 60,
        "RETRY_TIMES": 3,
        "CONCURRENT_REQUESTS": 8,
        "FEEDS": {
            "delhi_chamber_clean.csv": {
                "format": "csv",
                "encoding": "utf8",
                "overwrite": True,
            }
        },
    }

    def parse(self, response):
        hrefs = response.xpath(
            '//a[contains(@href, "ListingDetails.asp?MemID=")]/@href'
        ).getall()

        if not hrefs:
            hrefs = response.xpath('//a[contains(@href, "ListingDetails.asp")]/@href').getall()

        seen = set()
        for href in hrefs:
            full_url = urljoin(response.url, href)
            if full_url not in seen:
                seen.add(full_url)
                yield response.follow(full_url, callback=self.parse_detail)

    def parse_detail(self, response):
        loader = ItemLoader(item=dict(), response=response)
        loader.default_input_processor = MapCompose(clean_text)
        loader.default_output_processor = TakeFirst()

        loader.add_value("url", response.url)

        loader.add_value("company_name", self.extract_field(response, ["company name", "name"], prefer_title=True))
        loader.add_value("category", self.extract_field(response, ["category"]))
        loader.add_value("business_type", self.extract_field(response, ["business type", "type of business"]))
        loader.add_value("address", self.extract_field(response, ["address"]))
        loader.add_value("phone", clean_phone(self.extract_field(response, ["phone", "tel", "telephone"])))
        loader.add_value("website", clean_website(self.extract_field(response, ["website", "web site"])))
        loader.add_value("contact_person", self.extract_field(response, ["contact person", "contact person(s)", "contact"]))

        item = loader.load_item()

        for key in ["company_name", "category", "business_type", "address", "phone", "website", "contact_person"]:
            item.setdefault(key, "")

        yield item

    def extract_field(self, response, labels, prefer_title=False):
        for label in labels:
            xpaths = [
                f'//td[contains(translate(normalize-space(.), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "{label}")]/following-sibling::td[1]//text()',
                f'//*[contains(translate(normalize-space(.), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "{label}")]/following-sibling::*[1]//text()',
                f'//b[contains(translate(normalize-space(.), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "{label}")]/following-sibling::text()',
                f'//font[contains(translate(normalize-space(.), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "{label}")]/following-sibling::text()',
            ]
            for xp in xpaths:
                values = response.xpath(xp).getall()
                values = [clean_text(v) for v in values if clean_text(v)]
                if values:
                    return " ".join(values).strip()

        if prefer_title:
            title = response.xpath("//h1/text() | //h2/text() | //title/text()").get()
            if title:
                return clean_text(title)

        return ""
