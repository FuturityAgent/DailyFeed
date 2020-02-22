from django.db import models
from django.urls import reverse


class SearchTag(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Source(models.Model):
    name = models.CharField(max_length=100)
    link = models.URLField(max_length=256)




class Category(models.Model):
    name = models.CharField(max_length=30)
    sources = models.ManyToManyField(Source)
    search_tags = models.ManyToManyField(SearchTag)

# Create your models here.
