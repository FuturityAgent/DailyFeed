from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import TemplateView
from django.views.generic.edit import CreateView, DeleteView
from django.core.cache import cache
from django.urls import reverse_lazy
from django.http import JsonResponse
from .models import Category, Source, SearchTag
from .forms import SourceForm, FindSourceForm, DiscoveredSourceForm, SearchTagForm, TagFormset
from .source_builder import check_if_source_exists
import requests
import re
import itertools
import feedparser
from bs4 import BeautifulSoup
import time
import datetime
import json
from urllib.parse import urlparse
import random

html_cleaner_regex = re.compile('<.*?>')


class GeneralView(TemplateView):

    def get_context_data(self, **kwargs):
        context = super(GeneralView, self).get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context


class IndexView(GeneralView):
    http_method_names = ['get']
    template_name = "index.html"

class CategoryView(GeneralView):
    http_method_names = ['get']
    template_name = "category/articles.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = Category.objects.get(id=kwargs['id'])
        all_articles = self.get_articles(category.id)
        context['category'] = category
        context['no_of_sources'] = category.sources.count()
        context['articles'] = all_articles
        return context

    def get_articles(self, category_id):
        category = Category.objects.get(id=category_id)
        best_articles_grouped = []
        sources = category.sources.all()
        start = time.time()
        for site in sources:
            try_cache = cache.get("cache_{}".format(site.link))
            site_category_articles = try_cache or self.scrape_xml_feed(site.link)
            if not try_cache:
                cache.set("cache_{}".format(site.link), json.dumps(site_category_articles), 5*60)

            if isinstance(site_category_articles, str):
                site_category_articles = json.loads(site_category_articles)
            try_cache_formatted = cache.get("formatted_{}".format(site.link))

            site_category_articles = try_cache_formatted or self.format_entries(site_category_articles)
            if not try_cache_formatted:
                cache.set("formatted_{}".format(site.link), json.dumps(site_category_articles), 10 * 60)
            if isinstance(site_category_articles, str):
                site_category_articles = json.loads(site_category_articles)
            best_articles_grouped.append(site_category_articles)

        print("MINELO: ", round(time.time() - start, 3))
        best_articles = list(itertools.chain(*best_articles_grouped))
        best_articles = self.delete_duplicate_articles(best_articles)
        best_articles = sorted(best_articles, key=lambda l: l['published'], reverse=True)
        no_of_articles = len(best_articles) - 1
        best_articles = best_articles[:50] or best_articles[:no_of_articles] or []
        best_articles = self.make_date_clear(best_articles)

        print("ZAKONCZONO: ", round(time.time() - start, 3))
        return best_articles

    def scrape_xml_feed(self, source_link):
        print(source_link)
        current_year = datetime.datetime.today().year
        parsed_feed = feedparser.parse(source_link)
        entries = parsed_feed.entries
        entries = self.find_matching_entries(entries)
        last_entries = entries[:20] or entries[:abs(len(entries) - 1)]
        last_entries = [
                        {'url': getattr(e, 'link', '----'),
                         'title': getattr(e, 'title', '----'),
                         'summary': re.sub(html_cleaner_regex, ' ', getattr(e, 'summary', '-----')),
                         'published': time.struct_time(getattr(e, 'published_parsed', False) or getattr(e, 'updated_parsed', datetime.datetime.now().timetuple())),
                         'website': urlparse(getattr(parsed_feed, 'link', getattr(e, 'link',  getattr(parsed_feed, 'href', "unknown")))).netloc
                         } for e in last_entries]
        last_entries = [e for e in last_entries if (current_year - int(e['published'].tm_year) <= 1)]
        return last_entries

    def find_matching_entries(self, entries):
        category_id = self.kwargs.get('id', None)
        category = Category.objects.get(id=category_id)
        add_treshold = 0.8
        treshold_decrease = 1.0/len(entries)
        matching_entries = []
        for e in entries:
            if any([t.name.lower() in e.summary.lower() for t in category.search_tags.all()]):
                matching_entries.append(e)
            else:
                chance = random.random()
                if chance > add_treshold:
                    matching_entries.append(e)
            add_treshold -= treshold_decrease

        return matching_entries


    def format_entries(self, entries):
        urls_to_reparse = ['feedproxy', 'rss']
        for e in entries:
            date_published = time.struct_time(tuple(e['published'])) if isinstance(e['published'], list) else e['published']
            e['published'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', date_published)
            if any([e['website'].startswith(url) for url in urls_to_reparse]):
                article = requests.get(e['url'])
                e['website'] = urlparse(article.url).netloc
        return entries

    def make_date_clear(self, entries):
        for e in entries:
            e['published'] = "{} {}".format(e['published'][:10], e['published'][11:16])
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


class CategorySourcesView(GeneralView):
    http_method_names = ['get']
    template_name = "category/sources.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = Category.objects.get(id=kwargs['id'])
        sources = category.sources.all()
        context['category'] = category
        context['sources'] = sources
        return context


class GeneralCreateView(CreateView):
    """General class for create view"""

    def get_context_data(self, **kwargs):
        context = super(GeneralCreateView, self).get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context


class SourceCreateView(GeneralCreateView):
    model = Source
    template_name = "category/source_form.html"
    success_url = "/"
    form_class = SourceForm

    def get_context_data(self, **kwargs):
        context = super(SourceCreateView, self).get_context_data(**kwargs)
        context['id'] = self.kwargs.get('id', None)
        return context

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
        return response


class CategoryCreateView(GeneralCreateView):
    model = Category
    template_name = 'category/category_form.html'
    fields = ['name']
    success_url = '/'


class TagCreateView(GeneralCreateView):
    model = SearchTag
    template_name = 'tags/searchtag_form.html'
    fields = ['name']
    success_url = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        formset = TagFormset(self.request.POST) if self.request.POST else TagFormset()
        context['id'] = self.kwargs.get('id', None)
        context['formset'] = formset
        return context

    def get_success_url(self):
        category_id = self.kwargs.get('id', None)
        return reverse_lazy("category-view", kwargs={'id': category_id})

    def post(self, request, *args, **kwargs):
        formset = TagFormset(request.POST)
        category_id = self.kwargs.get('id', None)
        category = Category.objects.get(id=category_id)
        if formset.is_valid():
            cache.clear()
            for instance in formset.forms:
                new_tag = instance.cleaned_data.get('name', None)
                if new_tag:
                    new_tag_instance = SearchTag(name=new_tag)
                    new_tag_instance.save()
                    category.search_tags.add(new_tag_instance)
            response = redirect(self.get_success_url())
            return response


class FindSourcesView(GeneralView):
    http_method_names = ['get', 'post']
    template_name = "source/find.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['form'] = FindSourceForm()
        return context

    def post(self, request):
        form = FindSourceForm(request.POST)
        discovered_feeds = []
        if form.is_valid():
            link = form.cleaned_data['link']
            discovered_feeds = self.get_all_rss(link)
            discovered_feeds = self.get_suggested_categories(discovered_feeds)
        form = DiscoveredSourceForm()
        categories = Category.objects.all()
        return render(request, "source/discovered.html", {'categories': categories,"discovered_feeds": discovered_feeds, 'form': form})

    def get_all_rss(self, website_link: str):
        homepage = requests.get(website_link)
        homepage_soup = BeautifulSoup(homepage.text, 'html.parser')
        homepage_rss_feeds = homepage_soup.findAll(type='application/rss+xml')
        homepage_rss_feeds = homepage_rss_feeds + homepage_soup.findAll('a',
                                                                        {"href": re.compile("/(?!.*/).*(rss|xml)")})

        parsed_link = urlparse(website_link)
        for link in homepage_rss_feeds:
            if not link['href'].startswith("http"):
                link['href'] = parsed_link.scheme + "://" + parsed_link.netloc + link['href']

        homepage_rss_feeds = set([link['href'] for link in homepage_rss_feeds if (
                    "?" not in link['href'] and "video" not in link['href'] and "script" not in link['href'])])

        return homepage_rss_feeds

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
        categories = Category.objects.all()
        return render(request, "source/add_discovered.html", {'form': form, 'categories': categories})

    def post(self, request):
        form = DiscoveredSourceForm(data=request.POST)

        if form.is_valid():
            source_name = form.cleaned_data.get('name')
            source_url = form.data.get('link')
            category_obj = form.cleaned_data.get('category')
            new_source = Source(name=source_name, link=source_url)
            new_source.save()
            category_obj.sources.add(new_source)

        return JsonResponse({})


class DefaultDeleteView(DeleteView):

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)

    def get_success_url(self):
        category_url = self.request.META['HTTP_REFERER']
        return category_url


class DeleteSourceView(DefaultDeleteView):
    model = Source
    success_url = reverse_lazy("index")

    def get(self, request, *args, **kwargs):
        site = Source.objects.get(id=kwargs['pk'])
        try_cache = cache.get("cache_{}".format(site.link))
        try_cache_formatted = cache.get("formatted_{}".format(site.link))
        if try_cache:
            cache.delete("cache_{}".format(site.link))
        if try_cache_formatted:
            cache.delete("formatted_{}".format(site.link))
        return self.post(request, *args, **kwargs)


class DeleteTagView(DefaultDeleteView):
    model = SearchTag
    success_url = reverse_lazy("category-view")