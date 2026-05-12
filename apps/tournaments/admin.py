from django.contrib import admin

from .models import FriendTournament, TournamentMembership


class TournamentMembershipInline(admin.TabularInline):
    model = TournamentMembership
    extra = 0
    autocomplete_fields = ['user']


@admin.register(FriendTournament)
class FriendTournamentAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'invite_code', 'max_members', 'member_count', 'is_active', 'created_at']
    list_filter = ['is_active', 'is_private']
    search_fields = ['name', 'slug', 'invite_code']
    readonly_fields = ['invite_code']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [TournamentMembershipInline]

    @admin.display(description='Participantes')
    def member_count(self, obj):
        return obj.active_member_count


@admin.register(TournamentMembership)
class TournamentMembershipAdmin(admin.ModelAdmin):
    list_display = ['tournament', 'user', 'role', 'is_active', 'joined_at']
    list_filter = ['role', 'is_active', 'tournament']
    search_fields = ['tournament__name', 'user__username', 'user__email']

# Register your models here.
