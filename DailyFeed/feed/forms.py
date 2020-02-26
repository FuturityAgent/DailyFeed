from django import forms
from .models import Source, Category, SearchTag
import feedparser
import pdb


class SourceForm(forms.ModelForm):
    class Meta:
        model = Source
        fields = '__all__'


class DiscoveredSourceForm(forms.Form):

    name = forms.CharField(label="Nazwa")
    # url = forms.URLField(widget=forms.HiddenInput())
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        widget=forms.RadioSelect,
        label="Kategoria"
    )


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']


class SearchTagForm(forms.ModelForm):
    class Meta:
        model = SearchTag
        fields = ['name']


class FindSourceForm(forms.Form):
    link = forms.URLField(help_text="Adres strony")