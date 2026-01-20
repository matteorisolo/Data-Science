from rasa_sdk import FormValidationAction
from typing import Any, Dict, Text

class ValidateGuidedSearchForm(FormValidationAction):

    def name(self) -> Text:
        return "validate_guided_search_form"

    # ---------- CATEGORY ----------
    async def validate_category(self, value: Any, dispatcher, tracker, domain) -> Dict[Text, Any]:
        if tracker.get_slot("requested_slot") != "category":
            return {"category": tracker.get_slot("category")}

        # Controllo se l'utente ha detto "nessuno/qualsiasi" nel testo
        text = tracker.latest_message.get("text", "").lower()
        if text in ["no", "nessuno", "qualsiasi", "tutti", "indifferente"]:
            return {"category": None}  # Restituisco None per disattivare il filtro

        # Se value è arrivato dall'entità o dal testo, lo tengo
        return {"category": value}

    # ---------- DIFFICULTY ----------
    async def validate_difficulty(self, value: Any, dispatcher, tracker, domain) -> Dict[Text, Any]:
        if tracker.get_slot("requested_slot") != "difficulty":
            return {"difficulty": tracker.get_slot("difficulty")}

        text = tracker.latest_message.get("text", "").lower()
        if text in ["no", "qualsiasi", "indifferente", "tutte"]:
            return {"difficulty": None}  # Restituisco None

        # Normalizzazione opzionale (se nel CSV è "Media" e l'utente dice "Medio")
        val_str = str(value).lower()
        if "medi" in val_str: return {"difficulty": "media"}
        if "facil" in val_str: return {"difficulty": "facile"}
        if "difficil" in val_str: return {"difficulty": "difficile"}
        
        return {"difficulty": value}

    # ---------- INGREDIENTS ----------
    async def validate_ingredients(self, value: Any, dispatcher, tracker, domain) -> Dict[Text, Any]:
        if tracker.get_slot("requested_slot") != "ingredients":
            return {"ingredients": tracker.get_slot("ingredients")}

        text = tracker.latest_message.get("text", "").lower()
        # Controllo stop words
        if text in ["no", "nessuno", "niente", "non ho ingredienti", "skip"]:
            return {"ingredients": []}

        final_ingredients = []

        # CASO 1: Input è una stringa (da from_text)
        if isinstance(value, str):
            final_ingredients = [
                i.strip().lower() 
                for i in value.replace(" e ", ",").split(",") 
                if i.strip()
            ]
        
        # CASO 2: Input è una lista (da from_entity)
        elif isinstance(value, list):
            final_ingredients = [str(i).strip().lower() for i in value]

        return {"ingredients": final_ingredients}

    # ---------- NUM PEOPLE ----------
    async def validate_num_people(self, value: Any, dispatcher, tracker, domain) -> Dict[Text, Any]:
        if tracker.get_slot("requested_slot") != "num_people":
            return {"num_people": tracker.get_slot("num_people")}

        # Se arriva da from_entity (Duckling) è già un numero
        if isinstance(value, (int, float)):
            return {"num_people": int(value)}

        # Se arriva da from_text è una stringa
        if isinstance(value, str):
            value = value.strip().lower()
            words_to_numbers = {
                "uno": 1, "due": 2, "tre": 3, "quattro": 4,
                "cinque": 5, "sei": 6, "sette": 7,
                "otto": 8, "nove": 9, "dieci": 10
            }
            if value in words_to_numbers:
                return {"num_people": words_to_numbers[value]}
            try:
                return {"num_people": int(value)}
            except ValueError:
                return {"num_people": None}

        return {"num_people": None}