from django import template

register = template.Library()

TEAM_SHORT_CODES = {
    'Mexico': 'MEX',
    'South Africa': 'RSA',
    'Korea Republic': 'KOR',
    'Czechia': 'CZE',
    'Canada': 'CAN',
    'Bosnia and Herzegovina': 'BIH',
    'Qatar': 'QAT',
    'Switzerland': 'SUI',
    'Brazil': 'BRA',
    'Morocco': 'MAR',
    'Haiti': 'HAI',
    'Scotland': 'SCO',
    'USA': 'USA',
    'Paraguay': 'PAR',
    'Australia': 'AUS',
    'Türkiye': 'TUR',
    'Germany': 'GER',
    'Curaçao': 'CUW',
    "Côte d'Ivoire": 'CIV',
    'Ecuador': 'ECU',
    'Netherlands': 'NED',
    'Japan': 'JPN',
    'Sweden': 'SWE',
    'Tunisia': 'TUN',
    'Belgium': 'BEL',
    'Egypt': 'EGY',
    'IR Iran': 'IRN',
    'New Zealand': 'NZL',
    'Spain': 'ESP',
    'Cabo Verde': 'CPV',
    'Saudi Arabia': 'KSA',
    'Uruguay': 'URU',
    'France': 'FRA',
    'Senegal': 'SEN',
    'Iraq': 'IRQ',
    'Norway': 'NOR',
    'Argentina': 'ARG',
    'Algeria': 'ALG',
    'Austria': 'AUT',
    'Jordan': 'JOR',
    'Portugal': 'POR',
    'Congo DR': 'COD',
    'Uzbekistan': 'UZB',
    'Colombia': 'COL',
    'England': 'ENG',
    'Croatia': 'CRO',
    'Ghana': 'GHA',
    'Panama': 'PAN',
}


@register.inclusion_tag('matches/_team_label.html')
def team_label(team, placeholder='TBD'):
    label = team.public_name if team else placeholder or 'TBD'
    return {
        'team': team,
        'label': label,
        'short_label': TEAM_SHORT_CODES.get(team.name, label[:3].upper()) if team else 'TBD',
    }
