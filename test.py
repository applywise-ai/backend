from rapidfuzz import fuzz, process

# Define target and choices
target = "MAN"
choices = ["MALE", "FEMALE"]

# Calculate different similarity scores
results = {
    choice: {
        "ratio": fuzz.ratio(target, choice),
        "partial_ratio": fuzz.partial_ratio(target, choice),
        "token_sort_ratio": fuzz.token_sort_ratio(target, choice),
        "token_set_ratio": fuzz.token_set_ratio(target, choice),
        "WRatio": fuzz.WRatio(target, choice)
    }
    for choice in choices
}

# Also get the best match using extractOne
best_match = process.extractOne(target, choices, scorer=fuzz.partial_ratio)

results["best_match"] = {
    "match": best_match[0],
    "score": best_match[1],
    "method": "WRatio (default)"
}

# Print the results
import pprint
pprint.pprint(results)
from textdistance import jaccard, levenshtein

jaccard_score = jaccard.normalized_similarity("MAN", "MALE")
lev_score = levenshtein.normalized_similarity("MAN", "MALE")
final_score = (jaccard_score + lev_score) / 2
print(final_score)
