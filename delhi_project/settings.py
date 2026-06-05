BOT_NAME = "delhi_project"

SPIDER_MODULES = ["delhi_project.spiders"]
NEWSPIDER_MODULE = "delhi_project.spiders"

ROBOTSTXT_OBEY = False

FEEDS = {
    "items.csv": {
        "format": "csv",
        "overwrite": True,
    }
}
