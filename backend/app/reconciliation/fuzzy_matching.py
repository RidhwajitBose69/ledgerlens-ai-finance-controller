from rapidfuzz import fuzz

def calculate_string_similarity(str1: str, str2: str) -> float:
    if not str1 or not str2:
        return 0.0
    str1_clean = str1.strip().lower()
    str2_clean = str2.strip().lower()

    if str1_clean == str2_clean:
        return 1.0

    ratio = fuzz.ratio(str1_clean, str2_clean) / 100.0
    token_sort = fuzz.token_sort_ratio(str1_clean, str2_clean) / 100.0

    return max(ratio, token_sort)
