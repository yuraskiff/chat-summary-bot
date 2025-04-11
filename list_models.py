import os
import openai

def main():
    openai.api_key = os.getenv("OPENAI_API_KEY")
    try:
        models = openai.Model.list()
        print("Доступные модели OpenAI:")
        for model in models.data:
            print(model.id)
    except Exception as e:
        print(f"Ошибка при получении списка моделей: {e}")

if __name__ == "__main__":
    main()
