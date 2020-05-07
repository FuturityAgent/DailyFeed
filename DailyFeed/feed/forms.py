from django import forms
from .models import Source, Category, SearchTag


class SourceForm(forms.ModelForm):
    """Form used when adding new source to news category"""
    class Meta:
        model = Source
        fields = '__all__'


class DiscoveredSourceForm(forms.Form):
    """Form used when adding source discovered via FindSourceForm to category
    @fields:
        name: name of the new source
        category: category, radio button, where choices are all categories from database"""
    name = forms.CharField(label="Nazwa")
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        widget=forms.RadioSelect,
        label="Kategoria"
    )


class CategoryForm(forms.ModelForm):
    """Form used when creating new news category
    @fields:
        name: name of category (surprising, isn't it?)"""
    class Meta:
        model = Category
        fields = ['name']


class SearchTagForm(forms.ModelForm):
    """Field used when adding new tags to certain category
    @fields:
        name: string, which is later searched in news summary"""
    class Meta:
        model = SearchTag
        fields = ['name']


TagFormset = forms.formset_factory(SearchTagForm, extra=1)

class FindSourceForm(forms.Form):
    """Form used when trying to discover RSS feeds on certain webpage
    @fields:
        link: webpage URL
    """
    link = forms.URLField(help_text="Adres strony")
