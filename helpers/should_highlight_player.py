def should_highlight_player(total_matches, max_lp, min_matches, max_matches, max_rating):
    if min_matches is not None and total_matches < min_matches:
        return True
    if max_matches is not None and total_matches > max_matches:
        return True
    if max_rating is not None and max_lp > max_rating:
        return True
    return False
