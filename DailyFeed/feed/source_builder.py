from .models import Source


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
