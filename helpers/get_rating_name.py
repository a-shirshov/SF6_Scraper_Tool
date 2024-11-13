from constants.rank_thresholds import rank_thresholds
from helpers.clear_OL import clear_OL

def get_rating_name(lp):
    lp_value = clear_OL(lp)
    if lp_value is None:
        return "Unknown"

    # Find the highest rank that doesn't exceed lp_value
    for rank, threshold in sorted(rank_thresholds.items(), key=lambda x: x[1], reverse=True):
        if lp_value >= threshold:
            return rank

    return "Unknown"
