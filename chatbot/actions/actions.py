from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, ActiveLoop
from typing import Any, Text, Dict, List
import difflib
import re
import random
from actions.data_loader import recipes_df  # il tuo dataset
from actions.recipe_utils import get_recipe_by_name  # funzione da creare
from actions.recipe_utils import get_recipes_by_category
from actions.recipe_utils import search_recipes_by_name
from actions.recipe_utils import get_recipes_by_ingredients
from actions.recipe_utils import get_recipes_by_difficulty
from actions.recipe_utils import get_similar_recipes_by_ingredients
from actions.recipe_utils import search_recipes_guided
from actions.recipe_utils import merge_shopping_lists


class ActionSearchByCategory(Action):

    def name(self) -> str:
        return "action_search_by_category"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):

        category = tracker.get_slot("category")

        if not category:
            dispatcher.utter_message(response="utter_ask_category")
            return []

        recipes = get_recipes_by_category(recipes_df, category)

        if not recipes:
            dispatcher.utter_message(response="utter_no_category_results", category=category)
            return []

        response = f"Ecco alcune ricette per la categoria {category} 🍽️:\n"
        response += "\n".join([f"• {r}" for r in recipes])

        dispatcher.utter_message(response)
        dispatcher.utter_message(response="utter_ask_select_from_list")

        return [SlotSet("last_recipes", recipes)]

class ActionSmartRecipeHandler(Action):

    def name(self) -> str:
        return "action_smart_recipe_handler"

    def run(self, dispatcher, tracker, domain):
        user_text = tracker.latest_message.get('text', '').lower()
        
        slot_value = tracker.get_slot("recipe_name")
        entity_value = next(tracker.get_latest_entity_values("recipe_name"), None)
        last_recipes = tracker.get_slot("last_recipes") or []

        selected_candidate = None

        # =========================================================
        # FASE 1: CONTROLLO LISTA
        # =========================================================
        if last_recipes:
            
            # ---------------------------------------------------------
            # 1. PRIORITÀ SLOT (QUELLO CHE VOLEVI) 🥇
            # Se ActionSelectByIndex ha settato lo slot, o l'entità l'ha riempito,
            # e questo valore esiste nella lista attuale, VINCE LUI.
            # Ignoriamo totalmente cosa ha scritto l'utente nel testo.
            # ---------------------------------------------------------
            if slot_value:
                for r in last_recipes:
                    # Controllo case-insensitive esatto
                    if r.lower() == slot_value.lower():
                        selected_candidate = r
                        break
            
            # ---------------------------------------------------------
            # 2. FALLBACK SUL TESTO
            # Entriamo qui SOLO se lo slot era vuoto o conteneva una ricetta 
            # che NON c'entra nulla con la lista attuale (es. vecchio slot sporco).
            # ---------------------------------------------------------
            if not selected_candidate:
                search_term = entity_value if entity_value else user_text
                
                # Pulizia Stop Words
                stop_words = ["vediamo", "fammi", "vedere", "mostrami", "voglio", "la", "il", "lo", "i", "gli", "le", "un", "una", "ricetta", "della", "del", "di"]
                clean_term = search_term
                for word in stop_words:
                    clean_term = re.sub(r'\b' + word + r'\b', '', clean_term).strip()
                
                if len(clean_term) >= 3:
                    for r in last_recipes:
                        r_lower = r.lower()
                        if clean_term in r_lower or r_lower in user_text:
                            selected_candidate = r
                            break

        # --- EXIT IMMEDIATO ---
        if selected_candidate:
            return self._show_recipe_details(dispatcher, selected_candidate)


        # =========================================================
        # FASE 2: NUOVA RICERCA (Fallback totale)
        # =========================================================
        
        # Se siamo qui, lo slot conteneva roba vecchia non valida per la lista,
        # oppure è una ricerca nuova da zero.
        query = entity_value if entity_value else (slot_value if slot_value else user_text)

        if not query or len(query) < 3:
             dispatcher.utter_message(response="utter_ask_search_term")
             return []
        
        dispatcher.utter_message(response="utter_searching_feedback", query=query)

        results = search_recipes_by_name(recipes_df, query)

        if not results:
            dispatcher.utter_message(response="utter_no_recipes_found", query=query)
            return [SlotSet("recipe_name", None)]

        if len(results) == 1:
            return self._show_recipe_details(dispatcher, results[0])

        limit = 10
        # LOGICA CASUALE
        # Se i risultati sono più del limite, ne prendiamo 'limit' A CASO.
        if len(results) > limit:
            # random.sample estrae 'limit' elementi unici a caso dalla lista
            display_list = results[:limit]
            response = f"Ho trovato ben {len(results)} ricette! 😲\nEcco {len(display_list)} proposte per te:\n\n"
        else:
            # Se sono poche, le mostriamo tutte così come sono
            display_list = results
            response = f"Ho trovato {len(results)} ricette 🍽️:\n\n"

        # Costruzione elenco
        for i, r in enumerate(display_list): 
            response += f"{i + 1}. {r}\n"

        dispatcher.utter_message(text=response, parse_mode="HTML")
        dispatcher.utter_message(response="utter_ask_select_from_list")

        # --- PUNTO FONDAMENTALE ---
        # Salviamo nello slot SOLO 'display_list' (quelle mostrate), NON 'results' (tutte).
        # In questo modo l'indice "1" corrisponderà davvero alla prima visualizzata.
        return [
            SlotSet("last_recipes", display_list),
            SlotSet("recipe_name", None) 
        ]

    # --- HELPER MODIFICATO ---
    def _show_recipe_details(self, dispatcher, recipe_name):
        recipe_data = get_recipe_by_name(recipes_df, recipe_name)

        if not recipe_data:
            dispatcher.utter_message(f"🚫 Errore dati per {recipe_name}")
            return [SlotSet("recipe_name", None)]

        formatted_ingredients = [
            f"🔸 {i['nome'].title()}: {i['quantita']}" for i in recipe_data["ingredienti_parsed"]
        ]

        response = f"👨‍🍳 {recipe_data['nome'].upper()}\n\n"
        response += f"🥣 Ingredienti per {recipe_data['persone/pezzi']} persone/pezzi:\n"
        response += "\n".join(formatted_ingredients)
        response += f"\n\n🍳 Preparazione:\n{recipe_data['preparazione']}"

        dispatcher.utter_message(text=response, parse_mode="HTML")

        # --- MODIFICA FONDAMENTALE QUI SOTTO ---
        # NON pulire lo slot (None). Salva la ricetta visualizzata!
        # Così se dopo l'utente dice "Aggiungi alla lista", il bot sa di cosa parla.
        return [SlotSet("recipe_name", recipe_name)]

class ActionSelectByIndex(Action):

    def name(self) -> str:
        return "action_select_by_index"

    def run(self, dispatcher, tracker, domain):
        text = tracker.latest_message.get("text", "").lower()
        last_recipes = tracker.get_slot("last_recipes") or []

        if not last_recipes:
            dispatcher.utter_message(response="utter_no_list_active")
            return []

        selected_index = None

        # --- STRATEGIA 1: Cerca numeri a cifre (es. "1", "2", "10") ---
        # \b indica il confine della parola, \d+ indica uno o più numeri
        numbers = re.findall(r'\b\d+\b', text)
        
        if numbers:
            # Prende il primo numero trovato e converte in indice (0-based)
            selected_index = int(numbers[0]) - 1

        # --- STRATEGIA 2: Cerca parole (Ordinali e Cardinali) ---
        # Solo se non abbiamo trovato numeri a cifre
        if selected_index is None:
            # Mapping esteso per coprire i casi più comuni
            mapping = {
                "prima": 0, "primo": 0, "uno": 0,
                "seconda": 1, "secondo": 1, "due": 1,
                "terza": 2, "terzo": 2, "tre": 2,
                "quarta": 3, "quarto": 3, "quattro": 3,
                "quinta": 4, "quinto": 4, "cinque": 4,
                "sesta": 5, "sesto": 5, "sei": 5,
                "settima": 6, "settimo": 6, "sette": 6,
                "ottava": 7, "ottavo": 7, "otto": 7,
                "nona": 8, "nono": 8, "nove": 8,
                "decima": 9, "decimo": 9, "dieci": 9,
                "ultima": len(last_recipes) - 1,
                "penultima": len(last_recipes) - 2
            }
            
            for key, val in mapping.items():
                # Usa Regex per cercare la parola esatta (evita match parziali)
                if re.search(r'\b' + key + r'\b', text):
                    selected_index = val
                    break

        # --- VALIDAZIONE ---
        if selected_index is None:
            dispatcher.utter_message(response="utter_number_not_understood")
            return []

        if selected_index < 0 or selected_index >= len(last_recipes):
            dispatcher.utter_message(response="utter_number_out_of_bounds", max_number=len(last_recipes))
            return []

        # --- RISULTATO ---
        recipe_name = last_recipes[selected_index]

        # Messaggio di conferma (Opzionale, ma utile per feedback immediato)
        dispatcher.utter_message(response="utter_selection_confirmed", recipe_name=recipe_name.title())

        return [SlotSet("recipe_name", recipe_name)]

class ActionAskRecipeIngredients(Action):

    def name(self) -> str:
        return "action_ask_recipe_ingredients"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):

        last_recipes = tracker.get_slot("last_recipes") or []
        # Prendiamo l'entity se presente
        recipe_name = tracker.get_slot("recipe_name")
        text = tracker.latest_message.get("text", "").lower()

        # --- Caso posizionale ---
        index_mapping = {
            "prima": 0,
            "seconda": 1,
            "terza": 2,
            "quarta": 3,
            "quinta": 4,
            "ultima": len(last_recipes) - 1
        }

        # Se l'utente non ha detto il nome, controlliamo se menziona la posizione
        selected_index = None
        for key, idx in index_mapping.items():
            if key in text:
                if 0 <= idx < len(last_recipes):
                    selected_index = idx
                break

        if selected_index is not None:
            recipe_name = last_recipes[selected_index]

        # --- Caso fallback: nessun nome né posizione ---
        if not recipe_name:
            dispatcher.utter_message(response="utter_ask_specify_recipe_for_ingredients")
            return [SlotSet("recipe_name", None)]  # reset slot

        # --- Recuperiamo i dati della ricetta ---
        recipe_data = get_recipe_by_name(recipes_df, recipe_name)
        if not recipe_data:
            dispatcher.utter_message(response="utter_recipe_not_found_ingredients", recipe_name=recipe_name)
            return [SlotSet("recipe_name", None)]  # reset slot

        # --- Lista ingredienti ---
        ingredients = recipe_data.get("ingredienti_parsed", [])
        if not ingredients:
            dispatcher.utter_message(response="utter_no_ingredients_data")
            return [SlotSet("recipe_name", recipe_name)]

        formatted_ingredients = [f"- {i['nome'].title()}: {i['quantita']}" for i in ingredients]

        response = f"🥣 Ingredienti per {recipe_data['nome'].title()} (per {recipe_data['persone/pezzi']} persone/pezzi):\n"
        response += "\n".join(formatted_ingredients)

        dispatcher.utter_message(response)

        # --- Aggiorniamo sempre lo slot con la ricetta corrente ---
        return [SlotSet("recipe_name", recipe_name)]
    
class ActionSearchByIngredients(Action):

    def name(self) -> str:
        return "action_search_by_ingredients"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):

        # --- Prendiamo gli ingredienti dallo slot ---
        ingredients = tracker.get_slot("ingredients") or []

        # --- Fallback: se non ci sono entity, prova a parsare dal testo ---
        if not ingredients:
            text = tracker.latest_message.get("text", "").lower()
            
            # Lista di parole da IGNORARE (verbi, articoli, richieste comuni)
            stop_words = [
                "vorrei", "voglio", "cucinare", "preparare", "fare", "mangiare", "usare",
                "con", "senza", "il", "la", "le", "i", "gli", "un", "una", "uno", 
                "del", "della", "degli", "di", "da", "in", "e", "o", "a",
                "che", "cosa", "posso", "ho", "avrei", "c'è", "ci", "sono",
                "ricetta", "piatto", "pranzo", "cena", "veloce", "semplice", "buono",
                "oggi", "domani", "adesso", "subito", "per", "favore", "grazie"
            ]

            # Puliamo la punteggiatura (es. "uova, farina" -> "uova farina")
            clean_text = re.sub(r'[^\w\s]', ' ', text)
            
            # Estraiamo le parole che NON sono stop_words e sono lunghe almeno 3 caratteri
            ingredients = [
                w.strip() for w in clean_text.split() 
                if len(w) > 2 and w not in stop_words
            ]

        # 3. Se ANCORA non abbiamo nulla, chiediamo aiuto all'utente
        if not ingredients:
            dispatcher.utter_message(response="utter_ask_ingredients_missing")
            return [SlotSet("last_recipes", [])]

        # --- Recuperiamo le ricette corrispondenti ---
        recipes = get_recipes_by_ingredients(recipes_df, ingredients)

        # Prepariamo la stringa degli ingredienti per il messaggio (es. "uova, pepe")
        ingredients_str = ", ".join(ingredients).title()

        if not recipes:
            dispatcher.utter_message(
                response="utter_no_recipes_by_ingredients", 
                ingredients_list=ingredients_str
            )
            return [SlotSet("last_recipes", [])]

        # --- Formattiamo la risposta ---
        response = f"Ecco alcune ricette che puoi fare con {ingredients_str} 🍽️:\n"
        response += "\n".join([f"• {r}" for r in recipes])

        dispatcher.utter_message(response)
        dispatcher.utter_message(response="utter_ask_select_from_list")

        # --- Aggiorniamo lo slot last_recipes con i nuovi risultati ---
        return [SlotSet("last_recipes", recipes)]
    
class ActionSurpriseMe(Action):

    def name(self) -> str:
        return "action_surprise_me"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):

        if recipes_df.empty:
            dispatcher.utter_message(response="utter_empty_database")
            return []

        # scegliamo una ricetta casuale
        recipe_row = recipes_df.sample(1).iloc[0]
        recipe_name = recipe_row["Nome"]

        recipe_data = get_recipe_by_name(recipes_df, recipe_name)

        if not recipe_data:
            dispatcher.utter_message(response="utter_surprise_error")
            return []
        
        # ingredienti
        formatted_ingredients = [
            f"🔸 {i['nome'].title()}: {i['quantita']}"
            for i in recipe_data["ingredienti_parsed"]
        ]

        response = f"🎲 Ti propongo questa ricetta a sorpresa!\n\n"
        response += f"🍽 {recipe_data['nome'].title()}\n\n"
        response += f"Ingredienti per {recipe_data['persone/pezzi']} persone/pezzi:\n"
        response += "\n".join(formatted_ingredients)
        response += f"\n\nPreparazione:\n{recipe_data['preparazione']}"

        dispatcher.utter_message(response)

        return [
            SlotSet("recipe_name", recipe_name),
            SlotSet("last_recipes", [recipe_name]),
            SlotSet("recipe_index", None)
        ]

class ActionFilterByDifficulty(Action):

    def name(self) -> str:
        return "action_filter_by_difficulty"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):

        # Recupero dello slot
        difficulty = tracker.get_slot("difficulty")
        if not difficulty:
            dispatcher.utter_message(response="utter_ask_difficulty")
            return []

        # Chiamo la funzione helper
        recipes = get_recipes_by_difficulty(recipes_df, difficulty)

        if not recipes:
            dispatcher.utter_message(response="utter_no_difficulty_results", difficulty=difficulty)
            return []

        # Risposta all'utente
        response = f"Ecco alcune ricette di difficoltà '{difficulty}' 🍽️:\n"
        response += "\n".join([f"• {r}" for r in recipes])
        dispatcher.utter_message(response)

        dispatcher.utter_message(response="utter_ask_select_from_list")

        # Salvo le ultime ricette suggerite
        return [SlotSet("last_recipes", recipes)]

class ActionSuggestSimilarRecipes(Action):

    def name(self) -> str:
        return "action_suggest_similar_recipes"

    def run(self, dispatcher, tracker, domain):

        recipe_name = tracker.get_slot("recipe_name")

        if not recipe_name:
            dispatcher.utter_message(response="utter_ask_context_for_similar")
            return []

        recipes = get_similar_recipes_by_ingredients(
            recipes_df,
            recipe_name
        )

        if not recipes:
            dispatcher.utter_message(response="utter_no_similar_recipes", recipe_name=recipe_name)
            return []

        response = "Se ti è piaciuta questa, prova anche 🍽️:\n"
        response += "\n".join([f"• {r}" for r in recipes])

        dispatcher.utter_message(response)
        dispatcher.utter_message(response="utter_ask_select_from_list")

        return [SlotSet("last_recipes", recipes)]
    
class ActionStartGuidedSearchForm(Action):
    def name(self):
        return "action_start_guided_search_form"

    def run(self, dispatcher, tracker, domain):
        # reset di tutti gli slot del form
        return [
            SlotSet("category", None),
            SlotSet("difficulty", None),
            SlotSet("ingredients", None),
            SlotSet("num_people", None),
            SlotSet("recipe_name", None),
            SlotSet("last_recipes", None),
            SlotSet("recipe_index", None),
            ActiveLoop("guided_search_form")  # attiva il form da zero
        ]
    
class ActionSubmitGuidedSearch(Action):
    def name(self):
        return "action_submit_guided_search"

    def run(self, dispatcher, tracker, domain):
        category = tracker.get_slot("category")
        difficulty = tracker.get_slot("difficulty")

        if category == "any":
            category = None
        
        if difficulty == "any":
            difficulty = None

        ingredients = tracker.get_slot("ingredients")
        num_people = tracker.get_slot("num_people")

        # recipes_df deve essere importato dal tuo data_loader
        recipes = search_recipes_guided(
            recipes_df,
            category=category,
            difficulty=difficulty,
            ingredients=ingredients,
            num_people=num_people
        )

        if not recipes:
            dispatcher.utter_message(response="utter_no_guided_results")
            return [SlotSet("last_recipes", [])]

        dispatcher.utter_message(
                    response="utter_guided_search_header", 
                    count=len(recipes)
                )
        
        response = "\n".join([f"{i+1}. {r}" for i, r in enumerate(recipes)])
        dispatcher.utter_message(response)

        dispatcher.utter_message(response="utter_ask_select_from_list")

        return [SlotSet("last_recipes", recipes)]
    
class ActionAddToShoppingList(Action):
    def name(self) -> str:
        return "action_add_to_shopping_list"

    def run(self, dispatcher, tracker, domain):
        # 1. Recupera la ricetta corrente
        recipe_name = tracker.get_slot("recipe_name")
        if not recipe_name:
            dispatcher.utter_message(response="utter_ask_recipe_for_shopping")
            return []

        # 2. Recupera i dati dal CSV
        recipe_data = get_recipe_by_name(recipes_df, recipe_name) # La tua funzione esistente
        if not recipe_data:
             dispatcher.utter_message(response="utter_recipe_data_error", recipe_name=recipe_name)
             return []
             
        # 3. Recupera la lista spesa attuale (o creane una vuota)
        current_list = tracker.get_slot("shopping_list") or {}
        
        # 4. UNISCI (La magia della somma)
        updated_list = merge_shopping_lists(current_list, recipe_data['ingredienti_parsed'])
        
        dispatcher.utter_message(
            response="utter_added_to_shopping_list", 
            recipe_name=recipe_name.title()
        )

        dispatcher.utter_message(response="utter_check_shopping_list_footer")
        
        return [SlotSet("shopping_list", updated_list)]

class ActionShowShoppingList(Action):
    def name(self) -> str:
        return "action_show_shopping_list"

    def run(self, dispatcher, tracker, domain):
        shopping_list = tracker.get_slot("shopping_list")
        
        if not shopping_list:
            dispatcher.utter_message(response="utter_shopping_list_empty")
            return []
            
        response = "🛒 LA TUA LISTA DELLA SPESA:\n"
        for name, data in shopping_list.items():
            # Se abbiamo sommato matematicamente, ricostruiamo la stringa pulita
            if data['amount'] is not None and "+" not in str(data['original_text']):
                # Formattazione carina: 500.0g -> 500g
                qty_clean = f"{data['amount']:.0f}" if data['amount'].is_integer() else f"{data['amount']}"
                line = f"- {name.title()}: {qty_clean}{data['unit']}"
            else:
                # Fallback: stampa il testo accumulato (es. "Sale: q.b. + 1 pizzico")
                line = f"- {name.title()}: {data['original_text']}"
                
            response += line + "\n"
            
        dispatcher.utter_message(response)
        dispatcher.utter_message(response="utter_shopping_list_footer")
        return []

class ActionClearShoppingList(Action):
    def name(self) -> str:
        return "action_clear_shopping_list"

    def run(self, dispatcher, tracker, domain):
        dispatcher.utter_message(response="utter_shopping_list_cleared")
        return [SlotSet("shopping_list", None)]