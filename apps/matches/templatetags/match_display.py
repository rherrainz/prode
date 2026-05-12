from django import template

register = template.Library()


@register.inclusion_tag('matches/_team_label.html')
def team_label(team, placeholder='TBD'):
    return {
        'team': team,
        'label': team.public_name if team else placeholder or 'TBD',
    }
