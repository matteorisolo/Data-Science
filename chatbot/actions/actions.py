from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, ActiveLoop
from actions.data_loader import recipes_df  # il tuo dataset
from actions.recipe_utils import get_recipe_by_name  # funzione da creare
from actions.recipe_utils import get_recipes_by_category
from actions.recipe_utils import search_recipes_by_name
from actions.recipe_utils import get_recipes_by_ingredients
from actions.recipe_utils import get_recipes_by_difficulty
from actions.recipe_utils import get_similar_recipes_by_ingredients
from actions.recipe_utils import search_recipes_guided


class ActionSearchByCategory(Action):

    def name(self) -> str:
        return "action_search_by_category"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):

        category = tracker.get_slot("category")

        if not category:
            dispatcher.utter_message("Che tipo di piatto cerchi?")
            return []

        recipes = get_recipes_by_category(recipes_df, category)

        if not recipes:
            dispatcher.utter_message(
                f"Non ho trovato ricette per la categoria '{category}'."
            )
            return []

        response = f"Ecco alcune ricette {category} 🍽️:\n"
        response += "\n".join([f"• {r}" for r in recipes])

        dispatcher.utter_message(response)
        return [SlotSet("last_recipes", recipes)]

class ActionSelectRecipe(Action):

    def name(self) -> str:
        return "action_select_recipe"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):

        recipe_name = tracker.get_slot("recipe_name")
        last_recipes = tracker.get_slot("last_recipes") or []

        if not recipe_name or recipe_name.lower() not in [r.lower() for r in last_recipes]:
            dispatcher.utter_message(
                f"Non ho trovato '{recipe_name}' tra le ultime ricette suggerite. "
                f"Prova a sceglierne una dalle ultime {len(last_recipes)}."
            )
            return []

        recipe_data = get_recipe_by_name(recipes_df, recipe_name)

        if not recipe_data:
            dispatcher.utter_message(f"Ops, non sono riuscito a trovare la ricetta '{recipe_name}'.")
            return []

        # Creiamo la lista degli ingredienti
        formatted_ingredients = [
            f"- {i['nome'].title()}: {i['quantita']}" for i in recipe_data["ingredienti_parsed"]
        ]

        response = f"🍽 {recipe_data['nome'].title()}\n\nIngredienti:\n"
        response += "\n".join(formatted_ingredients)
        response += f"\n\nPreparazione:\n{recipe_data['preparazione']}"

        dispatcher.utter_message(response)
        return []

class ActionSelectByIndex(Action):

    def name(self) -> str:
        return "action_select_by_index"

    def run(self, dispatcher, tracker, domain):

        text = tracker.latest_message.get("text", "").lower()
        last_recipes = tracker.get_slot("last_recipes") or []

        if not last_recipes:
            dispatcher.utter_message(
                "Non ho ancora suggerito nessuna ricetta."
            )
            return []

        # Mapping parole → indice
        mapping = {
            "prima": 0,
            "seconda": 1,
            "terza": 2,
            "quarta": 3,
            "quinta": 4,
            "ultima": len(last_recipes) - 1
        }

        index = None
        for key, value in mapping.items():
            if key in text:
                index = value
                break

        if index is None or index < 0 or index >= len(last_recipes):
            dispatcher.utter_message(
                f"Puoi scegliere una posizione tra 1 e {len(last_recipes)}."
            )
            return []

        recipe_name = last_recipes[index]

        dispatcher.utter_message(
            f"Ok! Ti mostro la ricetta **{recipe_name}** 🍽️"
        )

        return [
            SlotSet("recipe_name", recipe_name)
        ]

class ActionShowShoppingList(Action):

    def name(self) -> str:
        return "action_show_shopping_list"

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
            dispatcher.utter_message(
                "Non hai specificato quale ricetta. "
                "Puoi dirmi il nome o la posizione tra le ultime suggerite."
            )
            return [SlotSet("recipe_name", None)]  # reset slot

        # --- Recuperiamo i dati della ricetta ---
        recipe_data = get_recipe_by_name(recipes_df, recipe_name)
        if not recipe_data:
            dispatcher.utter_message(f"Non ho trovato '{recipe_name}' tra le ricette disponibili.")
            return [SlotSet("recipe_name", None)]  # reset slot

        # --- Lista ingredienti ---
        ingredients = recipe_data.get("ingredienti_parsed", [])
        if not ingredients:
            dispatcher.utter_message("Ops, questa ricetta non ha ingredienti registrati.")
            return [SlotSet("recipe_name", recipe_name)]

        formatted_ingredients = [f"- {i['nome'].title()}: {i['quantita']}" for i in ingredients]

        response = f"🛒 Lista della spesa per {recipe_data['nome'].title()}:\n"
        response += "\n".join(formatted_ingredients)

        dispatcher.utter_message(response)

        # --- Aggiorniamo sempre lo slot con la ricetta corrente ---
        return [SlotSet("recipe_name", recipe_name)]

class ActionSearchByName(Action):

    def name(self) -> str:
        return "action_search_by_name"

    def run(self, dispatcher, tracker, domain):

        query = tracker.get_slot("recipe_name")

        if not query:
            dispatcher.utter_message(
                "Che ricetta stai cercando?"
            )
            return []

        results = search_recipes_by_name(recipes_df, query)

        if not results:
            dispatcher.utter_message(
                f"Non ho trovato ricette che contengono '{query}'."
            )
            return []

        # 🔹 Caso 1: una sola ricetta → mostriamo direttamente
        if len(results) == 1:
            recipe_name = results[0]
            dispatcher.utter_message(
                f"Ho trovato la ricetta **{recipe_name}** 🍽️"
            )
            return [
                SlotSet("last_recipes", results),
                SlotSet("recipe_name", recipe_name)
            ]

        # 🔹 Caso 2: più ricette → lista
        response = "Ho trovato queste ricette 🍽️:\n"
        response += "\n".join([f"• {r}" for r in results])

        dispatcher.utter_message(response)

        return [
            SlotSet("last_recipes", results),
            SlotSet("recipe_name", None)  # IMPORTANTISSIMO
        ]
    
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
            # prendiamo le parole che non siano troppo brevi
            ingredients = [w.strip() for w in text.split() if len(w) > 2]

        # --- Resettiamo lo slot last_recipes all'inizio per evitare risultati vecchi ---
        SlotSet("last_recipes", None)

        # --- Recuperiamo le ricette corrispondenti ---
        recipes = get_recipes_by_ingredients(recipes_df, ingredients)

        if not recipes:
            dispatcher.utter_message(
                "Non ho trovato ricette con questi ingredienti 😕"
            )
            return [SlotSet("last_recipes", [])]

        # --- Formattiamo la risposta ---
        response = "Ecco alcune ricette che puoi fare 🍽️:\n"
        response += "\n".join([f"• {r}" for r in recipes])

        dispatcher.utter_message(response)

        # --- Aggiorniamo lo slot last_recipes con i nuovi risultati ---
        return [SlotSet("last_recipes", recipes)]
    
class ActionSurpriseMe(Action):

    def name(self) -> str:
        return "action_surprise_me"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):

        if recipes_df.empty:
            dispatcher.utter_message(
                "Ops, al momento non ho ricette disponibili 😕"
            )
            return []

        # scegliamo una ricetta casuale
        recipe_row = recipes_df.sample(1).iloc[0]
        recipe_name = recipe_row["Nome"]

        recipe_data = get_recipe_by_name(recipes_df, recipe_name)

        if not recipe_data:
            dispatcher.utter_message(
                "Ops, qualcosa è andato storto con la ricetta casuale 😅"
            )
            return []

        # ingredienti
        formatted_ingredients = [
            f"- {i['nome'].title()}: {i['quantita']}"
            for i in recipe_data["ingredienti_parsed"]
        ]

        response = f"🎲 Ti propongo questa ricetta a sorpresa!\n\n"
        response += f"🍽 {recipe_data['nome'].title()}\n\n"
        response += "Ingredienti:\n"
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
            dispatcher.utter_message("Non hai specificato il livello di difficoltà 😕")
            return []

        # Chiamo la funzione helper
        recipes = get_recipes_by_difficulty(recipes_df, difficulty)

        if not recipes:
            dispatcher.utter_message(f"Non ho trovato ricette di difficoltà '{difficulty}' 😕")
            return []

        # Risposta all'utente
        response = f"Ecco alcune ricette di difficoltà '{difficulty}' 🍽️:\n"
        response += "\n".join([f"• {r}" for r in recipes])
        dispatcher.utter_message(response)

        # Salvo le ultime ricette suggerite
        return [SlotSet("last_recipes", recipes)]

class ActionSuggestSimilarRecipes(Action):

    def name(self) -> str:
        return "action_suggest_similar_recipes"

    def run(self, dispatcher, tracker, domain):

        recipe_name = tracker.get_slot("recipe_name")

        if not recipe_name:
            dispatcher.utter_message(
                "Dimmi prima una ricetta così posso suggerirti qualcosa di simile 🙂"
            )
            return []

        recipes = get_similar_recipes_by_ingredients(
            recipes_df,
            recipe_name
        )

        if not recipes:
            dispatcher.utter_message(
                "Non ho trovato ricette simili a questa 😕"
            )
            return []

        response = "Se ti è piaciuta questa, prova anche 🍽️:\n"
        response += "\n".join([f"• {r}" for r in recipes])

        dispatcher.utter_message(response)

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
            dispatcher.utter_message("Non ho trovato ricette con questi criteri 😕")
            return [SlotSet("last_recipes", [])]

        response = "Ecco alcune ricette che potrebbero piacerti 🍽️:\n"
        response += "\n".join([f"{i+1}. {r}" for i, r in enumerate(recipes)])
        dispatcher.utter_message(response)

        return [SlotSet("last_recipes", recipes)]