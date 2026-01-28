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
            return {"category": "any"}  # Restituisco None per disattivare il filtro

        # 2. Validazione Reale (Opzionale ma consigliata)
        # Se vuoi accettare SOLO categorie esistenti nel tuo DB, mettile qui.
        valid_categories = ["dolci", "primi piatti", "secondi piatti", "antipasti", "lievitati", "piatti unici", "contorni", "salse e sughi", "torte salate", "bevande", "marmellate e conserve", "insalate"]
        
        # Se il valore estratto (value) o il testo utente è valido
        normalized_val = str(value).lower()
        
        # Cerchiamo match parziali (es. "i primi" -> "primi")
        for cat in valid_categories:
            if cat in normalized_val:
                return {"category": cat}

        # 3. ERRORE: Categoria sconosciuta 🚫
        dispatcher.utter_message(text=f"⚠️ Non conosco la categoria '{value}'. Prova con Primi, Secondi o Dolci.")
        return {"category": None} # None costringe il Form a rifare la domanda

    # ---------- DIFFICULTY ----------
    async def validate_difficulty(self, value: Any, dispatcher, tracker, domain) -> Dict[Text, Any]:
        if tracker.get_slot("requested_slot") != "difficulty":
            return {"difficulty": tracker.get_slot("difficulty")}

        text = tracker.latest_message.get("text", "").lower()
        if text in ["no", "qualsiasi", "indifferente", "tutte"]:
            return {"difficulty": "any"}  # Restituisco None

        # Normalizzazione opzionale (se nel CSV è "Media" e l'utente dice "Medio")
        val_str = str(value).lower()
        if "medi" in val_str: return {"difficulty": "media"}
        if "facil" in val_str: return {"difficulty": "facile"}
        if "difficil" in val_str: return {"difficulty": "difficile"}
        
        dispatcher.utter_message(text="⚠️ La difficoltà deve essere Facile, Media o Difficile (oppure 'indifferente').")
        return {"difficulty": None} # Resetta lo slot per chiedere di nuovo

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

        if not final_ingredients:
            dispatcher.utter_message(text="⚠️ Non ho capito gli ingredienti. Scrivimeli separati da virgola (es. uova, farina) o scrivi 'salta'.")
            return {"ingredients": None}

        return {"ingredients": final_ingredients}

    # ---------- NUM PEOPLE ----------
    # ---------- NUM PEOPLE ----------
    async def validate_num_people(self, value: Any, dispatcher, tracker, domain) -> Dict[Text, Any]:
        if tracker.get_slot("requested_slot") != "num_people":
            return {"num_people": tracker.get_slot("num_people")}

        # Helper interno per controllare che il numero sia sensato (Range 1-50)
        def check_range(n):
            if n < 1:
                dispatcher.utter_message(text="⚠️ Devi cucinare per almeno una persona! 😉")
                return False
            if n > 50:
                dispatcher.utter_message(text="⚠️ Cucini per un esercito? 😮 Il mio limite è 50 persone.")
                return False
            return True

        # Se arriva da from_entity (Duckling) è già un numero
        if isinstance(value, (int, float)):
            num = int(value)
            if check_range(num):
                return {"num_people": num}
            return {"num_people": None}

        # Se arriva da from_text è una stringa
        if isinstance(value, str):
            value = value.strip().lower()

            # --- NUOVO: Gestione "Non so" / "Qualsiasi" ---
            # Se l'utente salta, impostiamo il default a 4 persone
            skip_keywords = ["non so", "boh", "fai tu", "qualsiasi", "indifferente", "salta", "no", "skip", "tutti"]
            if value in skip_keywords:
                dispatcher.utter_message(text="👨‍🍳 Ok, nel dubbio calcolo le dosi per una famiglia media (4 persone)!")
                return {"num_people": 4}
            # -----------------------------------------------

            words_to_numbers = {
                "uno": 1, "un": 1, "una": 1, "due": 2, "tre": 3, "quattro": 4,
                "cinque": 5, "sei": 6, "sette": 7,
                "otto": 8, "nove": 9, "dieci": 10, "undici": 11, "dodici": 12, 
                "tredici": 13, "quattordici": 14, "quindici": 15, "sedici": 16,
                "diciassette": 17, "diciotto": 18, "diciannove": 19, "venti": 20
            }
            
            if value in words_to_numbers:
                return {"num_people": words_to_numbers[value]}
            
            try:
                num = int(value)
                # Applichiamo il controllo range anche qui
                if check_range(num):
                    return {"num_people": num}
                return {"num_people": None}
            except ValueError:
                dispatcher.utter_message(text="⚠️ Non ho capito il numero. Scrivimi una cifra (es. 4) o dimmi 'non so'.")
                return {"num_people": None}

        dispatcher.utter_message(text="⚠️ Non ho capito. Per quante persone cucini?")
        return {"num_people": None}