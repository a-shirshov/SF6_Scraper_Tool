import re

def clear_OL(lp):
    try:
        numeric_part = re.sub(r'\D', '', lp)  # Remove all non-digit characters
        lp_value = int(numeric_part)
    except (ValueError, AttributeError):
        return None
    return lp_value
