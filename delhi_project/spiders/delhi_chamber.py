import re
import scrapy
from urllib.parse import urljoin
from itemloaders.processors import MapCompose, TakeFirst
from scrapy.loader import ItemLoader


def clean_text(value):
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def clean_phone(value):
    value = clean_text(value)
    value = re.sub(r"(?i)^(phone|tel|telephone|fax)\s*[:\-]?\s*", "", value)
    return value.strip(" ,;|")


def clean_website(value):
    value = clean_text(value)
    value = re.sub(r"(?i)^(website|web site)\s*[:\-]?\s*", "", value)
    value = value.strip(" ,;|")
    value = re.sub(r"^\[|\]$", "", value)
    return value


def clean_contact_person(value):
    value = clean_text(value)
    value = re.sub(r"(?i)^contactperson\(s\)\s*[:\-]?\s*", "", value)
    value = re.sub(r"(?i)^contact person\(s\)\s*[:\-]?\s*", "", value)
    value = re.sub(r"(?i)^contact person\s*[:\-]?\s*", "", value)
    value = re.sub(r"(?i)^contact\s*[:\-]?\s*", "", value)
    value = re.sub(r"(?i)\bthis company is also listed in the following categories\b.*$", "", value)
    return value.strip(" ,;|")


def extract_email(text):
    if not text:
        return ""
    m = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return m.group(0) if m else ""


class DelhiChamberSpider(scrapy.Spider):
    name = "delhi_chamber_v3"
    allowed_domains = ["delhichamber.com", "delhichamber.co.in"]
    start_urls = ["http://www.delhichamber.com/Members-List.asp?ALP=All"]

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_TIMEOUT": 60,
        "RETRY_TIMES": 3,
        "CONCURRENT_REQUESTS": 8,
        "FEEDS": {
            "delhi_chamber_clean_v3.csv": {
                "format": "csv",
                "encoding": "utf8",
                "overwrite": True,
            }
        },
    }

    def parse(self, response):
        hrefs = response.xpath('//a[contains(@href, "ListingDetails.asp?MemID=")]/@href').getall()
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

        page_text = clean_text(" ".join(response.xpath("//text()").getall()))
        page_text = re.sub(r"(?i)this company is also listed in the following categories.*$", "", page_text).strip()

        company_name = self.first_nonempty([
            self.extract_label_value(response, ["company name", "name"]),
            response.xpath("//h1/text() | //h2/text() | //title/text()").get(),
        ])
        loader.add_value("company_name", company_name)

        loader.add_value("category", self.extract_label_value(response, ["category"]))
        loader.add_value("business_type", self.extract_label_value(response, ["business type", "type of business"]))
        loader.add_value("address", self.extract_label_value(response, ["address"]))
        loader.add_value("phone", clean_phone(self.extract_label_value(response, ["phone", "tel", "telephone", "fax"])))
        loader.add_value("website", clean_website(self.extract_label_value(response, ["website", "web site"])))
        loader.add_value("contact_person", clean_contact_person(self.extract_label_value(response, ["contactperson(s)", "contact person(s)", "contact person", "contact"])))

        email = self.extract_email_from_page(response, page_text)
        loader.add_value("email_id", email)

        item = loader.load_item()

        for key in ["company_name", "category", "business_type", "address", "phone", "website", "contact_person", "email_id"]:
            item.setdefault(key, "")

        yield item

    def extract_label_value(self, response, labels):
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
        return ""

    def extract_email_from_page(self, response, page_text):
        email = response.xpath('//a[starts-with(translate(@href,"MAILTO","mailto"), "mailto:")]/@href').get()
        if email:
            email = email.split("mailto:", 1)[1].split("?", 1)[0].strip()
            if email:
                return email

        email = extract_email(page_text)
        return email

    def first_nonempty(self, values):
        for value in values:
            if value:
                value = clean_text(value)
                if value:
                    return value
        return ""
