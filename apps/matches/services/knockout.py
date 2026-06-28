from apps.matches.models import Match


WINNER_ADVANCEMENT = {
    73: (89, 'home'),
    75: (89, 'away'),
    74: (90, 'home'),
    77: (90, 'away'),
    76: (91, 'home'),
    78: (91, 'away'),
    79: (92, 'home'),
    80: (92, 'away'),
    83: (93, 'home'),
    84: (93, 'away'),
    81: (94, 'home'),
    82: (94, 'away'),
    86: (95, 'home'),
    88: (95, 'away'),
    85: (96, 'home'),
    87: (96, 'away'),
    89: (97, 'home'),
    90: (97, 'away'),
    93: (98, 'home'),
    94: (98, 'away'),
    91: (99, 'home'),
    92: (99, 'away'),
    95: (100, 'home'),
    96: (100, 'away'),
    97: (101, 'home'),
    98: (101, 'away'),
    99: (102, 'home'),
    100: (102, 'away'),
    101: (104, 'home'),
    102: (104, 'away'),
}

LOSER_ADVANCEMENT = {
    101: (103, 'home'),
    102: (103, 'away'),
}


def placeholder_for_match_slot(match_number, slot):
    for source_match_number, target in WINNER_ADVANCEMENT.items():
        if target == (match_number, slot):
            return f'Ganador partido {source_match_number}'
    for source_match_number, target in LOSER_ADVANCEMENT.items():
        if target == (match_number, slot):
            return f'Perdedor partido {source_match_number}'
    return None


def update_knockout_placeholders(dry_run=False):
    updated_count = 0
    target_match_numbers = {
        target_match_number
        for target_match_number, slot in [*WINNER_ADVANCEMENT.values(), *LOSER_ADVANCEMENT.values()]
    }
    for match in Match.objects.filter(match_number__in=target_match_numbers):
        update_fields = []
        home_placeholder = placeholder_for_match_slot(match.match_number, 'home')
        if home_placeholder and not match.home_team_id and match.home_team_placeholder != home_placeholder:
            match.home_team_placeholder = home_placeholder
            update_fields.append('home_team_placeholder')
        away_placeholder = placeholder_for_match_slot(match.match_number, 'away')
        if away_placeholder and not match.away_team_id and match.away_team_placeholder != away_placeholder:
            match.away_team_placeholder = away_placeholder
            update_fields.append('away_team_placeholder')
        if update_fields:
            updated_count += 1
            if not dry_run:
                match.save(update_fields=[*update_fields, 'updated_at'])
    return updated_count


def knockout_loser(match):
    if not match.has_result or not match.home_team or not match.away_team:
        return None
    if match.winner_id == match.home_team_id:
        return match.away_team
    if match.winner_id == match.away_team_id:
        return match.home_team
    return None


def set_match_slot(match, slot, team):
    if slot == 'home':
        if match.home_team_id == team.id and match.home_team_placeholder == '':
            return False
        match.home_team = team
        match.home_team_placeholder = ''
        match.save(update_fields=['home_team', 'home_team_placeholder', 'updated_at'])
        return True
    if match.away_team_id == team.id and match.away_team_placeholder == '':
        return False
    match.away_team = team
    match.away_team_placeholder = ''
    match.save(update_fields=['away_team', 'away_team_placeholder', 'updated_at'])
    return True


def advance_knockout_match(match):
    if not match.winner_id:
        return 0

    updated_count = 0
    winner_target = WINNER_ADVANCEMENT.get(match.match_number)
    if winner_target:
        target_match_number, slot = winner_target
        target_match = Match.objects.filter(match_number=target_match_number).first()
        if target_match and set_match_slot(target_match, slot, match.winner):
            updated_count += 1

    loser_target = LOSER_ADVANCEMENT.get(match.match_number)
    loser = knockout_loser(match)
    if loser_target and loser:
        target_match_number, slot = loser_target
        target_match = Match.objects.filter(match_number=target_match_number).first()
        if target_match and set_match_slot(target_match, slot, loser):
            updated_count += 1

    return updated_count
