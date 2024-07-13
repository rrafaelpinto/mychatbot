from django.contrib import admin
from .models import Candidate

@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'linkedin')
    search_fields = ('name', 'email')
    prepopulated_fields = {'slug': ('name',)}
