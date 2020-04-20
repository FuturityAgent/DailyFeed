from django.db import models


class SearchTag(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Source(models.Model):
    name = models.CharField(max_length=100)
    link = models.URLField(max_length=256)

    def __str__(self):
        return self.link


class Category(models.Model):
    name = models.CharField(max_length=30)
    sources = models.ManyToManyField(Source)
    search_tags = models.ManyToManyField(SearchTag)

    def __str__(self):
        return self.name

# Create your models here.
