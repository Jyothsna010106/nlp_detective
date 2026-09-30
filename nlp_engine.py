import spacy
from dateutil import parser as date_parser
import re

nlp = spacy.load("en_core_web_sm")

GEO_CORRECTIONS = {"chennai", "hyderabad", "bengaluru", "mumbai", "pune", "delhi", "singapore", "whitefield"}
PERSON_CORRECTIONS = {"ananya", "ananya sharma", "vikram", "vikram rao", "rahul", "rahul verma", "kavya", "kavya menon", "sameer", "sameer khan"}
ORG_CORRECTIONS = {
    "orion", "orion technologies", "orion technologies research centre", 
    "vertex data systems", "nexa digital solutions", "cyber crime investigation bureau",
    "indian institute of science", "infosys", "apex financial systems"
}

PRONOUN_MAP = {"he", "she", "they", "him", "her", "them", "the suspect", "the operative", "the engineer"}

def parse_document(text: str):
    return nlp(text)

def post_process_entities(doc) -> list[dict]:
    processed = []
    seen = set()
    for ent in doc.ents:
        txt = ent.text.strip()
        lower = txt.lower()
        label = ent.label_

        if lower in ("ip", "the", "an", "a", "pm", "am", "device", "unknown device"):
            continue

        if lower in GEO_CORRECTIONS:
            label = "GPE"
        elif lower in PERSON_CORRECTIONS:
            label = "PERSON"
        elif lower in ORG_CORRECTIONS:
            label = "ORG"

        key = (txt, label)
        if key not in seen:
            seen.add(key)
            processed.append({"text": txt, "label": label})
    return processed

def find_contained_entity(text: str, entities: list[dict]) -> dict:
    text_lower = text.lower()
    for ent in entities:
        if ent["text"].lower() in text_lower:
            return ent
    return None

def resolve_anaphora(doc, processed_ents: list[dict]) -> dict[int, str]:
    """
    Tracks the active Person and Organization across sentences.
    Returns a mapping of token indices to resolved entity names.
    """
    resolved_pronouns = {}
    last_person = None
    last_org = None

    for sent in doc.sents:
        # Check if new entities are introduced in this sentence
        for ent in sent.ents:
            if ent.label_ == "PERSON" or ent.text.lower() in PERSON_CORRECTIONS:
                last_person = ent.text
            elif ent.label_ == "ORG" or ent.text.lower() in ORG_CORRECTIONS:
                last_org = ent.text

        # Resolve pronouns in this sentence using the running antecedent
        for token in sent:
            token_lower = token.text.lower()
            if token_lower in ("he", "she", "him", "her", "they") and last_person:
                resolved_pronouns[token.i] = last_person
            elif token_lower in ("it", "company", "firm") and last_org:
                resolved_pronouns[token.i] = last_org

    return resolved_pronouns

def extract_triplets(doc) -> list[dict]:
    """
    Forensic Triplet Extractor with Cross-Sentence Coreference Resolution.
    Maps subject/object pronouns back to concrete antecedent suspects.
    """
    processed_ents = post_process_entities(doc)
    resolved_pronouns = resolve_anaphora(doc, processed_ents)
    triplets = []

    for sent in doc.sents:
        sent_ents = [e for e in processed_ents if e["text"].lower() in sent.text.lower()]

        for token in sent:
            if token.pos_ == "VERB" and token.lemma_.lower() not in ("be", "have", "do"):
                action = token.lemma_

                source_name = None
                source_type = "ENTITY"
                target_name = None
                target_type = "ENTITY"

                # 1. Look for Subject
                for child in token.children:
                    if child.dep_ in ("nsubj", "nsubjpass"):
                        if child.i in resolved_pronouns:
                            source_name = resolved_pronouns[child.i]
                            source_type = "PERSON"
                        else:
                            cand = find_contained_entity("".join([w.text_with_ws for w in child.subtree]), sent_ents)
                            if cand:
                                source_name = cand["text"]
                                source_type = cand["label"]

                    # 2. Look for Object / Prepositional Target
                    if child.dep_ in ("dobj", "attr", "prep", "pobj"):
                        cand = find_contained_entity("".join([w.text_with_ws for w in child.subtree]), sent_ents)
                        if cand:
                            target_name = cand["text"]
                            target_type = cand["label"]

                    # 3. Passive Agent
                    if child.dep_ == "agent":
                        cand = find_contained_entity("".join([w.text_with_ws for w in child.subtree]), sent_ents)
                        if cand:
                            source_name = cand["text"]
                            source_type = cand["label"]

                # Fallback within sentence if standard dependency was missing one side
                if not (source_name and target_name) and len(sent_ents) >= 2:
                    source_name = sent_ents[0]["text"]
                    source_type = sent_ents[0]["label"]
                    target_name = sent_ents[1]["text"]
                    target_type = sent_ents[1]["label"]

                if source_name and target_name and (source_name.lower() != target_name.lower()):
                    action_display = action.upper()
                    if action.lower() == "travel": action_display = "TRAVELLED TO"
                    elif action.lower() == "meet": action_display = "MET WITH"
                    elif action.lower() == "question": action_display = "QUESTIONED"
                    elif action.lower() == "resign": action_display = "RESIGNED FROM"
                    elif action.lower() == "transfer": action_display = "TRANSFERRED TO"
                    elif action.lower() == "recover": action_display = "RECOVERED FILES AT"
                    elif action.lower() == "plug": action_display = "PLUGGED DEVICE INTO"
                    elif action.lower() == "download": action_display = "DOWNLOADED FILES FROM"

                    triplet_obj = {
                        "Subject": source_name,
                        "Relation": action_display,
                        "Object": target_name,
                        "Subject_Type": source_type,
                        "Object_Type": target_type
                    }
                    if triplet_obj not in triplets:
                        triplets.append(triplet_obj)
                        break

    return triplets

def extract_timeline_events(doc) -> list[dict]:
    events = []
    seen_events = set()

    for sent in doc.sents:
        sent_dates = [ent.text for ent in sent.ents if ent.label_ in ("DATE", "TIME")]
        if not sent_dates:
            continue

        primary_date_str = sent_dates[0]
        parsed_dt = None

        try:
            clean_date = re.sub(r'^(on|at|around|approximately)\s+', '', primary_date_str, flags=re.IGNORECASE)
            parsed_dt = date_parser.parse(clean_date, fuzzy=True, default=date_parser.parse("2026-01-01"))
        except Exception:
            parsed_dt = None

        event_text = sent.text.strip()
        key = (primary_date_str, event_text)
        if key not in seen_events:
            seen_events.add(key)
            events.append({
                "raw_date": primary_date_str,
                "parsed_dt": parsed_dt,
                "event": event_text,
                "sort_key": parsed_dt.strftime("%Y-%m-%d %H:%M") if parsed_dt else "9999-99-99"
            })

    events.sort(key=lambda x: x["sort_key"])
    return events