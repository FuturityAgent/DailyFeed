import requests
import itertools
import re
from bs4 import BeautifulSoup
import pdb
from .models import Source, Category


def get_all_rss(website_link):
    rss_list = []
    homepage = requests.get(website_link)
    homepage_soup = BeautifulSoup(homepage.text, 'html.parser')
    homepage_rss_feeds = homepage_soup.findAll(type='application/rss+xml')
    homepage_rss_feeds = homepage_rss_feeds + homepage_soup.findAll('a', {"href": re.compile("^http.*(rss|xml)")})

    homepage_rss_feeds = set([link['href'] for link in homepage_rss_feeds if "video" not in link['href']])
    return homepage_rss_feeds


def build_category_sources(category, rss_feeds):
    rss_feeds = [rss.lower() for rss in rss_feeds]
    tags = [t.name for t in category.search_tags.all()]
    category_feeds = [rss for rss in rss_feeds if any([t in rss for t in tags])]
    category_feeds = [rss for rss in category_feeds if not check_if_source_exists(category, rss)]
    for source in category_feeds:
        new_source = Source(name=source, link=source)
        new_source.save()
        category.sources.add(new_source)


def check_if_source_exists(category, rss_link):
    existing_sources = category.sources.all().filter(link=rss_link)
    return existing_sources.exists()
