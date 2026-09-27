"""Controlled vocabularies and deterministic keyword maps for extraction/routing."""

SPECIALTIES = ["Oncology", "Cardiology", "Endocrinology"]
CONDITIONS_BY_SPECIALTY = {
    "Oncology": ["Breast cancer", "Lung cancer"],
    "Cardiology": ["Heart failure", "Atrial fibrillation"],
    "Endocrinology": ["Type 2 diabetes", "Obesity"],
}
CONDITIONS = [condition for values in CONDITIONS_BY_SPECIALTY.values() for condition in values]
TOPICS = [
    "Treatment sequencing", "Side-effect management", "Clinical trials", "Access/coverage",
    "Guideline update", "Drug interactions", "Monitoring",
]
INTENTS = ["Clinical update", "Evidence review", "Case consult", "Safety concern", "Access question"]
OTHER = "Other"

KEYWORDS = {
    "specialties": {
        "Oncology": ["oncology", "cancer", "tumor", "tumour", "oncologist"],
        "Cardiology": ["cardiology", "cardiac", "heart", "cardiologist"],
        "Endocrinology": ["endocrinology", "endocrine", "diabetes", "metabolic"],
    },
    "conditions": {
        "Breast cancer": ["breast cancer", "her2", "cdk4/6", "tamoxifen", "hr+"],
        "Lung cancer": ["lung cancer", "nsclc", "small cell", "egfr", "alk"],
        "Heart failure": ["heart failure", "hfref", "sglt2", "ejection fraction", "hfr ef"],
        "Atrial fibrillation": ["atrial fibrillation", "anticoagulation", "doac", "afib", "atrial fib"],
        "Type 2 diabetes": ["type 2 diabetes", "metformin", "a1c", "glp-1", "glp1"],
        "Obesity": ["obesity", "weight management", "bmi", "anti-obesity"],
    },
    "topics": {
        "Treatment sequencing": ["next line", "after progression", "sequence", "sequencing", "line of therapy"],
        "Side-effect management": ["side effect", "adverse event", "toxicity", "tolerability"],
        "Clinical trials": ["trial", "enrolling", "nct", "clinical study"],
        "Access/coverage": ["prior auth", "coverage", "insurance", "reimbursement"],
        "Guideline update": ["guideline", "what's new", "recently", "changed", "update"],
        "Drug interactions": ["interaction", "drug-drug", "concomitant", "contraindicated"],
        "Monitoring": ["monitoring", "monitor", "follow-up", "surveillance", "track"],
    },
    "intents": {
        "Clinical update": ["what's new", "recently", "changed", "latest", "update"],
        "Evidence review": ["evidence", "data", "literature", "studies", "review"],
        "Case consult": ["patient", "case", "complicated", "consult"],
        "Safety concern": ["safety", "risk", "harm", "warning", "toxic"],
        "Access question": ["coverage", "insurance", "prior auth", "access", "cost"],
    },
}


def normalize_value(value: str, values: list[str]) -> str:
    """Return a canonical controlled-vocabulary value, or Other for unknown input."""
    folded = value.strip().casefold()
    return next((candidate for candidate in values if candidate.casefold() == folded), OTHER)
