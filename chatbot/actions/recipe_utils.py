import pandas as pd
import random
import re

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
    results = df[df["Nome"].str.lower() == recipe_name.lower()]

    if results.empty:
        return None

    recipe_row = results.iloc[0]
    return {
        "nome": recipe_row["Nome"],
        "ingredienti_parsed": recipe_row["ingredienti_parsed"],
        "preparazione": recipe_row["Steps"],
        "persone/pezzi": recipe_row.get("Persone/Pezzi", None)
    }

def search_recipes_by_name(df, query):
    if not query:
        return []

    query = query.lower().strip()

    results = df[df["Nome"].str.lower().str.contains(query, na=False)]

    if results.empty:
        return []

    return results.sample(frac=1)["Nome"].tolist()

def get_recipes_by_ingredients(df, ingredients):
    ingredients = [i.lower() for i in ingredients]

    matched_recipes = []

    for _, row in df.iterrows():
        recipe_ingredients = [
            ing["nome"].lower()
            for ing in row["ingredienti_parsed"]
        ]

        # match se tutti gli ingredienti richiesti sono presenti
        if all(i in recipe_ingredients for i in ingredients):
            matched_recipes.append(row["Nome"])

    if not matched_recipes:
        return []

    random.shuffle(matched_recipes)

    return matched_recipes[:5]

def get_recipes_by_difficulty(
    recipes_df,
    difficulty: str,
    limit: int = 5,
    shuffle: bool = True
):
    
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

# Definizione degli ingredienti comuni da ignorare
STOP_INGREDIENTS = {
    "sale", "sale fino", "sale grosso", "pepe", "pepe nero", 
    "acqua", "olio", "olio extravergine d'oliva", "olio evo", "olio di oliva"
}

def get_similar_recipes_by_ingredients(
    recipes_df,
    recipe_name: str,
    limit: int = 5
):
    base = recipes_df[
        recipes_df["Nome"].str.lower() == recipe_name.lower()
    ]

    if base.empty:
        return []

    base_row = base.iloc[0]
    
    # Estrazione ingredienti base
    if "ingredienti_parsed" in base_row:
        base_ingredients = set(i['nome'].lower() for i in base_row["ingredienti_parsed"])
    else:
        base_ingredients = set(i.strip().lower() for i in base_row["Ingredienti"].split(","))

    base_clean = base_ingredients - STOP_INGREDIENTS
    
    if not base_clean:
        base_clean = base_ingredients

    similarities = []

    for _, row in recipes_df.iterrows():
        current_name = row["Nome"]

        if current_name.lower() == recipe_name.lower():
            continue

        # Estrazione ingredienti correnti
        if "ingredienti_parsed" in row:
            current_ingredients = set(i['nome'].lower() for i in row["ingredienti_parsed"])
        else:
            current_ingredients = set(i.strip().lower() for i in row["Ingredienti"].split(","))

        current_clean = current_ingredients - STOP_INGREDIENTS
        
        if not current_clean: continue

        intersection = base_clean.intersection(current_clean)
        union = base_clean.union(current_clean)

        if not union: continue

        jaccard_score = len(intersection) / len(union)

        # Soglie di qualità
        if jaccard_score > 0.15 and len(intersection) >= 1:
            similarities.append((current_name, jaccard_score))

    # Ordinamento decrescente per similarità
    similarities.sort(key=lambda x: x[1], reverse=True)

    return [name for name, score in similarities[:limit]]

def search_recipes_guided(
    recipes_df,
    category=None,
    difficulty=None,
    ingredients=None,
    num_people=None,
    limit=10
):
    df = recipes_df.copy()

    # Filtro Categoria
    if category and category != "any":
        df = df[df["Categoria"].str.lower().str.contains(str(category).lower(), na=False)]

    # Filtro Difficoltà
    if difficulty and difficulty != "any":
        df = df[df["difficolta"].str.lower() == str(difficulty).lower()]

    # Filtro Ingredienti (Logica OR)
    if ingredients:
        ing_list = [i.lower() for i in ingredients]
        df = df[df["Ingredienti"].apply(
            lambda x: any(i in str(x).lower() for i in ing_list)
        )]

    # Filtro Persone
    if num_people and "Persone/Pezzi" in df.columns:
        try:
            df["_temp_persone"] = pd.to_numeric(df["Persone/Pezzi"], errors='coerce')
            df = df[df["_temp_persone"] >= int(num_people)]
        except:
            pass 

    if df.empty:
        return []
    
    return df.sample(frac=1)["Nome"].head(limit).tolist()

def parse_quantity(quantity_str):
    quantity_str = str(quantity_str).lower().strip()
    
    # Regex per cercare numeri (anche decimali) all'inizio della stringa
    match = re.match(r"([\d\.,]+)\s*(.*)", quantity_str)
    
    if match:
        number_str = match.group(1).replace(",", ".")
        unit = match.group(2).strip()
        try:
            return float(number_str), unit
        except ValueError:
            return None, quantity_str
            
    return None, quantity_str

def merge_shopping_lists(current_list, new_ingredients):
    if not current_list:
        current_list = {}

    for item in new_ingredients:
        name = item['nome'].lower().strip()
        raw_qty = item['quantita']
        
        amount, unit = parse_quantity(raw_qty)
        
        # Se l'ingrediente è già in lista
        if name in current_list:
            existing = current_list[name]
            
            # Le unità sono uguali e numeriche
            if amount is not None and existing['amount'] is not None and existing['unit'] == unit:
                existing['amount'] += amount
            
            # Unità diverse o non numeriche
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