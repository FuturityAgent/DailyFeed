from django import forms
from .models import Source, Category, SearchTag
import feedparser
import pdb


class SourceForm(forms.ModelForm):
    class Meta:
        model = Source
        fields = '__all__'


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']


class SearchTagForm(forms.ModelForm):
    class Meta:
        model = SearchTag
        fields = ['name']