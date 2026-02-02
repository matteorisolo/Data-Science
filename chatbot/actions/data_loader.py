import pandas as pd
import ast

DATASET_PATH = "C:\\Users\\risol\\Desktop\\Matteo\\Università\\Ingegneria Informatica e della Automazione\\2° anno\\Data Science\\Data-Science\\datasets\\italian_recipes_clean.csv"


def ensure_ingredients_parsed(value):
    # Se è già nel formato corretto (lista di dict)
    if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
        return value

    try:
        parsed = ast.literal_eval(value)

        # Caso: lista di dict
        if isinstance(parsed, list) and isinstance(parsed[0], dict):
            return [
                {
                    "nome": ing["nome"].strip().lower(),
                    "quantita": ing["quantita"].strip().lower()
                }
                for ing in parsed
            ]

        # Caso legacy: lista di tuple/list
        return [
            {
                "nome": ing[0].strip().lower(),
                "quantita": ing[1].strip().lower()
            }
            for ing in parsed
        ]
    except:
        return []

    
def load_recipes():
    df = pd.read_csv(DATASET_PATH)
    return df

recipes_df = load_recipes()

# Applica la funzione per garantire il formato corretto
recipes_df["ingredienti_parsed"] = recipes_df["ingredienti_parsed"].apply(ensure_ingredients_parsed)