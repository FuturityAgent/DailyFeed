from django.shortcuts import render
from django.views import View
from django.views.generic.edit import CreateView
from django.core.cache import cache
from django.http import JsonResponse
from .models import Category, Source, SearchTag
from .forms import SourceForm, FindSourceForm, DiscoveredSourceForm
from .source_builder import get_all_rss, build_category_sources, check_if_source_exists
import requests
import re
import itertools
import feedparser
import time
import datetime
import json
from urllib.parse import urlparse
from dateutil.parser import parse
from bs4 import BeautifulSoup
import pdb

html_cleaner_regex = re.compile('<.*?>')


class IndexView(View):
    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        categories = Category.objects.all()
        return render(request, "index.html", {'categories': categories})

class CategoryView(View):
    http_method_names = ['get']

    def get(self, request, id):
        category = Category.objects.get(id=id)
        categories = Category.objects.all()
        all_articles = self.get_articles(category.id)
        return render(request, "category/articles.html", {"articles": all_articles,
                                                          'categories': categories,
                                                          'category': category})

    def get_articles(self, category_id):
        category = Category.objects.get(id=category_id)
        best_articles_grouped = []
        sources = category.sources.all()
        start = time.time()
        # pdb.set_trace()
        for site in sources:
            try_cache = cache.get("cache_{}".format(site.link))
            site_category_articles = try_cache or self.scrape_xml_feed(site.link)
            if not try_cache:
                cache.set("cache_{}".format(site.link), json.dumps(site_category_articles), 10*60)

            if isinstance(site_category_articles, str):
                site_category_articles = json.loads(site_category_articles)

            best_articles_grouped.append(site_category_articles)

        print("MINELO: ", round(time.time() - start, 3))
        best_articles = list(itertools.chain(*best_articles_grouped))
        # random.shuffle(best_articles)
        best_articles = self.delete_duplicate_articles(best_articles)
        for e in best_articles:
            e['published'] = time.struct_time(tuple(e['published'])) if isinstance(e['published'], list) else e['published']
        best_articles = sorted(best_articles, key=lambda l: l['published'], reverse=True)
        no_of_articles = len(best_articles) - 1
        best_articles = best_articles[:50] or best_articles[:no_of_articles] or []
        best_articles = self.format_entries(best_articles)

        print("ZAKONCZONO: ", round(time.time() - start, 3))
        return best_articles

    def scrape_xml_feed(self, source_link):
        print(source_link)
        current_year = datetime.datetime.today().year
        parsed_feed = feedparser.parse(source_link)
        entries = parsed_feed.entries

        if len(entries) > 30:
            entries = self.find_matching_entries(parsed_feed)
        last_entries = entries[:10] or entries[:abs(len(entries) - 1)]
        last_entries = [{'url': getattr(e, 'link', '----'),
                         'title': getattr(e, 'title', '----'),
                         'summary': re.sub(html_cleaner_regex, ' ', getattr(e, 'summary', '-----')),
                         'published': getattr(e, 'published_parsed', False) or getattr(e, 'updated_parsed', datetime.datetime.now().strftime("%Y-%m-%d")),
                         'website': urlparse(getattr(parsed_feed, 'link', getattr(e, 'link',  getattr(parsed_feed, 'href', "unknown")))).netloc
                         } for e in last_entries]

        last_entries = [e for e in last_entries if (current_year - e['published'].tm_year <= 1)]
        # last_entries = {frozenset(line.items()): line for line in last_entries}.values()

        return last_entries

    def find_matching_entries(self, feed):
        all_entries = feed.entries
        category_id = self.kwargs.get('id', None)
        category = Category.objects.get(id=category_id)

        matching_entries = []
        # pdb.set_trace()
        # bytags = self.request.GET.get('bytags', False)

        for e in all_entries:
            # link = e.link.lower() if not bytags else ''
            if any([t.name.lower() in e.summary.lower() for t in category.search_tags.all()]):
                matching_entries.append(e)

        return matching_entries

    def format_entries(self, entries):
        urls_to_reparse = ['feedproxy', 'rss']
        for e in entries:
            # pdb.set_trace()
            # date_published =
            e['published'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', e['published'])[:10]
            if any([e['website'].startswith(url) for url in urls_to_reparse]):
                article = requests.get(e['url'])
                e['website'] = urlparse(article.url).netloc
        return entries

    def delete_duplicate_articles(self, articles):
        unique_articles = []
        unique_paths = set()
        # pdb.set_trace()
        for line in articles:
            url_path = urlparse(line['url']).path
            if url_path in unique_paths:
                continue
            unique_articles.append(line)
            unique_paths.add(url_path)
        return unique_articles


class CategorySourcesView(View):
    http_method_names = ['get']

    def get(self, request, id):
        category = Category.objects.get(id=id)
        categories = Category.objects.all()
        sources = category.sources.all()
        return render(request, "category/sources.html", {'sources': sources,
                                                          'categories': categories,
                                                          'category': category})

class SourceCreateView(CreateView):
    model = Source
    template_name = "category/source_form.html"
    success_url = "/"
    form_class = SourceForm

    def form_valid(self, form):
        response = super(SourceCreateView, self).form_valid(form)
        link = form.cleaned_data.get('link')
        parsed = feedparser.parse(link)
        entries = parsed.entries
        if len(entries) == 0:
            form.add_error('link', "To nie jest feed RSS!")
            return self.form_invalid(form)
        category_id = self.kwargs.get('id', None)
        category = Category.objects.get(id=category_id)
        if check_if_source_exists(category, link):
            form.add_error('link', "Dodawałeś już ten feed dla kategorii {}".format(category.name))
            return self.form_invalid(form)
        category.sources.add(form.instance)
        cache.clear()
        return response




class CategoryCreateView(CreateView):
    model = Category
    template_name = 'category/category_form.html'
    fields = ['name']
    success_url = '/'


class TagCreateView(CreateView):
    model = SearchTag
    template_name = 'tags/searchtag_form.html'
    fields = ['name']
    success_url = '/'

    def form_valid(self, form):
        response = super(TagCreateView, self).form_valid(form)
        category_id = self.kwargs.get('id', None)
        category = Category.objects.get(id=category_id)
        pdb.set_trace()
        cache.clear()
        category.search_tags.add(form.instance)
        return response


class FindSourcesView(View):
    http_method_names = ['get', 'post']

    def get(self, request):
        form = FindSourceForm()
        return render(request, "source/find.html", {"form":form})

    def post(self, request):
        form = FindSourceForm(request.POST)
        discovered_feeds = []
        if form.is_valid():
            link = form.cleaned_data['link']
            discovered_feeds = get_all_rss(link)
            discovered_feeds = self.get_suggested_categories(discovered_feeds)
        # pdb.set_trace()
        form = DiscoveredSourceForm()
        return render(request, "source/discovered.html",{"discovered_feeds": discovered_feeds, 'form': form})

    def get_suggested_categories(self, discovered_feeds):
        """method checks keywords in each feed url, and attach  names of categories which
        matches the url the most
        :argument
        discovered_feeds - list of urls
        :returns
        discovered_feeds_with_categories - list of dictionaries, each contain url of feed and
        list of categories which match the most
        dictionary struct: {'url': url, 'categories': categories}"""
        categories = Category.objects.all()

        categories_tags = {
            cat.name: [t.name for t in cat.search_tags.all()]
            for cat in categories
        }
        discovered_feeds_with_categories = [
            {'url': line, 'categories': []}
            for line in discovered_feeds
        ]
        for feed in discovered_feeds_with_categories:
            categories = self.get_feed_categories(categories_tags, feed)
            feed['categories'] = categories

        return discovered_feeds_with_categories

    def get_feed_categories(self, categories_tags={}, feed=''):
        feed_categories = []
        for key, value in categories_tags.items():
            if self.check_category(value, feed['url']):
                feed_categories.append(key)
        return feed_categories

    def check_category(self, category_tags='', feed=''):
        return any([tag in feed for tag in category_tags])


class AddDiscoveredSourceView(View):
    def get(self, request):
        form = DiscoveredSourceForm()
        return render(request, "source/add_discovered.html", {'form': form})

    def post(self, request):
        form = DiscoveredSourceForm(data=request.POST)

        if form.is_valid():
            # pdb.set_trace()
            source_name = form.cleaned_data.get('name')
            source_url = form.data.get('link')
            category_id = form.cleaned_data.get('category')
            category_obj = form.cleaned_data.get('category')
            new_source = Source(name=source_name, link=source_url)
            new_source.save()
            cache.clear()
            category_obj.sources.add(new_source)

        return JsonResponse({'success': 1})


# Create your views here.
