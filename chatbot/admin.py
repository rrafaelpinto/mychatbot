from django.contrib import admin
from .models import Candidate, Interaction


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'linkedin')
    search_fields = ('name', 'email')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Interaction)
class InteractionAdmin(admin.ModelAdmin):
    list_display = ('user', 'candidate', 'question', 'timestamp')
    list_filter = ('user', 'candidate')
    search_fields = ('question',)

