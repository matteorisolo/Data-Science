import pandas as pd

def get_recipes_by_category(df, category, limit=5):
    results = df[df["Categoria"] == category.lower()]

    if results.empty:
        return []

    sample_size = min(limit, len(results))

    return (
        results
        .sample(n=sample_size, random_state=None)
        ["Nome"]
        .tolist()
    )

def get_recipe_by_name(df: pd.DataFrame, recipe_name: str):
    """Restituisce il dizionario completo della ricetta dato il nome."""
    results = df[df["Nome"].str.lower() == recipe_name.lower()]

    if results.empty:
        return None

    # Prendiamo la prima corrispondenza e trasformiamo in dizionario
    recipe_row = results.iloc[0]
    return {
        "nome": recipe_row["Nome"],
        "ingredienti_parsed": recipe_row["ingredienti_parsed"],  # già lista di dict
        "preparazione": recipe_row["Steps"]
    }

def search_recipes_by_name(df, query, limit=5):
    """
    Cerca ricette il cui nome contiene la query (case-insensitive).
    Ritorna una lista di nomi di ricette.
    """
    if not query:
        return []

    query = query.lower().strip()

    results = df[df["Nome"].str.lower().str.contains(query, na=False)]

    return results["Nome"].head(limit).tolist()

def get_recipes_by_ingredients(df, ingredients):
    ingredients = [i.lower() for i in ingredients]

    matched_recipes = []

    for _, row in df.iterrows():
        recipe_ingredients = [
            ing["nome"].lower()
            for ing in row["ingredienti_parsed"]
        ]

        # match se almeno 1 ingrediente è presente
        if any(i in recipe_ingredients for i in ingredients):
            matched_recipes.append(row["Nome"])

    return matched_recipes[:5]  # max 5 risultati

def get_recipes_by_difficulty(
    recipes_df,
    difficulty: str,
    limit: int = 5,
    shuffle: bool = True
):
    """
    Restituisce una lista di nomi di ricette filtrate per difficoltà.
    """
    if not difficulty:
        return []

    difficulty = difficulty.lower().strip()

    filtered = recipes_df[
        recipes_df["difficolta"].str.lower() == difficulty
    ]

    if filtered.empty:
        return []

    if shuffle:
        filtered = filtered.sample(frac=1)

    return filtered["Nome"].head(limit).tolist()

def get_similar_recipes_by_ingredients(
    recipes_df,
    recipe_name: str,
    min_common: int = 4,
    limit: int = 5
):
    """
    Trova ricette simili in base agli ingredienti condivisi.
    """
    base = recipes_df[
        recipes_df["Nome"].str.lower() == recipe_name.lower()
    ]

    if base.empty:
        return []

    base_ingredients = set(
        i.strip().lower()
        for i in base.iloc[0]["Ingredienti"].split(",")
    )

    similarities = []

    for _, row in recipes_df.iterrows():
        name = row["Nome"]

        if name.lower() == recipe_name.lower():
            continue

        ingredients = set(
            i.strip().lower()
            for i in row["Ingredienti"].split(",")
        )

        common = base_ingredients & ingredients

        if len(common) >= min_common:
            similarities.append((name, len(common)))

    similarities.sort(key=lambda x: x[1], reverse=True)

    return [name for name, _ in similarities[:limit]]

def search_recipes_guided(
    recipes_df,
    category=None,
    difficulty=None,
    ingredients=None,
    num_people=None,
    limit=10
):
    df = recipes_df.copy()

    # Filtro Categoria (Solo se category non è None e non è "any")
    if category and category != "any":
        # Usa str.contains per essere più flessibile (es. "primi" trova "Primi piatti")
        df = df[df["Categoria"].str.lower().str.contains(str(category).lower(), na=False)]

    # Filtro Difficoltà
    if difficulty and difficulty != "any":
        df = df[df["difficolta"].str.lower() == str(difficulty).lower()]

    # Filtro Ingredienti (Logica OR: basta averne uno)
    if ingredients:
        # Assicuriamoci che ingredients sia una lista pulita
        ing_list = [i.lower() for i in ingredients]
        df = df[df["Ingredienti"].apply(
            lambda x: any(i in str(x).lower() for i in ing_list)
        )]

    # Filtro Persone (Opzionale: >= invece di == per trovare ricette "sufficienti")
    if num_people and "Persone/Pezzi" in df.columns:
         # Nota: nel CSV la colonna è 'Persone/Pezzi', assicurati del nome esatto
         # Puliamo la colonna da 'g' o testo se necessario, o gestiamo errori
         try:
            # Qui faccio un tentativo di conversione sicuro
            df["_temp_persone"] = pd.to_numeric(df["Persone/Pezzi"], errors='coerce')
            df = df[df["_temp_persone"] >= int(num_people)]
         except:
             pass # Se fallisce ignora il filtro

    if df.empty:
        return []

    return df["Nome"].tolist()[:limit]

import re

def parse_quantity(quantity_str):
    """
    Trasforma '200g' in (200.0, 'g').
    Trasforma '2 cucchiai' in (2.0, 'cucchiai').
    Trasforma 'q.b.' in (None, 'q.b.').
    """
    quantity_str = str(quantity_str).lower().strip()
    
    # Regex per cercare numeri (anche decimali) all'inizio della stringa
    match = re.match(r"([\d\.,]+)\s*(.*)", quantity_str)
    
    if match:
        number_str = match.group(1).replace(",", ".") # Gestione virgola italiana
        unit = match.group(2).strip()
        try:
            return float(number_str), unit
        except ValueError:
            return None, quantity_str
            
    return None, quantity_str

def merge_shopping_lists(current_list, new_ingredients):
    """
    current_list: Dizionario {'farina': {'qty': 500, 'unit': 'g'}, ...}
    new_ingredients: Lista di dict dal CSV [{'nome': 'farina', 'quantita': '200g'}]
    """
    if not current_list:
        current_list = {}

    for item in new_ingredients:
        name = item['nome'].lower().strip()
        raw_qty = item['quantita']
        
        amount, unit = parse_quantity(raw_qty)
        
        # Se l'ingrediente è già in lista
        if name in current_list:
            existing = current_list[name]
            
            # CASO 1: Le unità sono uguali e numeriche (es. g con g) -> SOMMA
            if amount is not None and existing['amount'] is not None and existing['unit'] == unit:
                existing['amount'] += amount
            
            # CASO 2: Unità diverse o non numeriche -> ACCODA IL TESTO (es. "200g + q.b.")
            else:
                # Creiamo una visualizzazione composta se non possiamo sommare matematicamente
                existing['original_text'] = f"{existing['original_text']} + {raw_qty}"
        
        # Se l'ingrediente è nuovo
        else:
            current_list[name] = {
                'amount': amount,
                'unit': unit,
                'original_text': raw_qty if amount is None else f"{amount} {unit}" # Fallback visivo
            }
            
    return current_list