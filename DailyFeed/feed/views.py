from django.shortcuts import render
from django.views import View
from django.views.generic.edit import CreateView
from django.core.cache import cache
from .models import Category, Source, SearchTag
from .forms import SourceForm, FindSourceForm
from .source_builder import get_all_rss, build_category_sources, check_if_source_exists
import requests
import re
import itertools
import feedparser
import newspaper
import time
import datetime
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

        for site in sources:
            site_category_articles = self.scrape_xml_feed(site.link)
            best_articles_grouped.append(site_category_articles)

        best_articles = list(itertools.chain(*best_articles_grouped))
        # random.shuffle(best_articles)
        best_articles = self.delete_duplicate_articles(best_articles)
        best_articles = sorted(best_articles, key=lambda l: l['published'], reverse=True)
        no_of_articles = len(best_articles) - 1
        best_articles = best_articles[:50] or best_articles[:no_of_articles] or []
        best_articles = self.format_entries(best_articles)
        return best_articles

    def scrape_xml_feed(self, source_link):
        print(source_link)
        current_year = datetime.datetime.today().year
        parsed_feed = feedparser.parse(source_link)
        entries = parsed_feed.entries
        if len(entries) > 20:
            entries = self.find_matching_entries(parsed_feed)
        last_entries = entries[:10] or entries[:abs(len(entries) - 1)]
        last_entries = [{'url': e.link,
                         'title': e.title,
                         'summary': re.sub(html_cleaner_regex, ' ', e.summary),
                         'published': e.get('published_parsed') or e.get('updated_parsed', datetime.datetime.now().strftime("%Y-%m-%d")),
                         'website': urlparse(e.link).netloc} for e in last_entries]

        last_entries = [e for e in last_entries if (current_year - e['published'].tm_year <= 1)]
        last_entries = {frozenset(line.items()): line for line in last_entries}.values()
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
            e['published'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', e['published'])[:10]
            if any([e['website'].startswith(url) for url in urls_to_reparse]):
                article = requests.get(e['url'])
                e['website'] = urlparse(article.url).netloc
        return entries

    def delete_duplicate_articles(self, articles):
        unique_articles = []
        unique_paths = set()
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
        # if form.cleaned_data.get('not_rss'):
        #     self.try_parse_website(link)
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

    def try_parse_website(self, link):
        pdb.set_trace()
        news_website = newspaper.build(link)
        news_website.download()
        news_website.parse()
        for line in news_website.articles:
            print(line.title)



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
        return render(request, "source/discovered.html",{"discovered_feeds": discovered_feeds})
# Create your views here.
