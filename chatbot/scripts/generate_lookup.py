import pandas as pd

# 1. Carica il dataset delle ricette
df = pd.read_csv("C:\\Users\\risol\\Desktop\\Matteo\\Università\\Ingegneria Informatica e della Automazione\\2° anno\\Data Science\\Data-Science\\datasets\\italian_recipes_clean.csv")  # aggiorna il path se il tuo CSV sta altrove

# 2. Prendi tutti i nomi delle ricette, minuscolo per uniformità
recipes = df["Nome"].str.lower().unique()

# 3. Scrivi il file lookup YAML per Rasa
with open("data/nlu/lookup_recipes.yml", "w", encoding="utf-8") as f:
    f.write('version: "3.1"\n')
    f.write("nlu:\n")
    f.write("- lookup: recipe_name\n")
    f.write("  examples: |\n")
    for r in recipes:
        f.write(f"    - {r}\n")

print("File lookup_recipes.yml creato con successo!")
